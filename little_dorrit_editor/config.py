"""Configuration management for Little Dorrit Editor."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ModelConfig:
    """Configuration for a model."""

    endpoint: str  # Base URL for the API
    model_name: str  # Technical model name
    api_key: str  # API key
    logical_name: str  # Human-readable name


class ConfigManager:
    """Manager for loading and accessing configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file. If None, uses default path.
        """
        root_dir = Path(__file__).parent.parent

        # Use provided config path or default to models.toml
        self.config_path = config_path or (root_dir / "config" / "models.toml")
        self._models: Dict[str, ModelConfig] = {}
        self._load_config()

    def _load_config(self, config_path: Optional[Path] = None) -> None:
        """Load configuration from the TOML file.

        Args:
            config_path: Path to the configuration file. If None, uses the default path.
        """
        path_to_load = config_path or self.config_path

        if not path_to_load.exists():
            if config_path is None:
                # Only raise an error if this is the main config file
                raise FileNotFoundError(f"Configuration file not found: {path_to_load}")
            return

        with open(path_to_load, "rb") as f:
            config = tomllib.load(f)

        for model_id, model_config in config.items():
            # Process API key
            if "api_key" in model_config:
                api_key = model_config["api_key"]
                if api_key.startswith("${") and api_key.endswith("}"):
                    env_var = api_key[2:-1]
                    api_key = os.environ.get(env_var, "")
                    if not api_key:
                        print(f"Warning: Environment variable {env_var} not set for model {model_id}")
            else:
                api_key = ""

            # Load required fields
            endpoint = model_config["endpoint"]
            model_name = model_config["model_name"]
            logical_name = model_config["logical_name"]

            # Create the model configuration
            self._models[model_id] = ModelConfig(
                endpoint=endpoint,
                model_name=model_name,
                api_key=api_key,
                logical_name=logical_name,
            )

    def get_model(self, model_id: str) -> ModelConfig:
        """Get configuration for a specific model.

        Args:
            model_id: The identifier of the model in the configuration.

        Returns:
            The model configuration.

        Raises:
            KeyError: If the model ID is not found in the configuration.
        """
        if model_id not in self._models:
            raise KeyError(f"Model not found in configuration: {model_id}")

        return self._models[model_id]

    def list_models(self) -> Dict[str, str]:
        """List all available models.

        Returns:
            Dictionary mapping model IDs to their logical names.
        """
        return {model_id: config.logical_name for model_id, config in self._models.items()}


# Create a singleton instance for easy imports
config_manager = ConfigManager()


def get_model(model_id: str) -> ModelConfig:
    """Get configuration for a specific model.

    Args:
        model_id: The identifier of the model in the configuration.

    Returns:
        The model configuration.

    Raises:
        KeyError: If the model ID is not found in the configuration.
    """
    return config_manager.get_model(model_id)


def list_models() -> Dict[str, str]:
    """List all available models.

    Returns:
        Dictionary mapping model IDs to their logical names.
    """
    return config_manager.list_models()