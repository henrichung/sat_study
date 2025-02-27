"""
Application configuration module
"""
import os
import json
from pathlib import Path

# Default configuration
DEFAULT_CONFIG = {
    "default_db_path": "data/questions.db",
    "default_output_dir": "output/",
    "recent_databases": [],
    "latex_dpi": 300,
}

CONFIG_FILE = Path.home() / ".sat_study_config.json"

def load_config():
    """Load configuration from file or create default"""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
        
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)