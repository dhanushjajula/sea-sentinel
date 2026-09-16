"""Configuration loader for Sea Sentinel backend."""
import os
import yaml
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

def load_yaml_config(config_name: str) -> Dict[str, Any]:
    """Loads a YAML configuration file from configs/ directory."""
    candidates = [
        PROJECT_ROOT / "configs" / config_name,
        PROJECT_ROOT / "backend" / "configs" / config_name
    ]
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}

def get_pipeline_config() -> Dict[str, Any]:
    return load_yaml_config("pipeline_config.yaml")

def get_system_config() -> Dict[str, Any]:
    return load_yaml_config("system_config.yaml")
