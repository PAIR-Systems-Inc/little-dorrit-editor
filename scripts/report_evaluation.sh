#!/bin/bash
# Script to report Little Dorrit Editor evaluation results without running evaluations
#
# Usage: ./report_evaluation.sh [model_id] [output_dir]
#   model_id: ID of the model to report (default: gpt-4o)
#   output_dir: Base output directory (default: predictions)
#
# Available model IDs can be viewed with: config list

# Default values
MODEL_ID=${1:-"gpt-4o"}  # Use the first parameter or default to gpt-4o
BASE_OUTPUT_DIR=${2:-"predictions"}  # Use the second parameter or default to predictions

# Set up directory structure using new format
PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_ID}"
CONFIG_FILE="${PREDICTIONS_DIR}/config.json"
RESULTS_DIR="${PREDICTIONS_DIR}/results"
EVAL_RESULTS_DIR="${RESULTS_DIR}/eval"

# Check if the model directory exists
if [ ! -d "$PREDICTIONS_DIR" ]; then
    echo "Error: Model directory not found: $PREDICTIONS_DIR"
    echo "Usage: $0 [model_id] [output_dir]"
    echo "Example: $0 gpt-4o predictions"
    exit 1
fi

# Read and display experiment configuration if available
if [ -f "$CONFIG_FILE" ]; then
    echo "Experiment configuration:"
    cat "$CONFIG_FILE"
    echo ""
    
    # Extract shot count and display name for the report header
    SHOTS=$(grep -o '"shots": [0-9]*' "$CONFIG_FILE" | awk '{print $2}')
    DISPLAY_NAME=$(grep -o '"display_name": "[^"]*"' "$CONFIG_FILE" 2>/dev/null | awk -F '"' '{print $4}')
    
    # If no display name in config, try to get logical name from config module
    if [[ -z "${DISPLAY_NAME}" ]]; then
        # Try to get logical name from config
        LOGICAL_NAME=$(python -c "from little_dorrit_editor.config import get_model; print(get_model('${MODEL_ID}').logical_name)" 2>/dev/null)
        if [[ $? -eq 0 && -n "${LOGICAL_NAME}" ]]; then
            DISPLAY_NAME="${LOGICAL_NAME}"
        else
            DISPLAY_NAME="${MODEL_ID}"
        fi
    fi
else
    SHOTS="unknown"
    # Try to get logical name from config module even if config file doesn't exist
    LOGICAL_NAME=$(python -c "from little_dorrit_editor.config import get_model; print(get_model('${MODEL_ID}').logical_name)" 2>/dev/null)
    if [[ $? -eq 0 && -n "${LOGICAL_NAME}" ]]; then
        DISPLAY_NAME="${LOGICAL_NAME}"
    else
        DISPLAY_NAME="${MODEL_ID}"
    fi
    echo "Warning: No configuration file found at $CONFIG_FILE"
fi

# Check if results directory exists
if [ ! -d "$EVAL_RESULTS_DIR" ]; then
    echo "Error: Results directory not found: $EVAL_RESULTS_DIR"
    echo "Run './scripts/run_evaluation.sh ${MODEL_ID}' first to generate evaluation results."
    exit 1
fi

# Arrays to hold aggregate metrics
total_true_positives=0
total_false_positives=0
total_false_negatives=0
total_correct_count=0
total_files=0

# Summarize per-file results
echo -e "\n===== Per-File Evaluation Results ====="
echo "Model: $DISPLAY_NAME (${SHOTS}-shot learning)"
echo "Results directory: $EVAL_RESULTS_DIR"

