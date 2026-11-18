# Contributing to SUSCRCPY

Thank you for your interest in contributing to SUSCRCPY!

## Code of Conduct
Please be polite, constructive, and respectful to all community members.

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/Shadab-2604/suscrcpy.git
   cd suscrcpy
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run the automated test suite:
   ```bash
   python3 -m unittest discover -s tests -v
   ```

4. Launch the development version:
   ```bash
   python3 main.py --debug
   ```

## Pull Request Guidelines

- Branch naming: `feature/short-description` or `fix/short-description`.
- Run tests before submitting pull requests: `python3 -m unittest discover -s tests`.
- Do not commit virtual environments, compiled bytecode (`__pycache__`), or sensitive device tokens.
- Maintain compatibility with Debian and Kali Linux environments.
- Follow PEP 8 style standards and provide type hints where appropriate.
