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
6. `italicize`: Changing text to italic

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

# Set up environment variables for API keys
export OPENAI_API_KEY="your_openai_api_key"
export ANTHROPIC_API_KEY="your_anthropic_api_key"  # Optional
export GOOGLE_API_KEY="your_google_api_key"        # Optional
```

## Usage

### Model Configuration

The project uses TOML configuration files to manage LLM configurations:

```bash
# List available models
config list
```

This will display all configured models with their IDs, names, and API types.

#### Configuration Files

The system uses the following configuration files:

1. **Main configuration**: `config/models.toml`
   - Contains standard model configurations
   - Uses environment variables for API keys (e.g., `${OPENAI_API_KEY}`)
   - Checked into version control
   - Supports OpenRouter routing knobs such as `openrouter_provider = { sort = "latency" }` and `service_tier = "priority"`

2. **Local configuration**: `config/models.local.toml` and `config/local*.toml`
   - For local development with direct API keys
   - Not checked into version control (ignored by .gitignore)
   - Takes precedence over main configuration

#### Using Direct API Keys (Safely)

To use direct API keys without risk of committing them:

1. Create a local configuration file:
   ```bash
   # Create a local configuration file (already git-ignored)
   touch config/models.local.toml
   ```

2. Two methods for adding API keys:

   **Method 1: Create entirely new models**
   ```toml
   [local-gpt-4o]
   endpoint = "https://api.openai.com/v1"
   model_name = "gpt-4o"
   api_key = "sk-your-actual-api-key-here"  # Direct API key
   logical_name = "Local GPT-4o"
   ```

   **Method 2: Override just the API key for existing models**
   ```toml
   [local:gpt-4o]
   api_key = "sk-your-actual-api-key-here"  # Only the API key changes
   
   [local:claude-3-7-sonnet-latest]
   api_key = "sk-ant-your-api-key-here"  # Inherits everything else
   ```

3. Use either the original model ID (for overrides) or your local model ID:
   ```bash
   # For method 1 (new models with local- prefix)
   ./scripts/run_prediction.sh local-gpt-4o 2
   
   # For method 2 (overrides using local:), use the original model ID
   ./scripts/run_prediction.sh gpt-4o 2
   ```

The configuration supports various LLM providers (OpenAI, Anthropic, Google) through a consistent interface.

### Complete Evaluation Workflow

The benchmark includes scripts to automate the entire prediction, evaluation, and reporting workflow:

1. **Generate Predictions**:
   ```bash
   # Generate predictions for all evaluation images using the gpt-4o model with 2-shot learning
   ./scripts/run_prediction.sh gpt-4o --shots 2

   # Same run with 9 parallel workers
   ./scripts/run_prediction.sh gpt-4o --shots 2 --jobs 9
   ```

2. **Evaluate Predictions**:
   ```bash
   # Evaluate predictions and calculate metrics (using the default GPT-5.2 judge)
   ./scripts/run_evaluation.sh gpt-4o

   # Evaluate in parallel
   ./scripts/run_evaluation.sh gpt-4o --jobs 9
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

### Diagnosing a Model Run

Use the diagnostic utility to inspect the current state of a model directory under `predictions/`.

```bash
# Human-readable report with detailed issues
python scripts/diagnose_model_run.py or_gemma_4_31b --expected-runs 3 --details

# JSON output for automation
python scripts/diagnose_model_run.py or_gemma_4_31b --expected-runs 3 --json

# just wrapper
just diagnose or_gemma_4_31b
```

The diagnostic report checks:
- sample prediction completeness
- eval prediction completeness
- bad prediction files containing an `"error"` field or invalid JSON
- missing result files for otherwise valid eval predictions
- duplicate `(file_id, run_id)` keys caused by reruns on different dates
- orphan result files with no corresponding prediction file

This is the right first tool to run before deciding whether a model needs:
- selective reruns of bad predictions
- selective re-judging
- cleanup of duplicate run IDs
- a full rebuild of the model directory

### Parallelism

Both benchmark runner scripts support built-in parallel worker control:

```bash
./scripts/run_prediction.sh MODEL_ID --jobs 9
./scripts/run_evaluation.sh MODEL_ID --jobs 9
```

Notes:
- `--jobs 1` is the default and preserves the original sequential behavior.
- Prediction run IDs are assigned before workers start, so parallel prediction runs keep deterministic filenames without collisions.
- The Python CLI remains single-file-per-invocation; parallelism lives in the shell orchestration layer.

### Manual Prediction and Evaluation

You can also run individual steps manually:

```bash
# Zero-shot prediction
python -m little_dorrit_editor.cli predict run --model-id "gpt-4o" --shots 0 data/sample/001.png predictions/001_prediction.json

# Few-shot prediction with examples
python -m little_dorrit_editor.cli predict run --model-id "gpt-4o" --shots 2 data/sample/001.png predictions/001_prediction.json

# Using a different model (e.g., Claude)
python -m little_dorrit_editor.cli predict run --model-id "claude-3-7-sonnet-latest" --shots 0 data/sample/001.png predictions/001_prediction.json
```

The `predict run` command supports the following options:
- `--model-id`, `-m`: Model ID from config to use for predictions (default: "gpt-4o")
- `--shots`, `-s`: Number of examples to use for few-shot prompting (default: 0)
- `--sample-dataset`, `-d`: Path to the dataset containing examples (default: "data/hf/sample/little-dorrit-editor")
- `--model-name`: Alias for --model-id (for backward compatibility)
- `--temperature`, `-t`: Temperature (overrides model's configured default; ignored for GPT-5 family / thinking mode)
- `--reasoning-effort`: Reasoning effort for thinking models (e.g., low/medium/high; set to "none" to disable)

### Running Individual Evaluations

```bash
python -m little_dorrit_editor.cli evaluate run --model-name "your_model_id" --llm-model "gpt-4o" path/to/predicted.json path/to/ground_truth.json
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

#### Excluding Models from Leaderboard

To exclude a model from the leaderboard (e.g., for experimental runs or models still in development):

1. Create an empty `.noinclude` file in the model's prediction directory:
   ```bash
   # Example: Exclude the 'experimental-model' from the leaderboard
   touch predictions/experimental-model/.noinclude
   ```

2. The model will be automatically skipped when running `build_site_results.py` to update the leaderboard.

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
