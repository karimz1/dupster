# Changelog

All notable changes to Dupster will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.8] - 2026-09-12

### Added
- Staged duplicate detection: files are grouped by size, then by inode, then by partial hashes, and only survivors get a full SHA-256
- Per-drive read scheduling, with a deep queue on SSD and a single inode-ordered reader on spinning disks
- `--workers`, `--min-size`, `--verify` and `--follow-symlinks` flags
- `--verify` confirms matches with a lockstep byte-for-byte comparison
- In-session hash cache, so the rescan after a delete is close to instant
- Scan summary in the UI showing files seen, bytes read and how much was skipped
- `tools/benchmark.py` for timing the scanner against the old approach
- Differential test suite comparing the pipeline against a brute-force reference
- New Dupster logo for the README and TUI branding
- Textual theme support with Catppuccin Mocha as the default
- Theme picker with debounced live previews across the full UI
- Saved theme preference in `~/.config/dupster/config.json`
- `c` shortcut and command palette action to copy the selected file's full path
- `?` shortcut and command palette action to show or hide the right-side help and keys panel
- Left and right arrow shortcuts for switching panes alongside `h` and `l`
- `g` and `G` shortcuts to jump to the top or bottom of the active list
- Clickable `karimz1/dupster` GitHub footer action

### Changed
- Symlinks are no longer reported as duplicates by default, use `--follow-symlinks` for the old behaviour
- Directory walking uses `os.scandir`, dropping a redundant stat syscall per file
- Duplicate group sizes come from the scan instead of being re-stated on every UI redraw
- Compact rows are now the default for duplicate groups and files
- Header and footer layout is tighter, calmer by default, and more responsive on small terminals
- Delete actions now use clearer group versus all-groups wording
- README is shorter, SEO friendly, and mentions the LinuxLinks feature
- CI and local development now use `uv` with `pyproject.toml` and `uv.lock` instead of duplicate requirements files

### Fixed
- Hardlinked files that were the only members of a size group are no longer missed
- Theme changes now apply to the full TUI background and controls
- Highlight and hover colors now better match the active theme
- Group delete flow now asks what to keep before deleting the other duplicates
- Destructive delete previews now confirm with `y` instead of Enter

## [0.0.7] - 2026-01-08

### Added
- Modern Python packaging with `pyproject.toml` and `setup.py`
- `--version` flag to display current version
- Professional README with badges, comparison table, and use cases
- Separated development dependency metadata for contributors
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

[0.0.8]: https://github.com/karimz1/dupster/releases/tag/v0.0.8
[0.0.7]: https://github.com/karimz1/dupster/releases/tag/v0.0.7
