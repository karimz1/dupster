# dupster
A modern, colorful CLI tool to find, preview, and clean up duplicate files using smart SHA-256 content hashing — even inside ZIP archives.

### 🐍 Requirements
- Python **3.9.6 or newer**
- Works on macOS, Linux


## Install using Homebrew (Mac and Linux)

tap and install Dupster:

```bash
brew tap karimz1/dupster
brew install karimz1/dupster/dupster-cli
```

## **🚀 Usage**

Run Dupster in any folder to find duplicates:

```bash
dupster .
```

You’ll see an interactive interface where you can:

- Preview duplicate files side by side using your default viewer
- Delete duplicates selectively or automatically
- Enjoy a clean, colorful CLI experience 🧹

## **🧑‍💻 Run from Source**

Clone the repo and run locally:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python dupster.py /path/to/folder
```

Keyboard shortcuts: `s` scan, `o` open, `i` keep one, `d` delete all (preview), `h/l` focus, `m` maximize, `q` quit

Modal shortcuts: `y` or `Enter` confirm; `q`/`Esc` cancel

## **✅ Tests**

Run the test suite:

```bash
pytest -q
```

Core logic (hashing, scanning, planning) is covered by unit tests and separated from the UI for easy maintenance.


## **📦 About**

- **Author:** [Karim Zouine](https://github.com/karimz1)
- **License:** Apache 2.0
- **Source:** [github.com/karimz1/dupster](https://github.com/karimz1/dupster)


## ❤️ Support Development


If dupster saves you time, consider buying me a coffee, every donation keeps CI minutes ticking and pays for test data storage.

[![Donate with PayPal](https://camo.githubusercontent.com/c39e7a85a94673509c569f43275e7aaf6e39b66f1abbeb82db115333ec20478d/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f446f6e6174652d50617950616c2d626c75653f6c6f676f3d70617970616c)](https://paypal.me/KarimZouine972)

*(Completely optional, always appreciated.)*