# Check if there are any result files
result_files=$(ls -1 "$EVAL_RESULTS_DIR"/*.json 2>/dev/null)
if [ -z "$result_files" ]; then
    echo "No evaluation results found in $EVAL_RESULTS_DIR."
    exit 1
fi

# Create an array to store data for the table
declare -a file_names=()
declare -a precisions=()
declare -a recalls=()
declare -a f1s=()
declare -a tps=()
declare -a fps=()
declare -a fns=()

# Process each result file to collect data
for result_file in $result_files; do
    if [ -f "$result_file" ]; then
        # Extract base name from result file
        base_name=$(basename "$result_file" | sed 's/_[0-9]*_[0-9]*_results.json//')

        # Result files store per-edit judgements under details; derive counts
        # directly so this report stays compatible with the current JSON shape.
        metrics=$(python - "$result_file" <<'PY'
import json
import sys

with open(sys.argv[1], "r") as f:
    data = json.load(f)

tp = fp = fn = 0
for detail in data.get("details", []):
    tp += int(detail.get("tp") or 0)
    fp += int(detail.get("fp") or 0)
    fn += int(detail.get("fn") or 0)

precision = tp / (tp + fp) if tp + fp else 0.0
recall = tp / (tp + fn) if tp + fn else 0.0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

print(f"{precision:.4f}\t{recall:.4f}\t{f1:.4f}\t{tp}\t{fp}\t{fn}")
PY
)
        IFS=$'\t' read -r precision recall f1 tp fp fn <<< "$metrics"

        # Add to overall totals
        total_true_positives=$((total_true_positives + tp))
        total_false_positives=$((total_false_positives + fp))
        total_false_negatives=$((total_false_negatives + fn))
        total_correct_count=$((total_correct_count + tp))
        total_files=$((total_files + 1))

        # Store data for table
        file_names+=("$base_name")
        precisions+=("$precision")
        recalls+=("$recall")
        f1s+=("$f1")
        tps+=("$tp")
        fps+=("$fp")
        fns+=("$fn")
    fi
done

# Find the maximum width for each column
max_file_width=$(printf "%s\n" "${file_names[@]}" | wc -L)
max_file_width=$((max_file_width > 9 ? max_file_width : 9))  # min width for "File Name"

# Create a line of dashes for table borders
line=$(printf "%0.s━" $(seq 1 100))

# Print the table header
echo ""
# Bold top line with no vertical lines
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  %-11s   %9s   %6s   %8s   %2s   %2s   %2s\n" "File Name" "Precision" "Recall" "F1 Score" "TP" "FP" "FN"
echo "─────────────────────────────────────────────────────────────────"

# Print each row of the table
for i in "${!file_names[@]}"; do
    precision=$(printf "%.4f" "${precisions[$i]}")
    recall=$(printf "%.4f" "${recalls[$i]}")
    f1=$(printf "%.4f" "${f1s[$i]}")
    printf "  %-11s   %9s   %6s   %8s   %2s   %2s   %2s\n" \
        "${file_names[$i]}" "$precision" "$recall" "$f1" "${tps[$i]}" "${fps[$i]}" "${fns[$i]}"
done

# Print the table footer - bold bottom line
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Add a bit of space and show model display name as a header
echo -e "\n==================================================="
echo "    Overall Evaluation Results for ${DISPLAY_NAME} (${SHOTS}-shot)"
echo "==================================================="

# Calculate aggregate precision, recall, F1
total_predictions=$((total_true_positives + total_false_positives))
total_ground_truth=$((total_true_positives + total_false_negatives))

read -r overall_precision overall_recall overall_f1 < <(python - <<PY
tp = $total_true_positives
fp = $total_false_positives
fn = $total_false_negatives
precision = tp / (tp + fp) if tp + fp else 0.0
recall = tp / (tp + fn) if tp + fn else 0.0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
print(f"{precision:.4f} {recall:.4f} {f1:.4f}")
PY
)

# Format the metrics for display
formatted_precision=$(printf "%.4f" $overall_precision)
formatted_recall=$(printf "%.4f" $overall_recall)
formatted_f1=$(printf "%.4f" $overall_f1)

# Create a nice table for overall metrics
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "                   Aggregate Metrics"
echo "─────────────────────────────────────────────────────────────────"
printf "  %-25s   %17s\n" "True Positives" "$total_true_positives"
printf "  %-25s   %17s\n" "False Positives" "$total_false_positives"
printf "  %-25s   %17s\n" "False Negatives" "$total_false_negatives"
printf "  %-25s   %17s\n" "Total Edits" "$total_ground_truth"
echo "─────────────────────────────────────────────────────────────────"
printf "  %-25s   %17s\n" "Precision" "$formatted_precision"
printf "  %-25s   %17s\n" "Recall" "$formatted_recall"
printf "  %-25s   %17s\n" "F1 Score" "$formatted_f1"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -e "\nReport complete."
echo "To update the leaderboard site with these results, run: uv run python scripts/build_site_results.py"
