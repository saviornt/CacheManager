# Contributing

Thank you for your interest in contributing to CacheManager! This guide will help you get started with the development process.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/username/CacheManager.git
   cd CacheManager
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```
3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Coding Standards

- Follow PEP 8 style guidelines
- Use type annotations for all function parameters and return values
- Write docstrings in Google format
- Use Ruff for linting and formatting

## Pull Request Process

1. Fork the repository
2. Create a feature branch (git checkout -b feature/amazing-feature)
3. Make your changes
4. Ensure all tests pass:
   ```bash
   pytest tests/
   ```
5. Commit your changes (git commit -m ‘Add amazing feature’)
6. Push to the branch (git push origin feature/amazing-feature)
7. Open a Pull Request

## Running Tests

Run the test suite with:

```bash
pytest
```

For coverage report:

```bash
pytest --cov=src tests/
```

## Building Documentation

Build the documentation locally:

```bash
cd docs
make html
```

The built documentation will be in docs/build/html/.
