<div align="center">

# 🧹 Dupster

**Modern Duplicate File Finder with an Interactive TUI**

Fast, safe, and keyboard-driven duplicate detection using SHA-256 content hashing

[![CI](https://github.com/karimz1/dupster/actions/workflows/ci.yml/badge.svg)](https://github.com/karimz1/dupster/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/github/v/release/karimz1/dupster)](https://github.com/karimz1/dupster/releases)
[![Homebrew](https://img.shields.io/badge/Homebrew-tap-orange.svg)](https://github.com/karimz1/homebrew-dupster)
[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-pink.svg)](https://github.com/sponsors/karimz1)

<img src="images/live-demo.gif" alt="Dupster Demo" width="800"/>

[Features](#-features) •
[Installation](#-installation) •
[Quick Start](#-quick-start) •
[Documentation](#-documentation) •
[Contributing](#-contributing)

</div>

---

## 🎯 Overview

Dupster is a **terminal-first** duplicate file finder built for developers, system administrators, and power users who live in the command line. Inspired by Vim's keyboard-driven workflow, it delivers a fast, distraction-free way to find and clean duplicate files.

### Why Dupster?

- **🔐 Safe & Auditable**: Preview exactly what will be deleted before committing
- **⚡ Fast Content Hashing**: SHA-256 chunked hashing for true duplicate detection
- **🗜️ ZIP Archive Support**: Finds duplicates inside ZIP files without extraction
- **⌨️ Keyboard-First**: Vim-inspired shortcuts for maximum efficiency
- **📦 Cross-Platform**: Works on macOS and Linux (Windows support planned)
- **🎨 Beautiful TUI**: Clean, focused interface built with Textual

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Content-Based Detection** | Uses SHA-256 hashing—not filenames or sizes—to find true duplicates |
| **ZIP Archive Scanning** | Detects duplicates inside ZIP files without extracting |
| **Interactive TUI** | Full-screen terminal interface with keyboard shortcuts |
| **Safe Deletion** | Preview deletion plan and potential space reclaim before executing |
| **Bulk Operations** | Keep one per group or bulk delete with confirmation |
| **Open in Viewer** | Launch files in default application directly from TUI |
| **Progress Tracking** | Real-time scanning progress with file counts |
| **Async Scanning** | Non-blocking file system traversal for responsiveness |

## 📋 System Requirements

- **Python**: 3.9.6 or newer
- **OS**: macOS, Linux (Windows support coming soon)
- **Terminal**: Any modern terminal with Unicode support

## 📦 Installation

### Homebrew (Recommended for macOS/Linux)

```bash
brew tap karimz1/dupster
brew install karimz1/dupster/dupster-cli
```

### pip (From Source)

```bash
pip install git+https://github.com/karimz1/dupster.git
```

### Development Installation

```bash
git clone https://github.com/karimz1/dupster.git
cd dupster
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## 🚀 Quick Start

### Basic Usage

Scan a directory for duplicates:

```bash
dupster /path/to/folder
```

Scan current directory:

```bash
dupster .
```

Check version:

```bash
dupster --version
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `s` | Start scan |
| `o` | Open selected file in default viewer |
| `i` | Keep one file in group (delete others) |
| `d` | Delete all files in group (with preview) |
| `h`/`l` | Focus left/right panel |
| `m` | Maximize focused panel |
| `q` | Quit application |
| `y`/`Enter` | Confirm action in modal |
| `q`/`Esc` | Cancel modal |

### Example Workflow

1. **Launch Dupster** in a cluttered directory:
   ```bash
   dupster ~/Downloads
   ```

2. **Press `s`** to start scanning

3. **Navigate** through duplicate groups using arrow keys

4. **Press `o`** to preview files in your default viewer

5. **Press `i`** to keep one file and delete the rest in that group

6. **Review** the deletion plan showing space you'll reclaim

7. **Press `y`** to confirm and clean up duplicates

## 🎓 Use Cases

### For Photographers
Clean up duplicate photos from multiple imports:
```bash
dupster ~/Pictures/PhotoLibrary
```

### For Developers
Find duplicate dependencies, assets, or build artifacts:
```bash
dupster ~/Projects
```

### For System Administrators
Audit backup directories for redundant files:
```bash
dupster /backups
```

### For Media Libraries
Identify duplicate music, videos, or documents:
```bash
dupster ~/Music ~/Videos ~/Documents
```

## 📊 Comparison

| Feature | Dupster | fdupes | rdfind | duff |
|---------|---------|--------|--------|------|
| Interactive TUI | ✅ | ❌ | ❌ | ❌ |
| ZIP Support | ✅ | ❌ | ❌ | ❌ |
| Keyboard-First | ✅ | ❌ | ❌ | ❌ |
| Safe Preview | ✅ | Limited | Limited | ❌ |
| Async Scanning | ✅ | ❌ | ❌ | ❌ |
| SHA-256 | ✅ | MD5/SHA | SHA-1/256 | SHA-1 |

## 📚 Documentation

- **[Developer Guide](DEV_README.md)**: Architecture, testing, and development workflow
- **[Contributing Guidelines](CONTRIBUTING.md)**: How to contribute to Dupster
- **[Changelog](CHANGELOG.md)**: Release history and version notes

## 🧪 Testing

Run the test suite:

```bash
pytest -v
```

Generate test data for manual testing:

```bash
python tools/generate_dupes.py
dupster temp/
```

See the [Developer Guide](DEV_README.md) for more testing information.

## 🤝 Contributing

I welcome contributions! Please see the [Contributing Guidelines](CONTRIBUTING.md) for:

- Setting up your development environment
- Code style and testing requirements
- Pull request process
- Architecture guidelines

Quick contribution setup:

```bash
git clone https://github.com/karimz1/dupster.git
cd dupster
pip install -r requirements.txt -r requirements-dev.txt
pytest -v  # Verify tests pass
```

## 📄 License

Dupster is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.

## 👨‍💻 Author

**Karim Zouine**

- GitHub: [@karimz1](https://github.com/karimz1)
- Project: [github.com/karimz1/dupster](https://github.com/karimz1/dupster)

---

<div align="center">

**[⬆ Back to Top](#-dupster)**

Made with ❤️ by developers who love clean code and clean drives

</div>
