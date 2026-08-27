# Contributing to Dupster

First off, thanks for even looking at this file!

Dupster is a personal project I started because I wanted a better way to handle duplicates over SSH. I’m definitely not an expert in high-performance file scanning, so if you see something that could be done better, I’d love to improve it with you.

## How you can help

The staged scanner (size, then inode, then partial hashes, then SHA-256) and per-drive read
scheduling are in place now. Things I’m still thinking about:

- **Hardlink awareness:** Marking groups that are hardlinks, since deleting those frees nothing.
- **A hash cache on disk:** Right now hashes only survive for the lifetime of the session.
- **Physical block ordering:** Reading in `FIEMAP` order on Linux rather than inode order.
- **UI/UX:** Tweaks to the Textual interface to make it even smoother.
- **Bug Fixes:** Especially if you're testing on different Linux distros, Windows, or spinning disks.

If you change the scanner, note that `tests/test_scanner_staged.py` compares it against a
brute-force reference over randomly generated adversarial trees. That is the test that matters.
`tools/benchmark.py` will tell you whether a change actually helped.

## Simple Workflow

1. **Fork & Clone:** Grab the code and set it up locally.
2. **Play around:** Use `python tools/generate_dupes.py` to create a safe testing environment so you don't accidentally delete your own files while coding.
3. **Run Tests:** I use `pytest` to make sure I haven't broken the core logic.
4. **Open a PR:** Don't worry about making it perfect. Just describe what you changed and why.

## Philosophy

I want to keep this tool **simple** and **visual**. If you have a huge new feature idea, maybe open an Issue first just so we can chat about it!

If you contribute, please add your name to the **Authors** section in the PR. I’d be happy to have you as a co-author on the project.

**Thanks for helping me make this little tool better!**
