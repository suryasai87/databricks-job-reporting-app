"""
Databricks Jobs Monitor - Setup Package

This package provides one-time setup scripts for:
- Lakebase instance creation and synced tables
- OTEL metrics Delta tables
"""

from .lakebase_setup import (
    setup_lakebase_for_jobs_monitor,
    get_lakebase_connection_string,
)

__all__ = [
    "setup_lakebase_for_jobs_monitor",
    "get_lakebase_connection_string",
]
