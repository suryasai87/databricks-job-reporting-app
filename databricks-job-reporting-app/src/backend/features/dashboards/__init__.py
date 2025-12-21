"""
Custom Dashboards feature for Databricks Jobs Monitor.

Provides customizable dashboards with configurable widgets
for monitoring job metrics, costs, and performance.
"""

from .dashboard_service import (
    WidgetType,
    WidgetConfig,
    Dashboard,
    DashboardService,
    DASHBOARD_TEMPLATES,
    get_dashboard_service,
)

__all__ = [
    "WidgetType",
    "WidgetConfig",
    "Dashboard",
    "DashboardService",
    "DASHBOARD_TEMPLATES",
    "get_dashboard_service",
]
