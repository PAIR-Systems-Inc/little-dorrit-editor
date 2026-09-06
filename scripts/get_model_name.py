#!/usr/bin/env python
"""Read a model configuration value without loading provider credentials."""

import sys
import tomllib


def get_model_value(model_id, config_path, field="logical_name"):
    """Get a model value from the TOML config.

    Args:
        model_id: The ID of the model to look up
        config_path: Path to the config file

    Returns:
        The configured value, or a field-appropriate default if not found.
    """
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        if model_id in config and field in config[model_id]:
            return config[model_id][field]
    except Exception:
        pass

    return model_id if field == "logical_name" else ""


def get_logical_name(model_id, config_path):
    """Preserve the original helper API for callers and tests."""
    return get_model_value(model_id, config_path)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: get_model_name.py MODEL_ID CONFIG_PATH [FIELD]",
            file=sys.stderr,
        )
        sys.exit(1)

    model_id = sys.argv[1]
    config_path = sys.argv[2]
    field = sys.argv[3] if len(sys.argv) > 3 else "logical_name"

    print(get_model_value(model_id, config_path, field))
