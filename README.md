# Little Dorrit Editor

150 years after her quiet rebellion in the Marshalsea, Little Dorrit returns—with
red pen in hand—to help evaluate the judgment of modern language models.

## About the Benchmark

This benchmark evaluates the ability of multimodal language models (LLMs) to
interpret handwritten editorial corrections in printed text. Using annotated
scans from Charles Dickens' "Little Dorrit," we challenge models to accurately
capture human editing intentions.

### Task Description

- **Input**: A JPEG image of a printed page with handwritten markup/corrections
- **Output**: A list of JSON edit operations representing the intended changes
- **Evaluation**: Comparison of predicted edits to ground truth using an LLM judge
- **Metric**: Precision, recall, and F1 score

### Edit Types

The benchmark recognizes several types of editorial operations:

1. `insertion`: Adding new text
2. `deletion`: Removing existing text
3. `replacement`: Substituting text with alternatives
4. `punctuation`: Modifying or adding punctuation
5. `capitalization`: Changing case (upper/lower)
6. `reordering`: Rearranging text sequence

### Line Numbering Convention

- Line numbers start at 1 for the first full line of body text on the page.
- The chapter name (e.g., "Chapter II") is not counted as a line.
- The chapter title or section title (e.g., "Fellow Travellers") is referred to as line 0.
- This ensures consistent reference to editable text while still allowing markup of titles and headings.

## Installation

This project uses Python 3.13+ and [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
# Clone the repository
git clone https://github.com/pairsys/little-dorrit-editor.git
cd little-dorrit-editor

# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
uv pip install -e .
```

## Usage

### Complete Evaluation Workflow

The benchmark includes scripts to automate the entire prediction, evaluation, and reporting workflow:

1. **Generate Predictions**:
   ```bash
   # Generate predictions for all evaluation images using the gpt-4o model with 2-shot learning
   ./scripts/run_prediction.sh gpt-4o 2
   ```

2. **Evaluate Predictions**:
   ```bash
   # Evaluate predictions and calculate metrics
   ./scripts/run_evaluation.sh gpt-4o
   ```

3. **Generate Report**:
   ```bash
   # Display formatted evaluation results
   ./scripts/report_evaluation.sh gpt-4o
   ```

4. **Update Leaderboard**:
   ```bash
   # Update results.json for the leaderboard website
   python scripts/build_site_results.py
   ```

### Manual Prediction and Evaluation

You can also run individual steps manually:

```bash
# Zero-shot prediction
python scripts/evaluate.py generate --model-name "gpt-4o" data/sample/001.png predictions/001_prediction.json

# Few-shot prediction with examples
python scripts/evaluate.py generate --shots 2 --model-name "gpt-4o" data/sample/001.png predictions/001_prediction.json
```

The `generate` command supports the following options:
- `--model-name`, `-m`: Model to use for predictions (default: "gpt-4o")
- `--shots`, `-s`: Number of examples to use for few-shot prompting (default: 0)
- `--sample-dataset`, `-d`: Path to the dataset containing examples (default: "data/hf/sample/little-dorrit-editor")
- `--api-key`, `-k`: OpenAI API key (optional, defaults to environment variable)

### Running Individual Evaluations

```bash
python scripts/evaluate.py evaluate --model-name "your_model_name" path/to/predicted.json path/to/ground_truth.json
```

### Preparing Datasets

Use the `prepare_datasets.py` script to convert all data to Hugging Face format:

```bash
# Prepare both sample and evaluation datasets
python scripts/prepare_datasets.py

# Clean existing datasets before preparing
python scripts/prepare_datasets.py --clean

# Specify a custom output directory
python scripts/prepare_datasets.py --output-dir custom/output/path
```

If you need to convert individual datasets:

```bash
# Convert sample data only
python scripts/convert_to_hf_dataset.py data/sample/ data/hf/sample/

# Convert evaluation data
python scripts/convert_to_hf_dataset.py data/eval/ data/hf/eval/
```

### Leaderboard

View the current leaderboard at [GitHub Pages site](https://pairsys.github.io/little-dorrit-editor/).

## Dataset

### Data Organization

The project contains two sets of data:

- **Sample Data** (`data/sample/`): Public examples included in the repository
  - Used for demonstration, development, and testing
  - Contains a small set of representative examples
  - Available to everyone via the repository

- **Evaluation Data** (`data/eval/`): Private benchmark data excluded from Git
  - Used for official evaluation and leaderboard rankings
  - Contains a comprehensive set of test examples
  - Access restricted to maintain benchmark integrity

### Hugging Face Dataset

The full Little Dorrit Editor dataset is available on Hugging Face: [huggingface.co/datasets/pairsys/little-dorrit-editor](https://huggingface.co/datasets/pairsys/little-dorrit-editor)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.