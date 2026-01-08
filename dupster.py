#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dupster.ui.cli import cli

if __name__ == "__main__":
    cli()
