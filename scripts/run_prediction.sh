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
#   --jobs N: Number of worker processes to use (default: ${LDE_JOBS:-9})
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
JOBS="${LDE_JOBS:-9}"
DISPLAY_NAME=""
MODELS=()
REFRESH_DATASETS=false
QUESTION_IDS=""
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

run_prediction_task() {
    local split="$1"
    local model_id="$2"
    local shots="$3"
    local sample_dataset="$4"
    local img_file="$5"
    local prediction_file="$6"

    mkdir -p "$(dirname "$prediction_file")"
    echo "[start] pred ${split} $(basename "$img_file" .png) -> $(basename "$prediction_file")"
    uv run python -m little_dorrit_editor.cli predict run \
        --model-id "$model_id" \
        --shots "$shots" \
        --sample-dataset "$sample_dataset" \
        "$img_file" \
        "$prediction_file"
}

run_task_file() {
    local task_file="$1"
    local worker_flag="$2"
    local jobs="$3"

    if [ ! -s "$task_file" ]; then
        return 0
    fi

    if [ "$jobs" -le 1 ]; then
        while IFS= read -r task; do
            [ -z "$task" ] && continue
            bash "$SCRIPT_PATH" "$worker_flag" "$task" || return 1
        done < "$task_file"
        return 0
    fi

    xargs -0 -P "$jobs" -I{} bash "$SCRIPT_PATH" "$worker_flag" "{}" < <(
        while IFS= read -r task; do
            [ -z "$task" ] && continue
            printf '%s\0' "$task"
        done < "$task_file"
    )
}

if [[ "${1:-}" == "--predict-task" ]]; then
    IFS=$'\t' read -r split model_id shots sample_dataset img_file prediction_file <<< "$2"
    run_prediction_task "$split" "$model_id" "$shots" "$sample_dataset" "$img_file" "$prediction_file"
    exit $?
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --shots)
      SHOTS="$2"
      shift 2
      ;;
    --jobs)
      JOBS="$2"
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

if ! [[ "$JOBS" =~ ^[1-9][0-9]*$ ]]; then
  echo "Error: --jobs must be a positive integer"
  exit 1
fi

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
            # Find any prediction files for this file_id regardless of date so
            # run IDs remain monotonic across multi-day benchmark runs.
            local existing_files=$(find "$dir" -type f -name "${file_id}_*_prediction.json" 2>/dev/null)
            
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
    TASK_FILE=$(mktemp)
    trap 'rm -f "$TASK_FILE"' EXIT
    
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
    REASONING_EFFORT=$(uv run python scripts/get_model_name.py \
        "${MODEL_ID}" "config/models.toml" "reasoning_effort")
    if [[ -n "${REASONING_EFFORT}" ]]; then
        REASONING_EFFORT_JSON="\"${REASONING_EFFORT}\""
        NOTES="Benchmark run with ${SHOTS}-shot learning at ${REASONING_EFFORT} reasoning effort"
    else
        REASONING_EFFORT_JSON="null"
        NOTES="Benchmark run with ${SHOTS}-shot learning"
    fi
    cat > "$CONFIG_FILE" << EOL
{
  "model_id": "${MODEL_ID}",
  "display_name": "${CURRENT_DISPLAY_NAME}",
  "shots": ${SHOTS},
  "temperature": ${TEMPERATURE},
  "reasoning_effort": ${REASONING_EFFORT_JSON},
  "date": "$(date +"%Y-%m-%d")",
  "notes": "${NOTES}"
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

            echo "Queueing sample $img_file -> $prediction_file (Run ID: ${FILE_RUN_ID})"
            printf 'sample\t%s\t%s\t%s\t%s\t%s\n' \
                "$MODEL_ID" "$SHOTS" "$SAMPLE_DATASET" "$img_file" "$prediction_file" >> "$TASK_FILE"
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

            echo "Queueing eval $img_file -> $prediction_file (Run ID: ${FILE_RUN_ID})"
            printf 'eval\t%s\t%s\t%s\t%s\t%s\n' \
                "$MODEL_ID" "$SHOTS" "$SAMPLE_DATASET" "$img_file" "$prediction_file" >> "$TASK_FILE"
        done
        echo "Prediction generation complete for $MODEL_ID."
        echo "Evaluation predictions stored in: $EVAL_PREDICTIONS_DIR"
    else
        echo "No evaluation files found in data/eval. Please ensure evaluation data is available."
    fi

    echo "Running queued prediction tasks with ${JOBS} worker(s)..."
    if ! run_task_file "$TASK_FILE" "--predict-task" "$JOBS"; then
        echo "Error: One or more prediction worker tasks failed for ${MODEL_ID}."
        echo "Run scripts/diagnose_model_run.py ${MODEL_ID} to identify missing or bad artifacts."
        rm -f "$TASK_FILE"
        trap - EXIT
        exit 1
    fi

    rm -f "$TASK_FILE"
    trap - EXIT
    
    echo "Finished processing model: $MODEL_ID"
    echo "Use './scripts/run_evaluation.sh ${MODEL_ID} --jobs ${JOBS}' to evaluate the predictions."
done

echo "=========================================================="
echo "All predictions generated successfully for ${#MODELS[@]} models."
echo
echo "To evaluate all models, run:"
for MODEL_ID in "${MODELS[@]}"; do
    echo "  ./scripts/run_evaluation.sh ${MODEL_ID} --jobs ${JOBS}"
done
