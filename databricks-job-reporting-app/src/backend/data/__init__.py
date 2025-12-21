"""
Databricks Jobs Monitor - Data Layer Package

This package provides unified data access with Lakebase acceleration
and SQL Warehouse fallback for the Jobs Monitor application.
"""

from .data_layer import (
    DataAccessLayer,
    DataSource,
    LakebaseConfig,
    SQLWarehouseConfig,
    get_data_layer,
)

__all__ = [
    "DataAccessLayer",
    "DataSource",
    "LakebaseConfig",
    "SQLWarehouseConfig",
    "get_data_layer",
]
