# Release Process

This document describes the release process for Zippy (ZDS) across all platforms.

## Overview

Zippy publishes to multiple package registries:

| Platform | Registry | Package Name |
|----------|----------|--------------|
| Python | PyPI | `zippy-data` |
| Node.js | npm | `@zippydata/core` |
| Rust | crates.io | `zippy-core` |

All releases are automated via GitHub Actions with trusted publishing (no manual token management).

---

## Quick Release (Automated)

```bash
# 1. Update version in all manifests (see Version Locations below)
# 2. Create and push a tag
git tag v0.1.0
git push origin v0.1.0

# 3. GitHub Actions will automatically:
#    - Build all packages
#    - Run tests
#    - Publish to PyPI, npm, crates.io
#    - Create GitHub Release with artifacts
```

---

## Version Locations

Update version in ALL of these files before release:

```
python/zippy/__init__.py          __version__ = "0.1.0"
python/pyproject.toml             version = "0.1.0"
nodejs/package.json               "version": "0.1.0"
crates/zippy_core/Cargo.toml      version = "0.1.0"
crates/zippy_python/Cargo.toml    version = "0.1.0"
crates/zippy_nodejs/Cargo.toml    version = "0.1.0"
```

Use semantic versioning: `MAJOR.MINOR.PATCH`
- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

---

## CI/CD Pipeline

### GitHub Actions Workflows

#### `.github/workflows/release.yml` (Main Release)

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write
  id-token: write  # For trusted publishing

jobs:
  # Build Python wheels for all platforms
  build-python:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.9', '3.10', '3.11', '3.12']
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - uses: PyO3/maturin-action@v1
        with:
          command: build
          args: --release -o dist
          working-directory: crates/zippy_python
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}-${{ matrix.python-version }}
          path: crates/zippy_python/dist/*.whl

  # Build Node.js bindings
  build-nodejs:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
        working-directory: nodejs
      - run: npm run build
        working-directory: nodejs
      - uses: actions/upload-artifact@v4
        with:
          name: nodejs-${{ matrix.os }}
          path: nodejs/*.node

  # Publish to PyPI (trusted publishing)
  publish-pypi:
    needs: build-python
    runs-on: ubuntu-latest
    environment: release
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          pattern: wheels-*
          merge-multiple: true
          path: dist
      - uses: pypa/gh-action-pypi-publish@release/v1
        # No token needed - uses trusted publishing

  # Publish to npm
  publish-npm:
    needs: build-nodejs
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'
      - uses: actions/download-artifact@v4
        with:
          pattern: nodejs-*
          merge-multiple: true
          path: nodejs
      - run: npm publish --access public
        working-directory: nodejs
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}

  # Publish to crates.io
  publish-cargo:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo publish -p zippy-core
        env:
          CARGO_REGISTRY_TOKEN: ${{ secrets.CARGO_TOKEN }}

  # Create GitHub Release
  create-release:
    needs: [publish-pypi, publish-npm, publish-cargo]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: artifacts
      - uses: softprops/action-gh-release@v1
        with:
          files: |
            artifacts/**/*.whl
            artifacts/**/*.node
          generate_release_notes: true
```

#### `.github/workflows/ci.yml` (Continuous Integration)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
        working-directory: python
      - run: pytest
        working-directory: python

  test-nodejs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci && npm test
        working-directory: nodejs

  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo test --all

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: clippy, rustfmt
      - run: cargo fmt --all -- --check
      - run: cargo clippy --all -- -D warnings
```

---

## Registry Setup (One-Time)

### PyPI Trusted Publishing

1. Go to PyPI → Account Settings → Publishing
2. Add new pending publisher:
   - Repository: `zippydata/zippy`
   - Workflow: `release.yml`
   - Environment: `release`

### npm

1. Create npm account and org (@zippydata)
2. Generate automation token
3. Add `NPM_TOKEN` to GitHub Secrets

### crates.io

1. Login: `cargo login`
2. Generate token at crates.io
3. Add `CARGO_TOKEN` to GitHub Secrets

### GitHub

1. Create `release` environment in repo settings
2. Add required reviewers (optional)
3. Enable "Require approval for all outside collaborators"

---

## Pre-Release Checklist

Before creating a release tag:

