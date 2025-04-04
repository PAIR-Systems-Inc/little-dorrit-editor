"""Leaderboard management for the Little Dorrit Editor benchmark."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from little_dorrit_editor.types import EvaluationResult


def load_leaderboard(
    leaderboard_path: Optional[Path] = None,
) -> List[Dict]:
    """Load the current leaderboard results.

    Args:
        leaderboard_path: Path to results.json (defaults to project's leaderboard dir)

    Returns:
        List of leaderboard entries
    """
    if leaderboard_path is None:
        # Default to project's leaderboard directory
        project_root = Path(__file__).parent.parent
        leaderboard_path = project_root / "leaderboard" / "results.json"
    
    if not leaderboard_path.exists():
        # Create empty leaderboard if it doesn't exist
        leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
        with open(leaderboard_path, "w") as f:
            json.dump([], f)
        return []
    
    with open(leaderboard_path, "r") as f:
        return json.load(f)


def update_leaderboard(
    result: EvaluationResult, leaderboard_path: Optional[Path] = None
) -> None:
    """Update the leaderboard with new evaluation results.

    Args:
        result: Evaluation result to add
        leaderboard_path: Path to results.json (defaults to project's leaderboard dir)
    """
    if leaderboard_path is None:
        # Default to project's leaderboard directory
        project_root = Path(__file__).parent.parent
        leaderboard_path = project_root / "leaderboard" / "results.json"
    
    # Load current leaderboard
    leaderboard = load_leaderboard(leaderboard_path)
    
    # Convert result to dict
    result_dict = result.model_dump()
    
    # Check if this model already has an entry
    for i, entry in enumerate(leaderboard):
        if entry["model_name"] == result.model_name:
            # Update existing entry
            leaderboard[i] = result_dict
            break
    else:
        # Add new entry
        leaderboard.append(result_dict)
    
    # Sort by F1 score
    leaderboard.sort(key=lambda x: x["f1_score"], reverse=True)
    
    # Save updated leaderboard
    with open(leaderboard_path, "w") as f:
        json.dump(leaderboard, f, indent=2)
    
    # Regenerate HTML file
    generate_html(leaderboard, leaderboard_path.parent / "index.html")


def generate_html(leaderboard: List[Dict], output_path: Path) -> None:
    """Generate an HTML leaderboard page from results.

    Args:
        leaderboard: List of leaderboard entries
        output_path: Path to save the HTML file
    """
    # Format dates for display
    for entry in leaderboard:
        try:
            date = datetime.fromisoformat(entry["date"])
            entry["display_date"] = date.strftime("%Y-%m-%d")
        except (ValueError, KeyError):
            entry["display_date"] = "Unknown"
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Little Dorrit Editor Benchmark Leaderboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #eaecef;
            padding-bottom: 0.3em;
        }}
        p {{
            margin-bottom: 1.5em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            font-size: 0.9em;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
            border-radius: 5px;
            overflow: hidden;
        }}
        thead tr {{
            background-color: #2c3e50;
            color: #ffffff;
            text-align: left;
        }}
        th, td {{
            padding: 12px 15px;
        }}
        tbody tr {{
            border-bottom: 1px solid #dddddd;
        }}
        tbody tr:nth-of-type(even) {{
            background-color: #f3f3f3;
        }}
        tbody tr:last-of-type {{
            border-bottom: 2px solid #2c3e50;
        }}
        .medal {{
            display: inline-block;
            width: 20px;
            height: 20px;
            line-height: 20px;
            text-align: center;
            border-radius: 50%;
            color: white;
            font-weight: bold;
            margin-right: 5px;
        }}
        .gold {{ background-color: #FFD700; }}
        .silver {{ background-color: #C0C0C0; }}
        .bronze {{ background-color: #CD7F32; }}
        footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 0.8em;
            color: #7f8c8d;
        }}
        .updated {{
            text-align: right;
            font-style: italic;
            color: #7f8c8d;
            font-size: 0.8em;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <h1>Little Dorrit Editor Benchmark Leaderboard</h1>
    
    <p>
        This leaderboard tracks the performance of multimodal language models on the task of interpreting
        handwritten editorial corrections in printed text from Charles Dickens' "Little Dorrit."
    </p>
    
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Model</th>
                <th>F1 Score</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>Date</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for i, entry in enumerate(leaderboard):
        # Add medal icon for top 3
        medal = ""
        if i == 0:
            medal = '<span class="medal gold">1</span>'
        elif i == 1:
            medal = '<span class="medal silver">2</span>'
        elif i == 2:
            medal = '<span class="medal bronze">3</span>'
        
        html += f"""
            <tr>
                <td>{i + 1}</td>
                <td>{medal}{entry['model_name']}</td>
                <td>{entry['f1_score']:.4f}</td>
                <td>{entry['precision']:.4f}</td>
                <td>{entry['recall']:.4f}</td>
                <td>{entry['display_date']}</td>
            </tr>"""
    
    html += f"""
        </tbody>
    </table>
    
    <p class="updated">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <footer>
        <p>
            For more information, visit the 
            <a href="https://github.com/yourusername/little-dorrit-editor">Little Dorrit Editor repository</a>.
        </p>
    </footer>
</body>
</html>
"""
    
    with open(output_path, "w") as f:
        f.write(html)