"""Command-line interfaces for Little Dorrit Editor tools."""

from pathlib import Path
from typing import Optional

import json
import typer
from rich.console import Console

from little_dorrit_editor.convert import create_hf_dataset
from little_dorrit_editor.evaluate import display_results, evaluate
from little_dorrit_editor.predict import generate_predictions
from little_dorrit_editor.config import list_models, get_model
from little_dorrit_editor.utils import extract_json_from_llm_response

# Create Typer apps
app = typer.Typer()

evaluate_app = typer.Typer()
predict_app = typer.Typer()
convert_app = typer.Typer()
config_app = typer.Typer()

app.add_typer(predict_app, name="predict")
app.add_typer(evaluate_app, name="evaluate")
app.add_typer(convert_app, name="convert")
app.add_typer(config_app, name="config")

console = Console()


@evaluate_app.command()
def run(
    predicted: Path = typer.Argument(
        ..., help="Path to the predicted edits JSON file"
    ),
    ground_truth: Path = typer.Argument(
        ..., help="Path to the ground truth edits JSON file"
    ),
    model_name: str = typer.Option(
        "unnamed_model", "--model-name", "-m", help="Name/ID of the model being evaluated"
    ),
    llm_model: str = typer.Option(
        "gpt-4.5-preview", "--llm-model", "-l",
        help=f"LLM model ID to use for evaluation. Available models: {', '.join(list_models().keys())}"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Path to save evaluation results as JSON"
    ),
    update_leaderboard: bool = typer.Option(
        False, "--update-leaderboard", "-u", help="Update the leaderboard with results"
    ),
) -> None:
    """Evaluate predicted edits against ground truth using an LLM judge."""
    try:
        # Validate paths
        if not predicted.exists():
            console.print(f"[red]Error:[/red] Predicted file not found: {predicted}")
            raise typer.Exit(code=1)

        if not ground_truth.exists():
            console.print(f"[red]Error:[/red] Ground truth file not found: {ground_truth}")
            raise typer.Exit(code=1)

        # Get model configuration
        llm_config = get_model(llm_model)
        console.print(f"Using LLM judge: {llm_config.logical_name}")

        # Run evaluation
        result = evaluate(
            ground_truth_path=ground_truth,
            prediction_path=predicted,
            model_name=model_name,
            llm_model=llm_model,
        )

        # Display results
        display_results(result)

        # Save results if requested
        if output:
            with open(output, "w") as f:
                import json

                json.dump(result.model_dump(), f, indent=2)
            console.print(f"Results saved to [bold]{output}[/bold]")

        # Update leaderboard if requested
        if update_leaderboard:
            from little_dorrit_editor.leaderboard import update_leaderboard

            update_leaderboard(result)
            console.print("[green]Leaderboard updated successfully![/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(code=1)


@predict_app.command()
def run(
    image: Path = typer.Argument(
        ..., help="Path to the image file to analyze"
    ),
    output: Path = typer.Argument(
        ..., help="Path to save the predicted edits JSON"
    ),
    model_id: str = typer.Option(
        "gpt-4o", "--model-id", "-m",
        help=f"Model ID to use for predictions. Available models: {', '.join(list_models().keys())}"
    ),
    model_name: Optional[str] = typer.Option(
        None, "--model-name", help="Alias for --model-id (for backward compatibility)"
    ),
    shots: int = typer.Option(
        0, "--shots", "-s", help="Number of examples to use for few-shot prompting"
    ),
    sample_dataset: Path = typer.Option(
        Path("data/hf/sample/little-dorrit-editor"),
        "--sample-dataset",
        "-d",
        help="Path to the sample dataset for few-shot examples"
    ),
) -> None:
    """Generate predictions using an LLM model with optional few-shot examples."""
    try:
        # Allow for backward compatibility with --model-name
        if model_name is not None:
            model_id = model_name
            console.print(f"[yellow]Warning:[/yellow] --model-name is deprecated. Please use --model-id instead.")

        # Generate predictions
        generate_predictions(
            image_path=image,
            output_path=output,
            model_id=model_id,
            shots=shots,
            sample_dataset_path=sample_dataset,
            console=console
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(code=1)


@config_app.command("list")
def list_available_models() -> None:
    """List all available models in the configuration."""
    from little_dorrit_editor.config import list_models, get_model
    from rich.table import Table

    models = list_models()

    if not models:
        console.print("[yellow]No models found in configuration.[/yellow]")
        return

    table = Table(title="Available Models")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Model", style="blue")
    table.add_column("API", style="magenta")

    for model_id, model_name in models.items():
        model_config = get_model(model_id)
        api_type = "OpenAI" if "openai" in model_config.endpoint else (
            "Anthropic" if "anthropic" in model_config.endpoint else
            "Google" if "generativelanguage" in model_config.endpoint else "Other"
        )
        table.add_row(model_id, model_name, model_config.model_name, api_type)

    console.print(table)


@convert_app.command()
def run(
    input_dir: Path = typer.Argument(
        ..., help="Directory containing annotation files and images"
    ),
    output_dir: Path = typer.Argument(
        ..., help="Output directory for the Hugging Face dataset"
    ),
    dataset_name: str = typer.Option(
        "little-dorrit-editor", "--name", "-n", help="Name of the dataset"
    ),
) -> None:
    """Convert annotation files to a Hugging Face dataset."""
    try:
        # Validate paths
        if not input_dir.exists() or not input_dir.is_dir():
            console.print(f"[red]Error:[/red] Input directory not found: {input_dir}")
            raise typer.Exit(code=1)

        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run conversion
        create_hf_dataset(
            data_dir=input_dir,
            output_dir=output_dir,
            dataset_name=dataset_name,
        )

        console.print(
            f"[green]Conversion complete![/green] Dataset saved to {output_dir / dataset_name}"
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
