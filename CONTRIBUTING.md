# Contributing to Dupster

First off, thanks for even looking at this file!

Dupster is a personal project I started because I wanted a better way to handle duplicates over SSH. I’m definitely not an expert in high-performance file scanning, so if you see something that could be done better, I’d love to improve it with you.

## How you can help

Since the main goal is to move this from a "fun project" to something that is actually fast, here are some things I’m currently thinking about:

- **Speed:** Adding file-size pre-filtering (so we don't hash unique files).
- **Parallelism:** Making the hashing happen on multiple cores.
- **UI/UX:** Tweaks to the Textual interface to make it even smoother.
- **Bug Fixes:** Especially if you're testing on different Linux distros or macOS.

## Simple Workflow

1. **Fork & Clone:** Grab the code and set it up locally.
2. **Play around:** Use `python tools/generate_dupes.py` to create a safe testing environment so you don't accidentally delete your own files while coding.
3. **Run Tests:** I use `pytest` to make sure I haven't broken the core logic.
4. **Open a PR:** Don't worry about making it perfect. Just describe what you changed and why.

## Philosophy

I want to keep this tool **simple** and **visual**. If you have a huge new feature idea, maybe open an Issue first just so we can chat about it!

If you contribute, please add your name to the **Authors** section in the PR. I’d be happy to have you as a co-author on the project.

**Thanks for helping me make this little tool better!**
