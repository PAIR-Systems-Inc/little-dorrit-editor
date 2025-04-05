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
        if config_path is None:
            # Default path is in the project root
            root_dir = Path(__file__).parent.parent
            config_path = root_dir / "config" / "models.toml"
        
        self.config_path = config_path
        self._models: Dict[str, ModelConfig] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from the TOML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, "rb") as f:
            config = tomllib.load(f)
        
        for model_id, model_config in config.items():
            # Process environment variables in the API key
            api_key = model_config["api_key"]
            if api_key.startswith("${") and api_key.endswith("}"):
                env_var = api_key[2:-1]
                api_key = os.environ.get(env_var, "")
                if not api_key:
                    print(f"Warning: Environment variable {env_var} not set for model {model_id}")
            
            # Note: Most providers (including Anthropic and Google) now support an OpenAI-compatible
            # interface, but the endpoint URLs are different. The model config should specify the
            # correct base URL for each provider.
            
            self._models[model_id] = ModelConfig(
                endpoint=model_config["endpoint"],
                model_name=model_config["model_name"],
                api_key=api_key,
                logical_name=model_config["logical_name"],
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