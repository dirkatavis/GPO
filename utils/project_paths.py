"""
Project paths utility.

Provides centralized path management for configuration and other resources.
"""

import os
import json


class ProjectPaths:
    """Centralized path management."""
    
    @staticmethod
    def get_project_root():
        """Get the project root directory."""
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    @staticmethod
    def get_config_path():
        """Get the path to the config file."""
        return os.path.join(ProjectPaths.get_project_root(), "config.json")
    
    @staticmethod
    def get_data_path():
        """Get the path to the data directory."""
        return os.path.join(ProjectPaths.get_project_root(), "data")
