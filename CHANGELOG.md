# Changelog

All notable changes to Dupster will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.7] - 2026-01-08

### Added
- Modern Python packaging with `pyproject.toml` and `setup.py`
- `--version` flag to display current version
- Professional README with badges, comparison table, and use cases
- Separated development dependencies in `requirements-dev.txt`
- Code quality tools: Black and Ruff configurations
- CHANGELOG for tracking releases
- CONTRIBUTING guidelines for contributors
- Comprehensive CI/CD with linting and multi-OS testing (Ubuntu + macOS)
- Automatic GitHub releases on tag push
- GitHub Sponsors badge

### Changed
- Requirements now have version constraints for reproducibility
- Improved Homebrew formula generation with modern Python 3.11
- Enhanced developer documentation in DEV_README.md
- Updated all "we" to "I" (solo project by Karim Zouine)

### Improved
- CI workflow with separate linting job
- Homebrew release workflow creates GitHub releases automatically
- All code formatted with Black

[0.0.7]: https://github.com/karimz1/dupster/releases/tag/v0.0.7
