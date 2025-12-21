"""
Multi-Workspace Support for Databricks Jobs Monitor.

This module provides capabilities to aggregate metrics, alerts, and cost data
across multiple Databricks workspaces for unified monitoring and reporting.
"""

from .workspace_aggregator import (
    # Data classes
    WorkspaceConfig,
    WorkspaceMetrics,
    CrossWorkspaceAlert,
    # Service class
    MultiWorkspaceService,
    # Utility functions
    load_workspace_configs,
    get_multi_workspace_service,
)

__all__ = [
    # Data classes
    "WorkspaceConfig",
    "WorkspaceMetrics",
    "CrossWorkspaceAlert",
    # Service class
    "MultiWorkspaceService",
    # Utility functions
    "load_workspace_configs",
    "get_multi_workspace_service",
]
