#!/usr/bin/env python
"""
Simple script to extract logical_name from models.toml for a given model_id.
This script avoids importing the full config module to prevent any warnings.
"""

import sys
import tomllib
from pathlib import Path

def get_logical_name(model_id, config_path):
    """Get the logical name for a model from the TOML config.
    
    Args:
        model_id: The ID of the model to look up
        config_path: Path to the config file
        
    Returns:
        The logical name of the model or the model_id if not found
    """
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        # In the TOML file, model entries use the format ["model_id"]
        # So we need to look for the model_id in the config
        if model_id in config and "logical_name" in config[model_id]:
            return config[model_id]["logical_name"]
    except Exception as e:
        # Failed to find the model - return the model_id
        pass
    
    # If no logical name found, return the model_id
    return model_id

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: get_model_name.py MODEL_ID CONFIG_PATH", file=sys.stderr)
        sys.exit(1)
        
    model_id = sys.argv[1]
    config_path = sys.argv[2]
    
    logical_name = get_logical_name(model_id, config_path)
    print(logical_name)