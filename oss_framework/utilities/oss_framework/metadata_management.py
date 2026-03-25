"""
OSS Framework: Metadata Management

Handles schema definitions, privacy rules, and data dictionaries
"""

import pandas as pd
from typing import Dict, List, Optional, Any
import logging
import yaml

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manages metadata schema and privacy rules"""

    def __init__(self, metadata_path: str):
        """
        Initialize metadata manager

        Args:
            metadata_path: Path to metadata CSV file
        """
        self.metadata_path = metadata_path
        self.metadata = self._load_metadata()
        self.entities = self.metadata["Entity"].unique().tolist()

    def _load_metadata(self) -> pd.DataFrame:
        """Load metadata from CSV"""
        try:
            return pd.read_csv(self.metadata_path)
        except FileNotFoundError:
            logger.error(f"Metadata file not found: {self.metadata_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            raise

    def get_entity_schema(self, entity_name: str) -> pd.DataFrame:
        """
        Get schema for a specific entity

        Args:
            entity_name: Name of entity

        Returns:
            DataFrame with entity schema
        """
        return self.metadata[self.metadata["Entity"] == entity_name]

    def get_privacy_rules(self, entity_name: str) -> Dict[str, str]:
        """
        Get privacy rules for an entity

        Args:
            entity_name: Name of entity

        Returns:
            Dictionary mapping attributes to privacy rules
        """
        schema = self.get_entity_schema(entity_name)
        return dict(zip(schema["Attribute"], schema["Pseudonymization"]))

    def get_attributes(self, entity_name: str) -> List[str]:
        """
        Get all attributes for an entity

        Args:
            entity_name: Name of entity

        Returns:
            List of attribute names
        """
        schema = self.get_entity_schema(entity_name)
        return schema["Attribute"].tolist()

    def get_data_types(self, entity_name: str) -> Dict[str, str]:
        """
        Get data types for all attributes of an entity

        Args:
            entity_name: Name of entity

        Returns:
            Dictionary mapping attributes to data types
        """
        schema = self.get_entity_schema(entity_name)
        return dict(zip(schema["Attribute"], schema["DataType"]))

    def get_descriptions(self, entity_name: str) -> Dict[str, str]:
        """
        Get descriptions for all attributes

        Args:
            entity_name: Name of entity

        Returns:
            Dictionary mapping attributes to descriptions
        """
        schema = self.get_entity_schema(entity_name)
        return dict(zip(schema["Attribute"], schema["Description"]))


class DataDictionary:
    """Generate data dictionary documentation"""

    @staticmethod
    def generate_markdown(metadata: pd.DataFrame, entity_name: str) -> str:
        """
        Generate Markdown data dictionary

        Args:
            metadata: Metadata DataFrame
            entity_name: Entity name

        Returns:
            Markdown formatted data dictionary
        """
        schema = metadata[metadata["Entity"] == entity_name]

        if schema.empty:
            return f"No metadata found for entity: {entity_name}"

        md = f"# {entity_name} Data Dictionary\n\n"
        md += "| Attribute | DataType | Pseudonymization | Description |\n"
        md += "|-----------|----------|------------------|-------------|\n"

        for _, row in schema.iterrows():
            md += f"| {row['Attribute']} | {row['DataType']} | {row['Pseudonymization']} | {row['Description']} |\n"

        return md

    @staticmethod
    def generate_html(metadata: pd.DataFrame, entity_name: str) -> str:
        """
        Generate HTML data dictionary

        Args:
            metadata: Metadata DataFrame
            entity_name: Entity name

        Returns:
            HTML formatted data dictionary
        """
        schema = metadata[metadata["Entity"] == entity_name]

        if schema.empty:
            return f"<p>No metadata found for entity: {entity_name}</p>"

        html = f"<h1>{entity_name} Data Dictionary</h1>\n"
        html += "<table border='1'><tr><th>Attribute</th><th>DataType</th><th>Pseudonymization</th><th>Description</th></tr>\n"

        for _, row in schema.iterrows():
            html += f"<tr><td>{row['Attribute']}</td><td>{row['DataType']}</td><td>{row['Pseudonymization']}</td><td>{row['Description']}</td></tr>\n"

        html += "</table>"
        return html


class ConfigurationManager:
    """Manages environment-specific configurations"""

    def __init__(self, config_path: str):
        """
        Initialize configuration manager

        Args:
            config_path: Path to environment configuration file (YAML)
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key (dot notation supported, e.g., 'database.host')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.config.get("database", {})

    def get_pipeline_config(self) -> Dict[str, Any]:
        """Get pipeline configuration"""
        return self.config.get("pipelines", {})

    def get_privacy_config(self) -> Dict[str, Any]:
        """Get privacy configuration"""
        return self.config.get("privacy", {})
