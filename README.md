# Dupster — Fast Duplicate File Finder (TUI)
A TUI is a full‑screen terminal interface (keyboard‑first).
A modern, open‑source duplicate file finder with a fast, keyboard‑first terminal UI. Uses SHA‑256 content hashing (chunked) to detect true duplicates across folders — even inside ZIP archives. Cross‑platform on macOS and Linux.

## Tool Demo using iTerm2 on macOS
Dupster is built for people who live in the terminal. Inspired by Vim’s speed and ergonomics, it delivers a keyboard‑first, distraction‑free way to find and clean duplicate files — perfect for quick audits over SSH or local housekeeping. It’s free, open source, and designed to feel fast and enjoyable.

<img src="images/live-demo.gif" alt="Live Demo"/>

### 🐍 Requirements
- Python **3.9.6 or newer**
- macOS and Linux supported. Windows likely works but is not yet tested. Windows support is planned.


## Install using Homebrew (Mac and Linux)

tap and install Dupster:

```bash
brew tap karimz1/dupster
brew install karimz1/dupster/dupster-cli
```

## 🚀 Quick Start

Run Dupster in any folder to find duplicates:

```bash
dupster .
```

You’ll get an interactive TUI where you can:

- Preview and open files in your default viewer
- Delete duplicates safely (keep one per group, or bulk with preview)
- See potential space reclaim before deleting

## 🧑‍💻 Run from Source

Clone the repo and run locally:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python dupster.py /path/to/folder
```

Keyboard shortcuts: `s` scan · `o` open · `i` keep one · `d` delete all (preview) · `h/l` focus · `m` maximize · `q` quit
Modal: `y`/Enter confirm · `q`/Esc cancel

## ✅ Why It’s Useful

- Finds true duplicates by content, not by filename or size
- Cleans scattered backups and media libraries with confidence
- Gives a clear reclaim estimate and a safe, auditable delete plan

## ✅ Tests

Quick run:

```bash
pytest -q
```

For details on test coverage and structure, see the Developer Guide.

## 🧪 Generate Sample Files

Create a local dataset under `temp/` for interactive testing:

```bash
python tools/generate_dupes.py  # creates temp/dupster_dataset-<timestamp>
# then run Dupster against it
python dupster.py temp/
```

The generator creates duplicate groups, optional ZIP‑embedded duplicates, unique files, and same‑filename/different‑content pairs.

## 📚 Developer Guide

Read the full guide: [DEV_README.md](DEV_README.md) — architecture, tests, CI, and release workflow.


## **📦 About**

- **Author:** [Karim Zouine](https://github.com/karimz1)
- **License:** Apache 2.0
- **Source:** [github.com/karimz1/dupster](https://github.com/karimz1/dupster)


## ❤️ Support Development


Dupster helped you out? Buy me a coffee, I’ll be smiling all day. 🥳

[![Donate with PayPal](https://camo.githubusercontent.com/c39e7a85a94673509c569f43275e7aaf6e39b66f1abbeb82db115333ec20478d/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f446f6e6174652d50617950616c2d626c75653f6c6f676f3d70617970616c)](https://paypal.me/KarimZouine972)

*(Completely optional, always appreciated.)*
