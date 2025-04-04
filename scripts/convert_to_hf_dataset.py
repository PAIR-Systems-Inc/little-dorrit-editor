#!/usr/bin/env python3
"""
Conversion script for Little Dorrit Editor benchmark.

This script converts a directory of annotation files and images
to a Hugging Face-compatible dataset.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the little_dorrit_editor package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from little_dorrit_editor.cli import convert_app

if __name__ == "__main__":
    convert_app()