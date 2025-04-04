#!/bin/bash
# Script to run Little Dorrit Editor evaluation on existing predictions

# Set environment variables
API_KEY="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"
MODEL_NAME="gpt-4o"
BASE_OUTPUT_DIR="predictions"

# Get current date in YYYYMMDD format
DATE_STAMP=$(date +"%Y%m%d")
RUN_ID="01"  # Can be incremented for multiple runs on the same day

# Set up directory structure
PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_NAME}"
EVAL_PREDICTIONS_DIR="${PREDICTIONS_DIR}/eval"
RESULTS_DIR="${PREDICTIONS_DIR}/results"

# Ensure the results directory exists
mkdir -p "$RESULTS_DIR"

# Evaluate predictions
echo "Evaluating predictions..."

# These arrays are no longer needed as reporting is handled by report_evaluation.sh

# Process only evaluation data (since sample data is used for examples)
if [ -d "data/eval" ] && [ "$(ls -A data/eval/*.json 2>/dev/null)" ]; then
    for json_file in data/eval/*.json; do
        # Extract the base filename without extension
        base_name=$(basename "$json_file" .json)
        
        # Find the most recent prediction file for this base name
        prediction_file=$(ls -t "${EVAL_PREDICTIONS_DIR}/${base_name}_"*"_prediction.json" 2>/dev/null | head -n 1)
        
        # Check if prediction file exists
        if [ -n "$prediction_file" ] && [ -f "$prediction_file" ]; then
            echo "Evaluating $prediction_file against $json_file"
            
            # Extract filename part for results
            pred_filename=$(basename "$prediction_file")
            results_filename="${pred_filename/_prediction/_results}"
            results_path="${RESULTS_DIR}/${results_filename}"
            
            # Run evaluation with correct command structure
            python scripts/evaluate.py run \
                --model-name "$MODEL_NAME" \
                --api-key "$API_KEY" \
                --output "$results_path" \
                "$prediction_file" \
                "$json_file"
            
            # We don't need to calculate metrics here anymore
            # They will be calculated by the report script
        else
            echo "Warning: No prediction file found for $base_name"
        fi
    done
fi

# Use the report script to show detailed results
echo -e "\nGenerating evaluation report..."
bash scripts/report_evaluation.sh "$MODEL_NAME" "$BASE_OUTPUT_DIR"

echo -e "\nEvaluation complete."