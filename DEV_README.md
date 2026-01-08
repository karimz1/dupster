# Dupster — Developer Guide

This guide covers the codebase architecture, local development setup, testing strategy, CI/CD, and the release workflow.

## Quick Setup

Get started with development in one command:

```bash
git clone https://github.com/karimz1/dupster.git && cd dupster && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt && pytest -q
```

Or step-by-step:

```bash
# Clone repository
git clone https://github.com/karimz1/dupster.git
cd dupster

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify setup
pytest -q
```

## Architecture

Dupster follows **Clean Architecture** principles with clear separation of concerns:

```
src/dupster/
├── domain/              # Core business logic (framework-independent)
│   └── models.py        # DuplicateGroup entity
├── application/         # Use cases and business rules
│   ├── scanner.py       # Async duplicate scanning
│   └── planner.py       # Keep-one and bulk-delete planning
├── infrastructure/      # External dependencies
│   ├── filesystem.py    # File system operations
│   └── hashing.py       # SHA-256 content hashing (chunked)
├── ui/                  # User interfaces
│   ├── cli.py          # CLI entry point (Typer)
│   └── tui/            # Terminal UI (Textual)
│       └── app.py      # Main TUI application
└── utils/              # Shared utilities
    └── formatting.py   # Output formatting helpers
```

### Design Principles

- **Single Responsibility**: Each module has one clear purpose
- **Dependency Inversion**: Core logic doesn't depend on UI or infrastructure
- **Testability**: Application layer can be tested without UI
- **Small Functions**: Focused, readable, and maintainable code
- **Type Safety**: Type hints throughout for better IDE support

## Development Workflow

### Running Dupster Locally

From source:
```bash
python dupster.py /path/to/folder
```

As installed package (editable mode):
```bash
pip install -e .
dupster /path/to/folder
```

### Code Quality Tools

#### Black (Code Formatting)

Format all code:
```bash
black .
```

Check formatting without changes:
```bash
black --check .
```

#### Ruff (Linting)

Lint code:
```bash
ruff check .
```

Auto-fix issues:
```bash
ruff check --fix .
```

Configuration is in `pyproject.toml`.

## Testing

### Running Tests

Full test suite:
```bash
pytest -v
```

Specific test file:
```bash
pytest tests/test_scanner.py -v
```

Specific test function:
```bash
pytest tests/test_scanner.py::test_find_duplicates_basic -v
```

With coverage report:
```bash
pytest --cov=src/dupster --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Test Organization

| Test File | Coverage |
|-----------|----------|
| `test_cli_help.py` | CLI help output validation |
| `test_dataset_scanner.py` | Dataset scanning integration |
| `test_domain.py` | Domain models (DuplicateGroup) |
| `test_filesystem.py` | File system operations |
| `test_formatting.py` | Output formatting utilities |
| `test_hashing.py` | SHA-256 hashing (files and ZIPs) |
| `test_hashing_errors.py` | Hash error handling |
| `test_planner.py` | Deletion planning logic |
| `test_planner_dataset.py` | Planner with generated datasets |
| `test_planner_ordering.py` | File ordering in plans |
| `test_scanner.py` | Async scanner core functionality |
| `test_scanner_progress.py` | Progress callback testing |
| `test_scanner_zip.py` | ZIP archive scanning |
| `test_tui_smoke.py` | TUI smoke tests (Textual harness) |

### Test Data Generator

Generate realistic test datasets:

```bash
python tools/generate_dupes.py
```

This creates `temp/dupster_dataset-<timestamp>/` with:
- Duplicate groups (same content, different names)
- ZIP-embedded duplicates
- Unique files
- Same-filename/different-content pairs

Then test against it:
```bash
python dupster.py temp/
```

## CI/CD

### Continuous Integration

The CI pipeline (`.github/workflows/ci.yml`) runs on every push:

- **Multi-version testing**: Python 3.9, 3.10, 3.11, 3.12
- **Multi-OS testing**: Ubuntu and macOS
- **Linting**: Ruff checks for code quality
- **Formatting**: Black verification
- **Tests**: Full pytest suite
- **Coverage**: Code coverage reporting

### Release Workflow

The release workflow (`.github/workflows/homebrew-release.yml`) triggers on version tags:

1. Push a version tag:
   ```bash
   git tag v0.0.7
   git push origin v0.0.7
   ```

2. CI automatically:
   - Runs full test suite
   - Generates Homebrew formula
   - Computes SHA-256 of source tarball
   - Generates Python resource blocks via `homebrew-pypi-poet`
   - Commits formula to `karimz1/homebrew-dupster` tap

3. Users can install the new version:
   ```bash
   brew upgrade dupster-cli
   ```

### Release Checklist

Before tagging a release:

1. ✅ Update version in `pyproject.toml` and `src/dupster/__init__.py`
2. ✅ Update `CHANGELOG.md` with release notes
3. ✅ Run full test suite: `pytest -v`
4. ✅ Test installation: `pip install -e .`
5. ✅ Verify `dupster --version` shows correct version
6. ✅ Commit changes: `git commit -m "Bump version to vX.Y.Z"`
7. ✅ Create and push tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
8. ✅ Monitor GitHub Actions for successful deployment
9. ✅ Test Homebrew installation: `brew upgrade dupster-cli`

## Project Structure

```
dupster/
├── .github/
│   └── workflows/          # CI/CD pipelines
│       ├── ci.yml          # Main CI (tests, linting)
│       └── homebrew-release.yml  # Homebrew formula automation
├── src/dupster/            # Main source code
├── tests/                  # Test suite
├── tools/                  # Development tools
│   └── generate_dupes.py   # Test data generator
├── images/                 # README assets
├── temp/                   # Generated test data (gitignored)
├── dupster.py             # Entry point for source runs
├── pyproject.toml         # Package configuration
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── README.md              # User documentation
├── DEV_README.md          # This file
├── CONTRIBUTING.md        # Contribution guidelines
├── CHANGELOG.md           # Release history
└── LICENSE                # Apache 2.0 license
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development environment setup
- Code style guidelines
- Testing requirements
- Pull request process

### Quick Contribution Flow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/awesome-feature`
3. Make changes and add tests
4. Run linting and tests: `black . && ruff check . && pytest -v`
5. Commit: `git commit -m "Add: awesome feature"`
6. Push: `git push origin feature/awesome-feature`
7. Open a Pull Request

## Troubleshooting

### Textual TUI Issues

If the TUI doesn't render correctly:
- Ensure your terminal supports Unicode
- Try a different terminal emulator (iTerm2, Alacritty, etc.)
- Check `TERM` environment variable: `echo $TERM`

### Async Test Failures

If async tests fail:
- Install `pytest-asyncio`: `pip install pytest-asyncio`
- Verify `pytest.ini` has `asyncio_mode = "auto"`

### Import Errors

If imports fail after changes:
- Reinstall in editable mode: `pip install -e .`
- Clear `__pycache__`: `find . -type d -name __pycache__ -exec rm -rf {} +`

## Performance Optimization Tips

- **Large Directories**: The scanner uses async I/O for responsiveness
- **Chunked Hashing**: Files are hashed in 8KB chunks to avoid memory issues
- **Progress Callbacks**: Non-blocking progress updates during scanning

---

**Questions?** Open an issue or discussion on GitHub!

**Author**: Karim Zouine • [GitHub](https://github.com/karimz1)


