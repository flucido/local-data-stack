"""
OSS Framework Utilities Library

Provides reusable components for education analytics data processing:
- Data transformations (JSON flattening, normalization, pseudonymization)
- Batch processing (delta, additive, snapshot modes)
- Metadata management (schema, privacy rules, configurations)
- Quality checks and validation

Quick Start:
    from oss_framework import DataTransformer, Pseudonymizer, MetadataManager

    # Flatten JSON data
    flattened = DataTransformer.flatten_json({'user': {'name': 'John'}})

    # Apply privacy rules
    pseudo = Pseudonymizer(salt="your_salt")
    hashed = pseudo.hash_value("student123")

    # Load metadata
    metadata = MetadataManager("path/to/metadata.csv")
    rules = metadata.get_privacy_rules("students")
"""

from .batch_processing import BatchProcessor, DataQualityChecker
from .data_transformations import (
    DataTransformer,
    EngagementAggregator,
    Pseudonymizer,
    SchemaValidator,
)
from .metadata_management import ConfigurationManager, DataDictionary, MetadataManager

__version__ = "1.0.0"

__all__ = [
    "DataTransformer",
    "EngagementAggregator",
    "Pseudonymizer",
    "SchemaValidator",
    "BatchProcessor",
    "DataQualityChecker",
    "MetadataManager",
    "DataDictionary",
    "ConfigurationManager",
]
