# Evaluation Data

This directory contains private evaluation data used for benchmarking models.

## Important Note

The contents of this directory are excluded from Git via the `.gitignore` file
to keep the evaluation data private. This helps maintain the integrity of the
benchmark by preventing models from being trained directly on the evaluation
data.

## Expected Structure

Place evaluation data files here using the same format as the public sample data,
with numbered pairs of image and JSON annotation files:

```
eval/
├── 101.png
├── 101.json
├── 102.png
├── 102.json
⋮
```

## Accessing Evaluation Data

For legitimate evaluation purposes, please contact the project maintainers to
request access to the evaluation dataset.