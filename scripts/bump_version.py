#!/usr/bin/env python3
"""Utility to bump the Zippy version across all packages.

Usage:
    python scripts/bump_version.py 0.2.0
    python scripts/bump_version.py 0.2.0 --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Pattern

ROOT = Path(__file__).resolve().parents[1]


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
WORKSPACE_VERSION_RE = re.compile(
    r"(?ms)(\[workspace\.package\][^\[]*?version\s*=\s*)\"([^\"]+)\""
)
PYPROJECT_VERSION_RE = re.compile(
    r"(?ms)(\[project\][^\[]*?version\s*=\s*)\"([^\"]+)\""
)
PY_INIT_VERSION_RE = re.compile(r"(?m)(__version__\s*=\s*)\"([^\"]+)\"")
ZDS_CONST_RE = re.compile(r"(?m)(pub const ZDS_VERSION: &str = )\"([^\"]+)\"")


@dataclass
class RegexTarget:
    description: str
    path: Path
    pattern: Pattern[str]

    def apply(self, new_version: str, dry_run: bool) -> None:
        original = self.path.read_text()
        replacement = self.pattern.sub(
            lambda match: f"{match.group(1)}\"{new_version}\"",
            original,
            count=1,
        )
        if original == replacement:
            raise RuntimeError(f"Could not update {self.description} in {self.path}")
        if dry_run:
            print(f"[dry-run] Would update {self.description} -> {new_version}")
            return
        self.path.write_text(replacement)
        print(f"Updated {self.description} -> {new_version}")


def ensure_semver(value: str) -> str:
    if not SEMVER_RE.match(value):
        raise argparse.ArgumentTypeError(
            "Version must be a valid semantic version, e.g., 1.2.3 or 1.2.3-beta"
        )
    return value


def current_version() -> str:
    cargo = (ROOT / "Cargo.toml").read_text()
    match = WORKSPACE_VERSION_RE.search(cargo)
    if not match:
        raise RuntimeError("Could not find workspace version in Cargo.toml")
    return match.group(2)


def update_package_json(path: Path, new_version: str, dry_run: bool) -> None:
    data = json.loads(path.read_text())
    old_version = data.get("version")
    if not old_version:
        raise RuntimeError(f"Missing version field in {path}")
    if data["version"] == new_version:
        print(f"{path} already at {new_version}")
        return
    data["version"] = new_version
    if "packages" in data and "" in data["packages"]:
        data["packages"][""]["version"] = new_version
    payload = json.dumps(data, indent=2) + "\n"
    if dry_run:
        print(f"[dry-run] Would update npm manifest {path} -> {new_version}")
        return
    path.write_text(payload)
    print(f"Updated npm manifest {path} -> {new_version}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bump Zippy versions everywhere")
    parser.add_argument("version", type=ensure_semver, help="New semantic version")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing files"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    new_version = args.version
    current = current_version()

    if current == new_version:
        print(f"Workspace already at {new_version}; nothing to do")
        return

    targets = [
        RegexTarget(
            description="Cargo workspace version",
            path=ROOT / "Cargo.toml",
            pattern=WORKSPACE_VERSION_RE,
        ),
        RegexTarget(
            description="Python pyproject version",
            path=ROOT / "python" / "pyproject.toml",
            pattern=PYPROJECT_VERSION_RE,
        ),
        RegexTarget(
            description="python/zippy __version__",
            path=ROOT / "python" / "zippy" / "__init__.py",
            pattern=PY_INIT_VERSION_RE,
        ),
        RegexTarget(
            description="Rust ZDS_VERSION constant",
            path=ROOT / "crates" / "zippy_data" / "src" / "lib.rs",
            pattern=ZDS_CONST_RE,
        ),
    ]

    for target in targets:
        target.apply(new_version, args.dry_run)

    update_package_json(ROOT / "nodejs" / "package.json", new_version, args.dry_run)
    update_package_json(ROOT / "nodejs" / "package-lock.json", new_version, args.dry_run)

    print("Done. Remember to git commit, tag, and run release workflow.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
