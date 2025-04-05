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
    
    def __init__(self, config_path: Optional[Path] = None, load_local: bool = True):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default path.
            load_local: Whether to load local configuration files.
        """
        root_dir = Path(__file__).parent.parent
        
        if config_path is None:
            # Default path is in the project root
            config_path = root_dir / "config" / "models.toml"
        
        self.config_path = config_path
        self._models: Dict[str, ModelConfig] = {}
        self._load_config()
        
        # Load local configuration if available
        if load_local:
            # Try to load models.local.toml which is git-ignored for API keys
            local_config_path = root_dir / "config" / "models.local.toml"
            if local_config_path.exists():
                self._load_config(local_config_path)
                
            # Also try to load any local*.toml files
            for local_file in (root_dir / "config").glob("local*.toml"):
                if local_file != local_config_path:  # Avoid loading the same file twice
                    self._load_config(local_file)
    
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
            is_override = False
            existing_config = None
            
            # Check if this is overriding an existing model
            if ":" in model_id:
                # Format: "local:gpt-4o" means override the "gpt-4o" configuration
                prefix, original_id = model_id.split(":", 1)
                if original_id in self._models:
                    is_override = True
                    existing_config = self._models[original_id]
                    # Override will be stored with the original model ID
                    model_id = original_id
            
            # Process API key
            if "api_key" in model_config:
                api_key = model_config["api_key"]
                if api_key.startswith("${") and api_key.endswith("}"):
                    env_var = api_key[2:-1]
                    api_key = os.environ.get(env_var, "")
                    if not api_key:
                        print(f"Warning: Environment variable {env_var} not set for model {model_id}")
            else:
                # If no API key is defined, use the existing one (for overrides)
                api_key = existing_config.api_key if existing_config else ""
            
            # For overrides, use values from the original config unless specified
            if is_override:
                endpoint = model_config.get("endpoint", existing_config.endpoint)
                model_name = model_config.get("model_name", existing_config.model_name)
                logical_name = model_config.get("logical_name", existing_config.logical_name)
            else:
                endpoint = model_config["endpoint"]
                model_name = model_config["model_name"]
                logical_name = model_config["logical_name"]
            
            # Create or update the model configuration
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