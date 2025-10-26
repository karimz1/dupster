# Dupster — Developer Guide

This guide covers the code structure, local setup, tests, CI, and the release workflow.

## Architecture

Clean architecture with clear boundaries:

- Domain: value objects and core entities
  - `src/dupster/domain/models.py`
- Application: use cases
  - `src/dupster/application/scanner.py` (async duplicate scan)
  - `src/dupster/application/planner.py` (keep-one and bulk-delete plans)
- Infrastructure: OS and hashing
  - `src/dupster/infrastructure/filesystem.py`
  - `src/dupster/infrastructure/hashing.py`
- UI: end-user interfaces
  - `src/dupster/ui/cli.py` (Typer entrypoint)
  - `src/dupster/ui/tui/app.py` (Textual TUI)
- Utilities
  - `src/dupster/utils/formatting.py`

Principles: SRP, small functions, testable application layer, UI is thin orchestration.

## Local Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run TUI
python dupster.py /path/to/folder
```

## Tests

Run tests:

```bash
pytest -q
```

Highlights:

- Hashing: file and ZIP content hashing and error paths
- Scanner: async filesystem walk, exact grouping by SHA-256
- Planner: keep-one and bulk-delete plan, ordering and reclaim estimation
- Filesystem utilities: recursive listing and safe size/mtime
- TUI smoke tests: headless launch, modal open/close with Textual’s test harness

Test dataset generator (used in tests and for manual demo):

- `tools/generate_dupes.py` creates a realistic tree under `temp/`


## Scripts

- `tools/generate_dupes.py` — Create duplicate/unique datasets for demo or manual QA

## Contributing

- Keep functions small and focused
- Avoid incidental complexity; prefer explicit, testable code paths
- Follow the existing folder structure and naming

Thanks!

Author: Karim Zouine

