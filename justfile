# Little Dorrit Editor justfile
# For use with the 'just' command runner

# Default recipe to run when 'just' is called without arguments
default:
    @just --list

# Create a virtual environment and install dependencies
setup:
    uv venv
    uv pip install -e ".[dev]"

# Format code with black and ruff
format:
    black little_dorrit_editor tests scripts
    ruff check --fix little_dorrit_editor tests scripts

# Run type checking
typecheck:
    mypy little_dorrit_editor tests scripts

# Run tests
test:
    pytest tests/

# Run all checks (format, type check, test)
check: format typecheck test

# Evaluate a prediction against ground truth
evaluate MODEL_NAME PREDICTION GROUND_TRUTH:
    python scripts/evaluate.py --model-name "{{MODEL_NAME}}" "{{PREDICTION}}" "{{GROUND_TRUTH}}"

# Convert a directory of data to a Hugging Face dataset
convert INPUT_DIR OUTPUT_DIR:
    python scripts/convert_to_hf_dataset.py "{{INPUT_DIR}}" "{{OUTPUT_DIR}}"

# Convert sample data to a Hugging Face dataset
convert-sample:
    python scripts/convert_to_hf_dataset.py "data/sample" "hf_dataset/sample"

# Convert evaluation data to a Hugging Face dataset
convert-eval:
    python scripts/convert_to_hf_dataset.py "data/eval" "hf_dataset/eval"

# Update the leaderboard with a new evaluation result
update-leaderboard MODEL_NAME PREDICTION GROUND_TRUTH:
    python scripts/evaluate.py --model-name "{{MODEL_NAME}}" --update-leaderboard "{{PREDICTION}}" "{{GROUND_TRUTH}}"

# Generate a sample prediction file from ground truth (for testing)
generate-pred PAGE_NUM DATA_DIR="data/sample":
    @echo "Generating sample prediction for page {{PAGE_NUM}} from {{DATA_DIR}}"
    @python -c "import json; from pathlib import Path; gt = json.loads(Path('{{DATA_DIR}}/{{PAGE_NUM}}.json').read_text()); pred = gt.copy(); pred['edits'] = [e.copy() for e in gt['edits']]; pred['edits'][0]['edited_text'] = 'sample prediction'; Path('{{DATA_DIR}}/{{PAGE_NUM}}_prediction.json').write_text(json.dumps(pred, indent=2))"
    @echo "Sample prediction saved to {{DATA_DIR}}/{{PAGE_NUM}}_prediction.json"