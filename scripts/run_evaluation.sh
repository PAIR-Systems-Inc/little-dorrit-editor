#!/bin/bash
# Script to run Little Dorrit Editor evaluation on existing predictions
#
# This script processes prediction files to generate evaluation results using a judge model.
# It matches ground truth data against prediction files, and handles file organization
# and configuration management.
#
# Key Features:
# - Evaluates multiple models in a single command
# - Filters by question ID for targeted evaluations
# - Maintains a consistent judge model for benchmark integrity
# - Skips already evaluated files unless --force is specified
#
# Usage: ./run_evaluation.sh [model_id1] [model_id2] ... [options]
#   model_id: One or more IDs of models to evaluate (default: gpt-4o if none provided)
#
# Options:
#   --display-name "Name": Custom display name for the leaderboard (only used if creating new config)
#   --judge-model MODEL: Model ID to use for evaluation judging (default: gpt-4o)
#                WARNING: Changing this is NOT recommended as it affects benchmark consistency
#   --jobs N: Number of worker processes to use (default: ${LDE_JOBS:-9})
#   --force: Force re-evaluation even if results already exist
#   --question-ids "id1,id2,...": Only process specific question IDs (comma-separated, no spaces)
#
# File Naming:
#   For each prediction file {question_id}_{run_id}_{date}_prediction.json, 
#   this script creates a corresponding {question_id}_{run_id}_{date}_results.json file
#
# Examples:
#   ./run_evaluation.sh or_gpt_4o_latest                    # Evaluate a single model
#   ./run_evaluation.sh or_gpt_4o_latest or_llama_4_scout   # Evaluate multiple models
#   ./run_evaluation.sh or_gpt_4o_latest --force            # Force re-evaluation
#   ./run_evaluation.sh or_gpt_4o_latest --question-ids "003,005" # Only evaluate questions 003 and 005
#
# Note: The --question-ids flag is particularly useful for addressing missing evaluations
# identified by the check_predictions.py script.
#
# Available model IDs can be viewed with: config list

# Default values
DEFAULT_MODEL="gpt-4o"
DISPLAY_NAME=""
LLM_JUDGE_MODEL="or_openai_gpt_5_2"
JOBS="${LDE_JOBS:-9}"
FORCE_EVAL=false
MODELS=()
QUESTION_IDS=""
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

run_evaluation_task() {
    local model_id="$1"
    local llm_judge_model="$2"
    local prediction_file="$3"
    local json_file="$4"
    local results_path="$5"

    mkdir -p "$(dirname "$results_path")"
    echo "[start] eval $(basename "$prediction_file") -> $(basename "$results_path")"
    uv run python -m little_dorrit_editor.cli evaluate run \
        --model-name "$model_id" \
        --llm-model "$llm_judge_model" \
        --output "$results_path" \
        "$prediction_file" \
        "$json_file"
}

run_task_file() {
    local task_file="$1"
    local jobs="$2"

    if [ ! -s "$task_file" ]; then
        return 0
    fi

    if [ "$jobs" -le 1 ]; then
        while IFS= read -r task; do
            [ -z "$task" ] && continue
            bash "$SCRIPT_PATH" --evaluate-task "$task" || return 1
        done < "$task_file"
        return 0
    fi

    xargs -0 -P "$jobs" -I{} bash "$SCRIPT_PATH" --evaluate-task "{}" < <(
        while IFS= read -r task; do
            [ -z "$task" ] && continue
            printf '%s\0' "$task"
        done < "$task_file"
    )
}

if [[ "${1:-}" == "--evaluate-task" ]]; then
    IFS=$'\t' read -r model_id llm_judge_model prediction_file json_file results_path <<< "$2"
    run_evaluation_task "$model_id" "$llm_judge_model" "$prediction_file" "$json_file" "$results_path"
    exit $?
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --display-name)
      DISPLAY_NAME="$2"
      shift 2
      ;;
    --judge-model)
      LLM_JUDGE_MODEL="$2"
      shift 2
      ;;
    --jobs)
      JOBS="$2"
      shift 2
      ;;
    --force)
      FORCE_EVAL=true
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

# Show warning if custom judge model provided and it's not the default
if [[ "$LLM_JUDGE_MODEL" != "or_openai_gpt_5_2" ]]; then
    echo "⚠️ WARNING: Overriding the default judge model is NOT recommended ⚠️"
    echo "It affects benchmark consistency and makes results incomparable with others."
    echo "Default judge: or_openai_gpt_5_2"
    echo "Custom judge: $LLM_JUDGE_MODEL"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " confirm
    if [[ "$confirm" != [yY] && "$confirm" != [yY][eE][sS] ]]; then
        LLM_JUDGE_MODEL="or_openai_gpt_5_2"
        echo "Using default judge model: $LLM_JUDGE_MODEL"
    else
        echo "Using custom judge model: $LLM_JUDGE_MODEL"
    fi
    echo ""
fi

# Set environment variables
# No API key needed here - the config module will use the relevant environment variable
BASE_OUTPUT_DIR="predictions"

