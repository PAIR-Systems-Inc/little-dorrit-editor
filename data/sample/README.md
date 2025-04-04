# Sample Data

This directory contains public sample data that demonstrates the format and
structure of the Little Dorrit Editor dataset. These samples are included in the
repository to help users understand the benchmark task.

## Contents

The sample data consists of:
- Image files (PNG): Scanned pages with handwritten editorial marks
- Annotation files (JSON): Corresponding ground truth annotations describing the edits

## Example Usage

These samples can be used to:
1. Develop and test model implementations
2. Understand the annotation format
3. Experiment with the evaluation script

## Sample Data vs. Evaluation Data

Note that this is separate from the private evaluation data used for official
benchmark scoring. The private evaluation data follows the same format but is
stored in the `eval/` directory and is excluded from the Git repository.

## Expanding the Samples

Feel free to add more samples to this directory for educational purposes. If you
create additional samples, please ensure they follow the same format and naming
convention (numbered pairs of image and JSON files).
