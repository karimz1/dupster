# Contributing to Dupster

Thank you for your interest in contributing to Dupster! I welcome contributions from the community.

## Getting Started

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/karimz1/dupster.git
   cd dupster
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Run tests to verify setup**
   ```bash
   pytest -v
   ```

## Development Workflow

### Running Dupster Locally

```bash
python dupster.py /path/to/test/folder
```

Or install in editable mode:
```bash
pip install -e .
dupster /path/to/test/folder
```

### Code Style

Dupster uses **Black** for code formatting and **Ruff** for linting.

**Format your code:**
```bash
black .
```

**Lint your code:**
```bash
ruff check .
```

**Auto-fix linting issues:**
```bash
ruff check --fix .
```

### Testing

Run the full test suite:
```bash
pytest -v
```

Run specific tests:
```bash
pytest tests/test_scanner.py -v
pytest tests/test_scanner.py::test_specific_function -v
```

Run tests with coverage:
```bash
pytest --cov=src/dupster --cov-report=html
```

### Generating Test Data

Use the test data generator:
```bash
python tools/generate_dupes.py
```

This creates a realistic duplicate file dataset under `temp/` for manual testing.

## Architecture Guidelines

Dupster follows **Clean Architecture** principles:

- **Domain** (`src/dupster/domain/`): Core business logic and entities
- **Application** (`src/dupster/application/`): Use cases (scanner, planner)
- **Infrastructure** (`src/dupster/infrastructure/`): External dependencies (filesystem, hashing)
- **UI** (`src/dupster/ui/`): User interfaces (CLI, TUI)
- **Utils** (`src/dupster/utils/`): Shared utilities

### Coding Principles

- **Single Responsibility**: Each function/class should do one thing well
- **Testability**: Application layer should be easy to test without UI
- **Small Functions**: Keep functions focused and under 20 lines when possible
- **Type Hints**: Use type annotations for better IDE support
- **Docstrings**: Add docstrings to public functions and classes

## Submitting Changes

### Creating a Pull Request

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, well-documented code
   - Add tests for new features
   - Update documentation if needed

3. **Run tests and linting**
   ```bash
   black .
   ruff check .
   pytest -v
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: Brief description of your changes"
   ```

   Use conventional commit prefixes:
   - `Add:` for new features
   - `Fix:` for bug fixes
   - `Update:` for changes to existing features
   - `Refactor:` for code refactoring
   - `Docs:` for documentation
   - `Test:` for test-related changes

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request** on GitHub
   - Provide a clear description of your changes
   - Reference any related issues
   - Ensure CI tests pass

## Reporting Issues

Found a bug? Have a feature request?

1. Check if the issue already exists in [GitHub Issues](https://github.com/karimz1/dupster/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Your environment (OS, Python version)

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers and help them get started
- Focus on what's best for the project
- Show empathy towards other contributors

---

**Thank you for contributing to Dupster!** 🎉