### Code Quality
- [ ] All tests pass (`pytest`, `npm test`, `cargo test`)
- [ ] No clippy warnings (`cargo clippy`)
- [ ] Code formatted (`cargo fmt`, `black`, `prettier`)
- [ ] Documentation updated

### Version Bump
- [ ] `python/zippy/__init__.py` updated
- [ ] `python/pyproject.toml` updated
- [ ] `nodejs/package.json` updated
- [ ] `crates/*/Cargo.toml` updated
- [ ] All versions match

### Documentation
- [ ] CHANGELOG.md updated
- [ ] README.md accurate
- [ ] API docs generated
- [ ] Examples work with new version

### Testing
- [ ] Manual smoke test on all platforms
- [ ] Benchmarks show no regression
- [ ] New features documented and tested

---

## Release Checklist

### Create Release

```bash
# 1. Ensure main is up to date
git checkout main
git pull origin main

# 2. Verify all checks pass
cargo test --all
cd python && pytest && cd ..
cd nodejs && npm test && cd ..

# 3. Create annotated tag
git tag -a v0.1.0 -m "Release v0.1.0"

# 4. Push tag (triggers CI/CD)
git push origin v0.1.0
```

### Post-Release Verification

- [ ] GitHub Actions workflow completed successfully
- [ ] PyPI package available: `pip install zippy-data==0.1.0`
- [ ] npm package available: `npm install @zippydata/core@0.1.0`
- [ ] crates.io package available: `cargo add zippy-core@0.1.0`
- [ ] GitHub Release created with artifacts
- [ ] Documentation site updated (if applicable)

---

## Hotfix Process

For critical bug fixes:

```bash
# 1. Create hotfix branch from tag
git checkout -b hotfix/v0.1.1 v0.1.0

# 2. Apply fix
git commit -m "Fix: critical bug"

# 3. Bump patch version in all files

# 4. Create new tag
git tag -a v0.1.1 -m "Hotfix v0.1.1"

# 5. Push
git push origin hotfix/v0.1.1
git push origin v0.1.1

# 6. Merge back to main
git checkout main
git merge hotfix/v0.1.1
git push origin main
```

---

## Rollback Process

If a release has critical issues:

### PyPI
```bash
# Yank the release (prevents new installs, existing installs unaffected)
pip install twine
twine yank zippy-data 0.1.0
```

### npm
```bash
npm deprecate @zippydata/core@0.1.0 "Critical bug, use 0.1.1"
# Or unpublish within 72 hours:
npm unpublish @zippydata/core@0.1.0
```

### crates.io
```bash
cargo yank --version 0.1.0 zippy-core
```

### GitHub
1. Delete the release in GitHub UI
2. Delete the tag: `git push origin :refs/tags/v0.1.0`

---

## Security Considerations

### Secrets Management
- **Never** commit tokens or credentials
- Use GitHub Secrets for all tokens
- Rotate tokens annually
- Use environment protection rules

### Trusted Publishing (PyPI)
- No token stored in GitHub
- Tied to specific repo/workflow/environment
- Audit log in PyPI

### Code Signing (Future)
- Consider sigstore for Python wheels
- Consider npm provenance
- Consider cargo audit

---

## Troubleshooting

### Build Failures

**Python wheels:**
```bash
# Test locally
cd crates/zippy_python
maturin build --release
```

**Node.js bindings:**
```bash
# Test locally
cd nodejs
npm run build
```

### Publishing Failures

**PyPI 403 Forbidden:**
- Check trusted publishing setup
- Verify environment name matches
- Check repo/workflow in PyPI settings

**npm 401 Unauthorized:**
- Verify NPM_TOKEN is valid
- Check token has publish scope
- Verify package name is available

**crates.io 401:**
- Verify CARGO_TOKEN is valid
- Check crate name is available
- Ensure version not already published

---

## Changelog Template

```markdown
# Changelog

## [0.2.0] - 2025-XX-XX

### Added
- Feature X
- Feature Y

### Changed
- Improved performance of Z

### Fixed
- Bug in A
- Issue with B

### Deprecated
- Old API C (use D instead)

### Removed
- Obsolete feature E

### Security
- Fixed vulnerability F
```

---

## Contact

- **Maintainer**: Omar Kamali
- **Repository**: https://github.com/zippydata/zippy
- **Issues**: https://github.com/zippydata/zippy/issues
