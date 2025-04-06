#!/bin/bash
# Script to run Little Dorrit Editor evaluation on existing predictions
#
# Usage: ./run_evaluation.sh [model_id] [display_name] [judge_model_id]
#   model_id: ID of the model (default: gpt-4o)
#   display_name: Custom display name for the leaderboard (only used if creating new config)
#   judge_model_id: OPTIONAL - Model ID to use for evaluation judging (default: gpt-4.5-preview)
#                WARNING: Changing this is NOT recommended as it affects benchmark consistency
#
# Available model IDs can be viewed with: config list

# Get command line arguments or use defaults
MODEL_ID=${1:-"gpt-4o"}    # Default model is gpt-4o
DISPLAY_NAME=${2:-""}      # Optional display name (only used if creating new config)
CUSTOM_JUDGE_MODEL=${3:-""}  # Optional judge model override

# Use fixed judge model for consistent evaluation
LLM_JUDGE_MODEL="gpt-4.5-preview"  

# Show warning if custom judge model is provided
if [[ -n "$CUSTOM_JUDGE_MODEL" ]]; then
    echo "⚠️ WARNING: Overriding the default judge model is NOT recommended ⚠️"
    echo "It affects benchmark consistency and makes results incomparable with others."
    echo "Default judge: $LLM_JUDGE_MODEL"
    echo "Custom judge: $CUSTOM_JUDGE_MODEL"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " confirm
    if [[ "$confirm" == [yY] || "$confirm" == [yY][eE][sS] ]]; then
        LLM_JUDGE_MODEL="$CUSTOM_JUDGE_MODEL"
        echo "Using custom judge model: $LLM_JUDGE_MODEL"
    else
        echo "Using default judge model: $LLM_JUDGE_MODEL"
    fi
    echo ""
fi

# Set environment variables
# No API key needed here - the config module will use the relevant environment variable
BASE_OUTPUT_DIR="predictions"

# Set up directory structure using new format
PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_ID}"
CONFIG_FILE="${PREDICTIONS_DIR}/config.json"
PREDICTIONS_OUTPUT_DIR="${PREDICTIONS_DIR}/predictions"
EVAL_PREDICTIONS_DIR="${PREDICTIONS_OUTPUT_DIR}/eval"
RESULTS_DIR="${PREDICTIONS_DIR}/results"
EVAL_RESULTS_DIR="${RESULTS_DIR}/eval"

# Verify the model directory exists
if [ ! -d "$PREDICTIONS_DIR" ]; then
    echo "Error: Model directory not found: $PREDICTIONS_DIR"
    echo "Run './scripts/run_prediction.sh ${MODEL_ID}' first to generate predictions."
    exit 1
fi

# Verify config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Warning: Config file not found: $CONFIG_FILE"
    echo "Creating a default config file with 2-shot learning..."
    
    # Get the model's logical name if no display name is provided
    if [[ -z "${DISPLAY_NAME}" ]]; then
        # Try to get logical name from config
        LOGICAL_NAME=$(python -c "from little_dorrit_editor.config import get_model; print(get_model('${MODEL_ID}').logical_name)" 2>/dev/null)
        if [[ $? -eq 0 && -n "${LOGICAL_NAME}" ]]; then
            DISPLAY_NAME="${LOGICAL_NAME}"
        else
            DISPLAY_NAME="${MODEL_ID}"
        fi
    fi

    # Create a default config.json file
    cat > "$CONFIG_FILE" << EOL
{
  "model_id": "${MODEL_ID}",
  "display_name": "${DISPLAY_NAME}",
  "shots": 2,
  "temperature": 0.0,
  "date": "$(date +"%Y-%m-%d")",
  "notes": "Benchmark run with 2-shot learning (default)"
}
EOL
    echo "Default configuration saved to $CONFIG_FILE"
fi

# Display experiment configuration
echo "Experiment configuration:"
cat "$CONFIG_FILE"
echo ""
echo "Using judge model: $LLM_JUDGE_MODEL"
echo ""

# Ensure the results directories exist
mkdir -p "$EVAL_RESULTS_DIR"

# Evaluate predictions
echo "Evaluating predictions..."

# Process only evaluation data
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
            results_path="${EVAL_RESULTS_DIR}/${results_filename}"
            
            # Run evaluation with correct command structure and fixed judge model
            # Directly call the CLI module
            uv run python -m little_dorrit_editor.cli evaluate run \
                --model-name "$MODEL_ID" \
                --llm-model "$LLM_JUDGE_MODEL" \
                --output "$results_path" \
                "$prediction_file" \
                "$json_file"
        else
            echo "Warning: No prediction file found for $base_name"
        fi
    done
fi

# Use the report script to show detailed results
echo -e "\nGenerating evaluation report..."
bash scripts/report_evaluation.sh "$MODEL_ID" "$BASE_OUTPUT_DIR"

echo -e "\nEvaluation complete. Results stored in $EVAL_RESULTS_DIR"
echo "To update the leaderboard site, run: python scripts/build_site_results.py"