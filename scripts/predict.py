#!/usr/bin/env python3
"""
Prediction script for Little Dorrit Editor benchmark.

This script generates editorial correction predictions from images
using multimodal language models.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import the little_dorrit_editor package
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from little_dorrit_editor.cli import predict_app

if __name__ == "__main__":
    predict_app()