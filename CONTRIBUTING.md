# Contributing to PASS

Thank you for your interest in contributing to **PASS (Peer-to-peer Automated Secure Sharing)**!

## Development Guidelines

1. **Keep it Zero-Configuration**:
   - The core philosophy of PASS is that users should never have to manually enter IP addresses, ports, subnets, or configure SSH/SMB.
2. **Terminal-First & Cross-Platform**:
   - Ensure changes run reliably across Windows, Linux, and Android Termux.
   - Do not introduce heavy C-extensions or external database/cloud requirements.
3. **Security is Mandatory**:
   - Every file transfer MUST be verified with cryptographic hashes (SHA-256).
   - Inbound files MUST be sanitized against path traversal attacks.
   - Keep network traffic TLS encrypted.

## Setting Up Development Environment

```bash
git clone https://github.com/adityasing9/SettleHub.git
cd SettleHub
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running Tests

Run the full pytest suite before submitting any pull request:

```bash
python -m pytest tests/ -v
```

## Submitting Pull Requests

1. Create a feature branch (`git checkout -b feature/awesome-feature`).
2. Commit your changes with clear, descriptive commit messages.
3. Verify that all automated tests pass.
4. Push to your branch and open a Pull Request.
