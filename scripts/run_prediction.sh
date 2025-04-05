#!/bin/bash
# Script to run Little Dorrit Editor prediction generation
#
# Usage: ./run_prediction.sh [model_name] [shots] [display_name]
#   model_name: Name of the model (default: gpt-4o)
#   shots: Number of shots to use (default: 2)
#   display_name: Custom display name for the leaderboard (optional)

# Get command line arguments or use defaults
MODEL_NAME=${1:-"gpt-4o"}  # Default model is gpt-4o
SHOTS=${2:-2}              # Default to 2-shot learning
DISPLAY_NAME=${3:-""}      # Optional display name

# Set environment variables
API_KEY="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"
BASE_OUTPUT_DIR="predictions"
SAMPLE_DATASET="data/hf/sample/little-dorrit-editor"  # Path to sample dataset for examples
TEMPERATURE=0.0

# Get current date in YYYYMMDD format
DATE_STAMP=$(date +"%Y%m%d")
RUN_ID="01"  # Can be incremented for multiple runs on the same day

# Create organized output directory structure
PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_NAME}"
PREDICTIONS_OUTPUT_DIR="${PREDICTIONS_DIR}/predictions"
EVAL_PREDICTIONS_DIR="${PREDICTIONS_OUTPUT_DIR}/eval"
SAMPLE_PREDICTIONS_DIR="${PREDICTIONS_OUTPUT_DIR}/sample"
CONFIG_FILE="${PREDICTIONS_DIR}/config.json"

# Ensure the output directories exist
mkdir -p "$EVAL_PREDICTIONS_DIR"
mkdir -p "$SAMPLE_PREDICTIONS_DIR"

# Create a config.json file for the experiment
echo "Creating experiment configuration..."

# Use provided display name or default to model name
if [[ -z "${DISPLAY_NAME}" ]]; then
    DISPLAY_NAME="${MODEL_NAME}"
fi

cat > "$CONFIG_FILE" << EOL
{
  "model_name": "${MODEL_NAME}",
  "display_name": "${DISPLAY_NAME}",
  "shots": ${SHOTS},
  "temperature": ${TEMPERATURE},
  "date": "$(date +"%Y-%m-%d")",
  "notes": "Benchmark run with ${SHOTS}-shot learning"
}
EOL
echo "Experiment configuration saved to $CONFIG_FILE"

# Prepare the datasets if needed
echo "Preparing datasets..."
python scripts/prepare_datasets.py --clean

# Generate predictions for sample files (for documentation purposes)
if [ -d "data/sample" ] && [ "$(ls -A data/sample/*.png 2>/dev/null)" ]; then
    echo "Generating predictions for sample files..."
    for img_file in data/sample/*.png; do
        # Extract the base filename without extension
        base_name=$(basename "$img_file" .png)
        
        # Define the output prediction file
        prediction_file="${SAMPLE_PREDICTIONS_DIR}/${base_name}_${RUN_ID}_${DATE_STAMP}_prediction.json"
        
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
fi

# Process the evaluation files
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

echo "All predictions generated successfully."
echo "Run './scripts/run_evaluation.sh ${MODEL_NAME}' to evaluate the predictions."