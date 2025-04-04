#!/bin/bash
# Script to run Little Dorrit Editor prediction generation with GPT-4o

# Set environment variables
API_KEY="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"
MODEL_NAME="gpt-4o"
BASE_OUTPUT_DIR="predictions"
SHOTS=2  # Number of examples for few-shot learning
SAMPLE_DATASET="data/hf/sample/little-dorrit-editor"  # Path to sample dataset for examples

# Get current date in YYYYMMDD format
DATE_STAMP=$(date +"%Y%m%d")
RUN_ID="01"  # Can be incremented for multiple runs on the same day

# Create organized output directory structure
PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_NAME}"
EVAL_PREDICTIONS_DIR="${PREDICTIONS_DIR}/eval"

# Ensure the output directories exist
mkdir -p "$EVAL_PREDICTIONS_DIR"

# Prepare the datasets if needed
echo "Preparing datasets..."
python scripts/prepare_datasets.py --clean

# Process only the evaluation files - skip sample files since they're used for examples
if [ -d "data/eval" ] && [ "$(ls -A data/eval/*.png 2>/dev/null)" ]; then
    echo "Generating predictions for evaluation files..."
    for img_file in data/eval/*.png; do
        # Extract the base filename without extension
        base_name=$(basename "$img_file" .png)
        
        # Define the output prediction file
        prediction_file="${EVAL_PREDICTIONS_DIR}/${base_name}_${RUN_ID}_${DATE_STAMP}_prediction.json"
        
        echo "Processing $img_file -> $prediction_file"
        
        # Generate predictions using n-shot learning
        python scripts/evaluate.py generate \
            --model-name "$MODEL_NAME" \
            --api-key "$API_KEY" \
            --shots "$SHOTS" \
            --sample-dataset "$SAMPLE_DATASET" \
            "$img_file" \
            "$prediction_file"
    done
    echo "Prediction generation complete."
    echo "Evaluation predictions stored in: $EVAL_PREDICTIONS_DIR"
else
    echo "No evaluation files found in data/eval. Please ensure evaluation data is available."
fi