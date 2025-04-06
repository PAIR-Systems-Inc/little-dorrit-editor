#!/bin/bash
# Script to run Little Dorrit Editor prediction generation
#
# Usage: ./run_prediction.sh [model_id1] [model_id2] ... [--shots N] [--display-name "Name"]
#   model_id: One or more IDs of models from config (default: gpt-4o if none provided)
#   --shots N: Number of shots to use (default: 2)
#   --display-name "Name": Custom display name for the leaderboard (optional)
#
# Examples:
#   ./run_prediction.sh or_gpt_4o_latest                 # Run with a single model
#   ./run_prediction.sh or_gpt_4o_latest or_llama_4_scout # Run with multiple models
#   ./run_prediction.sh or_gpt_4o_latest --shots 3       # Run with 3-shot learning
#
# Available model IDs can be viewed with: config list

# Default values
DEFAULT_MODEL="gpt-4o"
SHOTS=2
DISPLAY_NAME=""
MODELS=()

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --shots)
      SHOTS="$2"
      shift 2
      ;;
    --display-name)
      DISPLAY_NAME="$2"
      shift 2
      ;;
    --*)
      echo "Unknown option: $1"
      exit 1
      ;;
    *)
      # Assume anything else is a model ID
      MODELS+=("$1")
      shift
      ;;
  esac
done

# If no models specified, use default
if [ ${#MODELS[@]} -eq 0 ]; then
  MODELS=("$DEFAULT_MODEL")
fi

# Set environment variables
# No API key needed here - the config module will use the relevant environment variable
BASE_OUTPUT_DIR="predictions"
SAMPLE_DATASET="data/hf/sample/little-dorrit-editor"  # Path to sample dataset for examples
TEMPERATURE=0.0

# Get current date in YYYYMMDD format
DATE_STAMP=$(date +"%Y%m%d")

# Prepare the datasets if needed (do this once before running all models)
echo "Preparing datasets..."
python scripts/prepare_datasets.py --clean

# Function to get highest run ID across all models
function get_highest_run_id() {
    local highest=0
    
    # Look through all model directories for today's files
    for model_dir in "${BASE_OUTPUT_DIR}"/*; do
        if [ -d "$model_dir" ]; then
            local sample_dir="${model_dir}/predictions/sample"
            local eval_dir="${model_dir}/predictions/eval"
            
            for dir in "$sample_dir" "$eval_dir"; do
                if [ -d "$dir" ]; then
                    # Find any prediction files with today's date
                    local existing_files=$(find "$dir" -type f -name "*_${DATE_STAMP}_prediction.json" 2>/dev/null)
                    
                    # Extract run numbers from filenames and find highest
                    for file in $existing_files; do
                        # Extract the run ID part from filename (format: name_XX_date_prediction.json)
                        local filename=$(basename "$file")
                        local run_part=$(echo "$filename" | grep -o -E '_[0-9]+_' | head -1 | tr -d '_')
                        
                        if [[ "$run_part" =~ ^[0-9]+$ ]]; then
                            local run_num=$((10#$run_part)) # Force decimal interpretation
                            if [ $run_num -gt $highest ]; then
                                highest=$run_num
                            fi
                        fi
                    done
                fi
            done
        fi
    done
    
    echo $highest
}

# Process each model in sequence
for MODEL_ID in "${MODELS[@]}"; do
    echo "=========================================================="
    echo "Processing model: $MODEL_ID (${#MODELS[@]} total models in queue)"
    echo "=========================================================="
    
    # Calculate a fresh run ID before each model's processing
    # This allows multiple runs of the same model in a single command
    HIGHEST_RUN=$(get_highest_run_id)
    NEXT_RUN=$((HIGHEST_RUN + 1))
    RUN_ID=$(printf "%02d" $NEXT_RUN)
    echo "Using run ID: $RUN_ID (based on existing runs found across all models)"
    
    # Create organized output directory structure for this model
    PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_ID}"
    PREDICTIONS_OUTPUT_DIR="${PREDICTIONS_DIR}/predictions"
    EVAL_PREDICTIONS_DIR="${PREDICTIONS_OUTPUT_DIR}/eval"
    SAMPLE_PREDICTIONS_DIR="${PREDICTIONS_OUTPUT_DIR}/sample"
    CONFIG_FILE="${PREDICTIONS_DIR}/config.json"
    
    # Ensure the output directories exist
    mkdir -p "$EVAL_PREDICTIONS_DIR"
    mkdir -p "$SAMPLE_PREDICTIONS_DIR"
    
    # Get the model's logical name if no display name is provided
    CURRENT_DISPLAY_NAME="$DISPLAY_NAME"
    if [[ -z "${CURRENT_DISPLAY_NAME}" ]]; then
        # Try to get logical name from config
        LOGICAL_NAME=$(python -c "from little_dorrit_editor.config import get_model; print(get_model('${MODEL_ID}').logical_name)" 2>/dev/null)
        if [[ $? -eq 0 && -n "${LOGICAL_NAME}" ]]; then
            CURRENT_DISPLAY_NAME="${LOGICAL_NAME}"
        else
            CURRENT_DISPLAY_NAME="${MODEL_ID}"
        fi
    fi
    
    # Create a config.json file for the experiment
    echo "Creating experiment configuration..."
    cat > "$CONFIG_FILE" << EOL
{
  "model_id": "${MODEL_ID}",
  "display_name": "${CURRENT_DISPLAY_NAME}",
  "shots": ${SHOTS},
  "temperature": ${TEMPERATURE},
  "date": "$(date +"%Y-%m-%d")",
  "notes": "Benchmark run with ${SHOTS}-shot learning"
}
EOL
    echo "Experiment configuration saved to $CONFIG_FILE"
    
    # Generate predictions for sample files (for documentation purposes)
    if [ -d "data/sample" ] && [ "$(ls -A data/sample/*.png 2>/dev/null)" ]; then
        echo "Generating predictions for sample files..."
        for img_file in data/sample/*.png; do
            # Extract the base filename without extension
            base_name=$(basename "$img_file" .png)
    
            # Define the output prediction file
            prediction_file="${SAMPLE_PREDICTIONS_DIR}/${base_name}_${RUN_ID}_${DATE_STAMP}_prediction.json"
    
            echo "Processing $img_file -> $prediction_file"
    
            # Generate predictions using n-shot learning with uv
            # Directly call the CLI module
            uv run python -m little_dorrit_editor.cli predict run \
                --model-id "$MODEL_ID" \
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
    
            # Generate predictions using n-shot learning with uv
            # Directly call the CLI module
            uv run python -m little_dorrit_editor.cli predict run \
                --model-id "$MODEL_ID" \
                --shots "$SHOTS" \
                --sample-dataset "$SAMPLE_DATASET" \
                "$img_file" \
                "$prediction_file"
        done
        echo "Prediction generation complete for $MODEL_ID."
        echo "Evaluation predictions stored in: $EVAL_PREDICTIONS_DIR"
    else
        echo "No evaluation files found in data/eval. Please ensure evaluation data is available."
    fi
    
    echo "Finished processing model: $MODEL_ID"
    echo "Use './scripts/run_evaluation.sh ${MODEL_ID}' to evaluate the predictions."
done

echo "=========================================================="
echo "All predictions generated successfully for ${#MODELS[@]} models."
echo
echo "To evaluate all models, run:"
for MODEL_ID in "${MODELS[@]}"; do
    echo "  ./scripts/run_evaluation.sh ${MODEL_ID}"
done