#!/bin/bash
# Script to run Little Dorrit Editor prediction generation
#
# This script runs prediction generation for the Little Dorrit Editor benchmark
# using specified models. It handles processing of evaluation and sample data,
# configuration management, and file/directory organization.
#
# Key Features:
# - Supports multiple models in a single command
# - File-specific run IDs for better organization
# - Question ID filtering for targeted prediction runs
# - Conditional dataset preparation
#
# Usage: ./run_prediction.sh [model_id1] [model_id2] ... [options]
#   model_id: One or more IDs of models from config (default: gpt-4o if none provided)
#
# Options:
#   --shots N: Number of shots to use (default: 2)
#   --display-name "Name": Custom display name for the leaderboard (optional)
#   --refresh-datasets: Force rebuild of the sample and evaluation datasets
#   --question-ids "id1,id2,...": Only process specific question IDs (comma-separated, no spaces)
#
# File Naming:
#   Prediction files are named as: {question_id}_{run_id}_{date}_prediction.json
#   - question_id: ID of the question (e.g., "003")
#   - run_id: Sequential ID for each run, starting from 01 for each file/model pair
#   - date: Generation date in YYYYMMDD format
#
# Examples:
#   ./run_prediction.sh or_gpt_4o_latest                 # Run with a single model
#   ./run_prediction.sh or_gpt_4o_latest or_llama_4_scout # Run with multiple models
#   ./run_prediction.sh or_gpt_4o_latest --shots 3       # Run with 3-shot learning
#   ./run_prediction.sh or_gpt_4o_latest --refresh-datasets # Force dataset rebuild
#   ./run_prediction.sh or_gpt_4o_latest --question-ids "003,005" # Only process questions 003 and 005
#
# Note: The --question-ids flag is particularly useful when balancing your dataset
# based on the output from check_predictions.py script.
#
# Available model IDs can be viewed with: config list

# Default values
DEFAULT_MODEL="gpt-4o"
SHOTS=2
DISPLAY_NAME=""
MODELS=()
REFRESH_DATASETS=false
QUESTION_IDS=""

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
    --refresh-datasets)
      REFRESH_DATASETS=true
      shift
      ;;
    --question-ids)
      QUESTION_IDS="$2"
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

# Only prepare datasets if they don't exist or if --refresh-datasets flag is provided
if [ ! -d "data/hf/sample" ] || [ ! -d "data/hf/eval" ] || [ "$REFRESH_DATASETS" = "true" ]; then
    if [ "$REFRESH_DATASETS" = "true" ]; then
        echo "Preparing datasets (--refresh-datasets flag provided)..."
    else
        echo "Preparing datasets (missing directories)..."
    fi
    python scripts/prepare_datasets.py --clean
else
    echo "Using existing datasets (use --refresh-datasets to force rebuilding)"
fi

# Function to get highest run ID for a specific file within the current model
function get_highest_run_id_for_file() {
    local file_id="$1"
    local model_dir="$2"
    local highest=0
    
    # Only look in the current model directory
    local sample_dir="${model_dir}/predictions/sample"
    local eval_dir="${model_dir}/predictions/eval"
    
    for dir in "$sample_dir" "$eval_dir"; do
        if [ -d "$dir" ]; then
            # Find any prediction files with today's date and the specific file_id for this model
            local existing_files=$(find "$dir" -type f -name "${file_id}_*_${DATE_STAMP}_prediction.json" 2>/dev/null)
            
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
    
    echo $highest
}

# Process each model in sequence
for MODEL_ID in "${MODELS[@]}"; do
    echo "=========================================================="
    echo "Processing model: $MODEL_ID (${#MODELS[@]} total models in queue)"
    echo "=========================================================="
    
    # No need for a global run ID anymore - each file will get its own run ID
    echo "Using file-specific run IDs for this model"
    
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
        # Use our standalone script to get the logical name from config
        # This avoids capturing any warning messages that might be printed by the config module
        LOGICAL_NAME=$(uv run python scripts/get_model_name.py "${MODEL_ID}" "config/models.toml")
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
            
            # Get the highest run ID for this specific file within this model
            HIGHEST_RUN=$(get_highest_run_id_for_file "$base_name" "${PREDICTIONS_DIR}")
            NEXT_RUN=$((HIGHEST_RUN + 1))
            FILE_RUN_ID=$(printf "%02d" $NEXT_RUN)
    
            # Define the output prediction file
            prediction_file="${SAMPLE_PREDICTIONS_DIR}/${base_name}_${FILE_RUN_ID}_${DATE_STAMP}_prediction.json"
    
            echo "Processing $img_file -> $prediction_file (Run ID: ${FILE_RUN_ID})"
    
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
        
        # Filter files if specific question IDs are requested
        FILTER_QUESTIONS=false
        declare -a QUESTION_ID_ARRAY
        if [ -n "$QUESTION_IDS" ]; then
            FILTER_QUESTIONS=true
            # Convert comma-separated list to array
            IFS=',' read -ra QUESTION_ID_ARRAY <<< "$QUESTION_IDS"
            echo "Filtering to only process question IDs: ${QUESTION_IDS}"
        fi
        
        for img_file in data/eval/*.png; do
            # Extract the base filename without extension
            base_name=$(basename "$img_file" .png)
            
            # Skip if specific questions requested and this one is not included
            if [ "$FILTER_QUESTIONS" = true ]; then
                # Extract question ID from filename (first part before underscore or entire name if no underscore)
                QUESTION_ID="${base_name%%_*}"
                # Check if it's in the requested questions
                FOUND=false
                for qid in "${QUESTION_ID_ARRAY[@]}"; do
                    if [ "$QUESTION_ID" = "$qid" ]; then
                        FOUND=true
                        break
                    fi
                done
                
                if [ "$FOUND" = false ]; then
                    echo "Skipping $img_file (not in requested question IDs)"
                    continue
                fi
            fi
            
            # Get the highest run ID for this specific file within this model
            HIGHEST_RUN=$(get_highest_run_id_for_file "$base_name" "${PREDICTIONS_DIR}")
            NEXT_RUN=$((HIGHEST_RUN + 1))
            FILE_RUN_ID=$(printf "%02d" $NEXT_RUN)
    
            # Define the output prediction file
            prediction_file="${EVAL_PREDICTIONS_DIR}/${base_name}_${FILE_RUN_ID}_${DATE_STAMP}_prediction.json"
    
            echo "Processing $img_file -> $prediction_file (Run ID: ${FILE_RUN_ID})"
    
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