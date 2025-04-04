#!/usr/bin/env python3
"""
Evaluation script for Little Dorrit Editor benchmark.

This script compares predicted edits against ground truth annotations
and calculates precision, recall, and F1 score using an LLM judge.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the little_dorrit_editor package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from little_dorrit_editor.cli import evaluate_app

if __name__ == "__main__":
    evaluate_app()