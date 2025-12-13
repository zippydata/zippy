# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in ZDS, please report it responsibly:

1. **Do NOT open a public issue**
2. Email security concerns to: zippy@omarkama.li
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Considerations

### Data at Rest

ZDS stores data as plain JSON/JSONL files:

- **No encryption by default**: Data is stored in human-readable format
- **File permissions**: ZDS respects OS file permissions
- **Recommendation**: Use filesystem encryption (e.g., LUKS, FileVault, BitLocker) for sensitive data

### Dependencies

We regularly audit dependencies for known vulnerabilities:

```bash
# Rust
cargo audit

# Python
pip-audit

# Node.js
npm audit
```

### Rust Dependencies

| Package | Version | Purpose | Security Notes |
|---------|---------|---------|----------------|
| serde | 1.0 | Serialization | Widely audited |
| serde_json | 1.0 | JSON parsing | Standard, well-maintained |
| simd-json | 0.14 | Fast JSON parsing | SIMD-safe |
| memmap2 | 0.9 | Memory mapping | Unsafe code for performance |
| zip | 0.6 | Archive handling | Deflate only, no zip bombs |
| blake3 | 1.5 | Hashing | Cryptographically secure |
| tempfile | 3 | Temp files | Secure temp directory handling |
| rayon | 1.10 | Parallelism | Safe parallelism |

### Python Dependencies

| Package | Purpose | Security Notes |
|---------|---------|----------------|
| maturin | Build | Build-time only |
| pyo3 | FFI | Well-audited Rust-Python bridge |

### Node.js Dependencies

| Package | Purpose | Security Notes |
|---------|---------|----------------|
| napi-rs | FFI | Well-audited Rust-Node bridge |

## Best Practices

### For Users

1. **Validate input**: Always validate data before storing
2. **Use secure paths**: Avoid storing in world-readable directories
3. **Regular updates**: Keep ZDS and dependencies updated
4. **Backup data**: ZDS files are regular files; use standard backup tools

### For Contributors

1. **No unsafe code without justification**: Document why unsafe is needed
2. **Dependency review**: Audit new dependencies before adding
3. **Fuzz testing**: Consider fuzz testing for parsing code
4. **No secrets in code**: Never commit API keys or tokens

## Dependency Pinning

### Rust (Cargo.lock)

The `Cargo.lock` file is committed to ensure reproducible builds.

### Python (uv.lock / requirements.txt)

For production deployments:

```bash
pip freeze > requirements.lock
```

### Node.js (package-lock.json)

The `package-lock.json` is committed for reproducible installs.

## Audit Commands

```bash
# Run all audits
make audit

# Individual audits
cargo audit
pip-audit
npm audit
```

## Known Limitations

1. **No authentication**: ZDS is a file format, not a database server
2. **No encryption**: Data is stored in plaintext
3. **No access control**: Relies on filesystem permissions
4. **No network isolation**: Not designed for network access

For applications requiring these features, consider wrapping ZDS with appropriate infrastructure.
