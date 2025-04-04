#!/bin/bash
# Script to report Little Dorrit Editor evaluation results without running evaluations

# Default values
MODEL_NAME=${1:-"gpt-4o"}  # Use the first parameter or default to gpt-4o
BASE_OUTPUT_DIR=${2:-"predictions"}  # Use the second parameter or default to predictions

# Set up directory structure
PREDICTIONS_DIR="${BASE_OUTPUT_DIR}/${MODEL_NAME}"
RESULTS_DIR="${PREDICTIONS_DIR}/results"

# Check if results directory exists
if [ ! -d "$RESULTS_DIR" ]; then
    echo "Error: Results directory not found: $RESULTS_DIR"
    echo "Usage: $0 [model_name] [output_dir]"
    echo "Example: $0 gpt-4o predictions"
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
echo "Model: $MODEL_NAME"
echo "Results directory: $RESULTS_DIR"

# Check if there are any result files
result_files=$(ls -1 "$RESULTS_DIR"/*.json 2>/dev/null)
if [ -z "$result_files" ]; then
    echo "No evaluation results found in $RESULTS_DIR."
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

        # Extract metrics from the result file
        precision=$(grep -o '"precision": [0-9.]*' "$result_file" | head -1 | cut -d' ' -f2)
        recall=$(grep -o '"recall": [0-9.]*' "$result_file" | head -1 | cut -d' ' -f2)
        f1=$(grep -o '"f1_score": [0-9.]*' "$result_file" | head -1 | cut -d' ' -f2)

        # Extract counts for aggregation
        correct_count=$(grep -o '"correct_count": [0-9]*' "$result_file" | head -1 | awk '{print $2}')
        total_gt=$(grep -o '"total_ground_truth": [0-9]*' "$result_file" | head -1 | awk '{print $2}')
        total_pred=$(grep -o '"total_predicted": [0-9]*' "$result_file" | head -1 | awk '{print $2}')

        # Calculate metrics for this file
        tp=$correct_count
        fp=$((total_pred - tp))
        fn=$((total_gt - tp))

        # Add to overall totals
        total_true_positives=$((total_true_positives + tp))
        total_false_positives=$((total_false_positives + fp))
        total_false_negatives=$((total_false_negatives + fn))
        total_correct_count=$((total_correct_count + correct_count))
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
printf "  %-11s   %-9s   %-6s   %-8s   %-2s   %-2s   %-2s\n" "File Name" "Precision" "Recall" "F1 Score" "TP" "FP" "FN"
echo "─────────────────────────────────────────────────────────────────"

# Print each row of the table
for i in "${!file_names[@]}"; do
    precision=$(printf "%.4f" "${precisions[$i]}")
    recall=$(printf "%.4f" "${recalls[$i]}")
    f1=$(printf "%.4f" "${f1s[$i]}")
    printf "  %-11s   %-9s   %-6s   %-8s   %-2s   %-2s   %-2s\n" \
        "${file_names[$i]}" "$precision" "$recall" "$f1" "${tps[$i]}" "${fps[$i]}" "${fns[$i]}"
done

# Print the table footer - bold bottom line
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Add a bit of space and show model name as a header
echo -e "\n==================================================="
echo "    Overall Evaluation Results for Model: $MODEL_NAME"
echo "==================================================="

# Calculate aggregate precision, recall, F1
total_predictions=$((total_true_positives + total_false_positives))
total_ground_truth=$((total_true_positives + total_false_negatives))

if [ $total_true_positives -eq 0 ]; then
    overall_precision=0
    overall_recall=0
    overall_f1=0
else
    overall_precision=$(echo "scale=4; $total_true_positives / $total_predictions" | bc 2>/dev/null || echo "0")
    overall_recall=$(echo "scale=4; $total_true_positives / $total_ground_truth" | bc 2>/dev/null || echo "0")
    sum_pr=$(echo "$overall_precision + $overall_recall" | bc 2>/dev/null || echo "0")
    if (( $(echo "$sum_pr > 0" | bc -l) )); then
        overall_f1=$(echo "scale=4; 2 * $overall_precision * $overall_recall / ($overall_precision + $overall_recall)" | bc 2>/dev/null || echo "0")
    else
        overall_f1=0
    fi
fi

# Format the metrics for display
formatted_precision=$(printf "%.4f" $overall_precision)
formatted_recall=$(printf "%.4f" $overall_recall)
formatted_f1=$(printf "%.4f" $overall_f1)

# Create a nice table for overall metrics
echo ""
echo "                   Aggregate Metrics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  %-25s   %-17s\n" "True Positives" "$total_true_positives"
printf "  %-25s   %-17s\n" "False Positives" "$total_false_positives"
printf "  %-25s   %-17s\n" "False Negatives" "$total_false_negatives"
printf "  %-25s   %-17s\n" "Total Edits" "$total_ground_truth"
echo "─────────────────────────────────────────────────────────────────"
printf "  %-25s   %-17s\n" "Precision" "$formatted_precision"
printf "  %-25s   %-17s\n" "Recall" "$formatted_recall"
printf "  %-25s   %-17s\n" "F1 Score" "$formatted_f1"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -e "\nReport complete."