# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.1.x   | :white_check_mark: |
| 2.0.x   | :x:                |
| 1.0.x   | :x:                |

## Security Architecture & Threat Model

SUSCRCPY includes an automatic system updater that runs with administrator privileges (`sudo suscrcpy --update`). To safeguard users against attacks, the following measures are enforced:

1. **Strict Transport Security (HTTPS Only)**:
   - All communication with the GitHub Releases API and all asset downloads are strictly performed over encrypted HTTPS (`urllib.request` with standard certificate verification).

2. **Cryptographic Checksum Verification**:
   - Every downloaded archive (`suscrcpy-source.zip`) is hashed with SHA-256 and compared against the published `SHA256SUMS` file before extraction.
   - Any checksum discrepancy results in immediate abortion of the update process.

3. **Archive Security & Zip Slip Protection**:
   - Archive extraction validates each member path to ensure it cannot escape the destination directory.
   - Absolute paths (e.g. `/etc/...`) and path traversal sequences (`../../`) are blocked and raise `ArchiveSecurityError`.

4. **Atomic Staging and Rollback**:
   - Updates are staged in isolated temporary directories (`/tmp/suscrcpy_update_*`).
   - The current installation is backed up prior to file replacement.
   - The new installation runs a self-test dry-run (`python3 /opt/suscrcpy/main.py --version`). If verification fails, the backup is automatically restored.

5. **No Script Execution**:
   - The updater strictly extracts verified application assets and never executes untrusted remote shell scripts or arbitrary downloaded code.

6. **Trust Boundary Limitation**:
   - A checksum published alongside an archive on GitHub protects against transmission errors and asset tampering, but does not protect against a compromised maintainer account. Publication access must remain restricted to authorized maintainers with multi-factor authentication (MFA).

## Reporting a Vulnerability

If you discover a security vulnerability in SUSCRCPY:
1. Do **not** open a public issue.
2. Email the maintainers directly or use GitHub Private Vulnerability Reporting on the repository:
   https://github.com/Shadab-2604/suscrcpy/security/advisories/new
3. Provide details on how to reproduce the issue and affected versions.
4. We aim to acknowledge reports within 48 hours and release patches in a timely manner.
