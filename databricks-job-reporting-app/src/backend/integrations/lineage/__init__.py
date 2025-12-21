"""
Unity Catalog Lineage Integration for Databricks Jobs Monitor.

This module provides lineage tracking and visualization capabilities by querying
Unity Catalog's system tables for table lineage and job access patterns.
"""

from .lineage_service import (
    # Data classes
    TableNode,
    JobNode,
    LineageEdge,
    JobLineageResult,
    LineageDirection,
    # Service classes
    LineageService,
    LineageGraphVisualizer,
    # Singleton accessor
    get_lineage_service,
)

__all__ = [
    # Data classes
    "TableNode",
    "JobNode",
    "LineageEdge",
    "JobLineageResult",
    "LineageDirection",
    # Service classes
    "LineageService",
    "LineageGraphVisualizer",
    # Singleton accessor
    "get_lineage_service",
]