# Process each model in sequence
for MODEL_ID in "${MODELS[@]}"; do
    echo "=========================================================="
    echo "Processing model: $MODEL_ID (${#MODELS[@]} total models in queue)"
    echo "=========================================================="
    
    # Set up directory structure for this model
    PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_ID}"
    CONFIG_FILE="${PREDICTIONS_DIR}/config.json"
    PREDICTIONS_OUTPUT_DIR="${PREDICTIONS_DIR}/predictions"
    EVAL_PREDICTIONS_DIR="${PREDICTIONS_OUTPUT_DIR}/eval"
    RESULTS_DIR="${PREDICTIONS_DIR}/results"
    EVAL_RESULTS_DIR="${RESULTS_DIR}/eval"
    TASK_FILE=$(mktemp)
    trap 'rm -f "$TASK_FILE"' EXIT
    
    # Verify the model directory exists
    if [ ! -d "$PREDICTIONS_DIR" ]; then
        echo "Error: Model directory not found: $PREDICTIONS_DIR"
        echo "Run './scripts/run_prediction.sh ${MODEL_ID}' first to generate predictions."
        echo "Skipping to next model (if any)..."
        continue
    fi
    
    # Verify config file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Warning: Config file not found: $CONFIG_FILE"
        echo "Creating a default config file with 2-shot learning..."
        
        # Get the model's logical name if no display name is provided
        CURRENT_DISPLAY_NAME="$DISPLAY_NAME"
        if [[ -z "${CURRENT_DISPLAY_NAME}" ]]; then
            # Use our standalone script to get the logical name
            LOGICAL_NAME=$(uv run python scripts/get_model_name.py "${MODEL_ID}" "config/models.toml")
            if [[ $? -eq 0 && -n "${LOGICAL_NAME}" ]]; then
                CURRENT_DISPLAY_NAME="${LOGICAL_NAME}"
            else
                CURRENT_DISPLAY_NAME="${MODEL_ID}"
            fi
        fi
    
        # Create a default config.json file
        cat > "$CONFIG_FILE" << EOL
{
  "model_id": "${MODEL_ID}",
  "display_name": "${CURRENT_DISPLAY_NAME}",
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
    echo "Evaluating predictions for model $MODEL_ID..."
    
    # Process only evaluation data
    if [ -d "data/eval" ] && [ "$(ls -A data/eval/*.json 2>/dev/null)" ]; then
        # Filter files if specific question IDs are requested
        FILTER_QUESTIONS=false
        declare -a QUESTION_ID_ARRAY
        if [ -n "$QUESTION_IDS" ]; then
            FILTER_QUESTIONS=true
            # Convert comma-separated list to array
            IFS=',' read -ra QUESTION_ID_ARRAY <<< "$QUESTION_IDS"
            echo "Filtering to only process question IDs: ${QUESTION_IDS}"
        fi
        
        for json_file in data/eval/*.json; do
            # Extract the base filename without extension
            base_name=$(basename "$json_file" .json)
            
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
                    echo "Skipping $json_file (not in requested question IDs)"
                    continue
                fi
            fi
            
            # Find ALL prediction files for this base name
            prediction_files=("${EVAL_PREDICTIONS_DIR}/${base_name}_"*"_prediction.json")
            
            # Check if any prediction files exist
            if [ ${#prediction_files[@]} -eq 0 ] || [ ! -f "${prediction_files[0]}" ]; then
                echo "Warning: No prediction files found for $base_name"
                continue
            fi
            
            echo "Found ${#prediction_files[@]} prediction file(s) for $base_name"
            
            # Process each prediction file
            for prediction_file in "${prediction_files[@]}"; do
                echo "Evaluating $prediction_file against $json_file"
                
                # Extract filename part for results
                pred_filename=$(basename "$prediction_file")
                results_filename="${pred_filename/_prediction/_results}"
                results_path="${EVAL_RESULTS_DIR}/${results_filename}"
                
                # Check if results already exist and whether to force re-evaluation
                if [ ! -f "$results_path" ] || [ "$FORCE_EVAL" = true ]; then
                    if [ -f "$results_path" ] && [ "$FORCE_EVAL" = true ]; then
                        echo "  Force flag set: Re-evaluating existing results..."
                    fi

                    printf '%s\t%s\t%s\t%s\t%s\n' \
                        "$MODEL_ID" "$LLM_JUDGE_MODEL" "$prediction_file" "$json_file" "$results_path" >> "$TASK_FILE"
                else
                    echo "  Skipping evaluation: Results already exist at $results_path"
                    echo "  Use --force to re-evaluate if needed"
                fi
            done
        done

        echo "Running queued evaluation tasks with ${JOBS} worker(s)..."
        if ! run_task_file "$TASK_FILE" "$JOBS"; then
            echo "Error: One or more evaluation worker tasks failed for ${MODEL_ID}."
            echo "Run scripts/diagnose_model_run.py ${MODEL_ID} to identify missing result artifacts."
            rm -f "$TASK_FILE"
            trap - EXIT
            exit 1
        fi
    else
        echo "No evaluation files found in data/eval. Please ensure evaluation data is available."
    fi

    rm -f "$TASK_FILE"
    trap - EXIT
    
    # Use the report script to show detailed results for this model
    echo -e "\nGenerating evaluation report for $MODEL_ID..."
    bash scripts/report_evaluation.sh "$MODEL_ID" "$BASE_OUTPUT_DIR"
    
    echo -e "\nEvaluation complete for $MODEL_ID. Results stored in $EVAL_RESULTS_DIR"
    echo "Finished processing model: $MODEL_ID"
done

echo "=========================================================="
echo "All evaluations completed for ${#MODELS[@]} models."
if [ "$FORCE_EVAL" = true ]; then
    echo "Force flag was set: Re-evaluated all existing results"
fi
