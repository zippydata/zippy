# ZDS Development Makefile
# Convenient commands for development, testing, and linting

.PHONY: all build test lint format check clean docs

# ============================================================================
# Build
# ============================================================================

all: build

build:
	cargo build --release

build-python:
	cd python && maturin develop

build-nodejs:
	cd nodejs && npm run build

# ============================================================================
# Test
# ============================================================================

test: test-rust test-python test-nodejs

test-rust:
	cargo test --all

test-python:
	cd python && pytest -v

test-nodejs:
	cd nodejs && npm test

# ============================================================================
# Lint
# ============================================================================

lint: lint-rust lint-python lint-nodejs

lint-rust:
	cargo fmt --all -- --check
	cargo clippy --all -- -D warnings

lint-python:
	cd python && ruff check zippy/ tests/
	cd python && ruff format --check zippy/ tests/
	cd python && mypy zippy/ --ignore-missing-imports

lint-nodejs:
	cd nodejs && npm run lint
	cd nodejs && npm run format:check

# ============================================================================
# Format
# ============================================================================

format: format-rust format-python format-nodejs

format-rust:
	cargo fmt --all

format-python:
	cd python && ruff format zippy/ tests/
	cd python && ruff check --fix zippy/ tests/

format-nodejs:
	cd nodejs && npm run format
	cd nodejs && npm run lint:fix

# ============================================================================
# Check (lint + test)
# ============================================================================

check: lint test

# ============================================================================
# Benchmarks
# ============================================================================

bench: bench-rust

bench-rust:
	cd crates/zippy_data && cargo bench

bench-python:
	cd benchmarks/python && python benchmark_io.py

bench-nodejs:
	cd benchmarks/nodejs && node benchmark_io.js

# ============================================================================
# Docs
# ============================================================================

docs:
	cargo doc --no-deps --open

docs-serve:
	cd docs && bundle exec jekyll serve

# ============================================================================
# Security
# ============================================================================

audit:
	cargo audit
	cd python && pip-audit || true
	cd nodejs && npm audit || true

# ============================================================================
# Clean
# ============================================================================

clean:
	cargo clean
	rm -rf python/.pytest_cache python/*.egg-info
	rm -rf nodejs/node_modules nodejs/dist
	rm -rf examples/data/
	rm -rf docs/_site

# ============================================================================
# Release Prep
# ============================================================================

release-check: lint test audit
	@echo "✅ All checks passed!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Update version numbers"
	@echo "  2. Update CHANGELOG.md"
	@echo "  3. Create git tag: git tag -a v0.1.0 -m 'Release v0.1.0'"
	@echo "  4. Push: git push && git push --tags"

# ============================================================================
# Help
# ============================================================================

help:
	@echo "ZDS Development Commands"
	@echo ""
	@echo "Build:"
	@echo "  make build          - Build Rust release"
	@echo "  make build-python   - Build Python package"
	@echo "  make build-nodejs   - Build Node.js package"
	@echo ""
	@echo "Test:"
	@echo "  make test           - Run all tests"
	@echo "  make test-rust      - Run Rust tests"
	@echo "  make test-python    - Run Python tests"
	@echo "  make test-nodejs    - Run Node.js tests"
	@echo ""
	@echo "Lint:"
	@echo "  make lint           - Run all linters"
	@echo "  make format         - Auto-format all code"
	@echo ""
	@echo "Benchmark:"
	@echo "  make bench          - Run Rust benchmarks"
	@echo ""
	@echo "Security:"
	@echo "  make audit          - Run security audit"
	@echo ""
	@echo "Other:"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make release-check  - Pre-release validation"
