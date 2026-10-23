"""OSS Framework Utilities Library.

Provides reusable components for education analytics data processing:
- Data transformations (JSON flattening, normalization, pseudonymization)
- Batch processing (delta, additive, snapshot modes)
- Metadata management (schema, privacy rules, configurations)
- Quality checks and validation

Quick Start:
    from oss_framework import DataTransformer, Pseudonymizer, MetadataManager
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
