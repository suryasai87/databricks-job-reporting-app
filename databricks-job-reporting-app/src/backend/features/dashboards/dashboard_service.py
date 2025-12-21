"""
Dashboard Service for Databricks Jobs Monitor.

Provides comprehensive dashboard management including:
- Widget configuration and data fetching
- Dashboard CRUD operations
- Built-in dashboard templates
- Real-time metric aggregation
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List, Callable

from data.data_layer import get_data_layer

logger = logging.getLogger(__name__)


class WidgetType(Enum):
    """Types of dashboard widgets."""
    METRIC_CARD = "metric_card"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    SPARKLINE = "sparkline"
    STATUS_LIST = "status_list"
    AREA_CHART = "area_chart"


@dataclass
class WidgetConfig:
    """Configuration for a dashboard widget."""
    id: str
    type: WidgetType
    title: str
    data_source: str  # Name of the data source function
    position: Dict[str, int]  # x, y, width, height in grid units
    config: Dict[str, Any] = field(default_factory=dict)  # Widget-specific config
    filters: Dict[str, Any] = field(default_factory=dict)  # Data filters
    refresh_interval: int = 60  # Seconds between auto-refresh

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "data_source": self.data_source,
            "position": self.position,
            "config": self.config,
            "filters": self.filters,
            "refresh_interval": self.refresh_interval,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WidgetConfig":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=WidgetType(data["type"]),
            title=data["title"],
            data_source=data["data_source"],
            position=data["position"],
            config=data.get("config", {}),
            filters=data.get("filters", {}),
            refresh_interval=data.get("refresh_interval", 60),
        )


@dataclass
class Dashboard:
    """Dashboard configuration and metadata."""
    id: str
    name: str
    description: str
    owner: str
    widgets: List[WidgetConfig]
    is_public: bool = False
    is_template: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    layout: Dict[str, Any] = field(default_factory=lambda: {"columns": 12, "row_height": 80})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "widgets": [w.to_dict() for w in self.widgets],
            "is_public": self.is_public,
            "is_template": self.is_template,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "layout": self.layout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Dashboard":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            owner=data["owner"],
            widgets=[WidgetConfig.from_dict(w) for w in data["widgets"]],
            is_public=data.get("is_public", False),
            is_template=data.get("is_template", False),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow()),
            updated_at=datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else data.get("updated_at", datetime.utcnow()),
            tags=data.get("tags", []),
            layout=data.get("layout", {"columns": 12, "row_height": 80}),
        )


class DashboardService:
    """
    Service for managing custom dashboards.

    Handles dashboard CRUD operations, widget data fetching,
    and provides built-in data sources for common metrics.
    """

    # Schema and table names
    CONFIG_SCHEMA = "jobs_monitor.config"
    DASHBOARDS_TABLE = "jobs_monitor.config.dashboards"

    def __init__(self):
        """Initialize dashboard service."""
        self._data_layer = get_data_layer()
        self._data_sources: Dict[str, Callable] = {
            "active_jobs_count": self._get_active_jobs_count,
            "success_rate": self._get_success_rate,
            "cost_24h": self._get_cost_24h,
            "failed_count": self._get_failed_count,
            "run_trend_7d": self._get_run_trend_7d,
            "cost_by_owner": self._get_cost_by_owner,
            "recent_failures": self._get_recent_failures,
            "running_jobs": self._get_running_jobs,
            "avg_duration": self._get_avg_duration,
            "job_status_distribution": self._get_job_status_distribution,
            "top_expensive_jobs": self._get_top_expensive_jobs,
            "hourly_run_heatmap": self._get_hourly_run_heatmap,
        }

    def _ensure_table_exists(self) -> None:
        """Ensure the dashboards configuration table exists."""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.DASHBOARDS_TABLE} (
            id STRING NOT NULL,
            name STRING NOT NULL,
            description STRING,
            owner STRING NOT NULL,
            config STRING NOT NULL,
            is_public BOOLEAN DEFAULT FALSE,
            is_template BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags ARRAY<STRING>,
            PRIMARY KEY (id)
        )
        USING DELTA
        """
        try:
            self._data_layer.query(create_table_sql, force_warehouse=True)
            logger.info(f"Ensured dashboards table exists: {self.DASHBOARDS_TABLE}")
        except Exception as e:
            logger.warning(f"Could not create dashboards table (may already exist): {e}")

    # =========================================================================
    # Dashboard CRUD Operations
    # =========================================================================

    def create_dashboard(self, dashboard: Dashboard) -> Dashboard:
        """
        Create a new dashboard.

        Args:
            dashboard: Dashboard configuration to create

        Returns:
            Created dashboard with generated ID
        """
        if not dashboard.id:
            dashboard.id = str(uuid.uuid4())

        dashboard.created_at = datetime.utcnow()
        dashboard.updated_at = datetime.utcnow()

        config_json = json.dumps(dashboard.to_dict())
        tags_sql = "ARRAY(" + ", ".join(f"'{tag}'" for tag in dashboard.tags) + ")" if dashboard.tags else "ARRAY()"

        insert_sql = f"""
        INSERT INTO {self.DASHBOARDS_TABLE}
        (id, name, description, owner, config, is_public, is_template, created_at, updated_at, tags)
        VALUES (
            '{dashboard.id}',
            '{dashboard.name.replace("'", "''")}',
            '{dashboard.description.replace("'", "''")}',
            '{dashboard.owner}',
            '{config_json.replace("'", "''")}',
            {str(dashboard.is_public).lower()},
            {str(dashboard.is_template).lower()},
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            {tags_sql}
        )
        """

        try:
            self._data_layer.query(insert_sql, force_warehouse=True)
            logger.info(f"Created dashboard: {dashboard.id} - {dashboard.name}")
            return dashboard
        except Exception as e:
            logger.error(f"Failed to create dashboard: {e}")
            raise

    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """
        Get a dashboard by ID.

        Args:
            dashboard_id: Dashboard ID to retrieve

        Returns:
            Dashboard if found, None otherwise
        """
        query = f"""
        SELECT config
        FROM {self.DASHBOARDS_TABLE}
        WHERE id = '{dashboard_id}'
        """

        try:
            results = self._data_layer.query(query)
            if results:
                config = json.loads(results[0]["config"])
                return Dashboard.from_dict(config)
            return None
        except Exception as e:
            logger.error(f"Failed to get dashboard {dashboard_id}: {e}")
            return None

    def list_dashboards(
        self,
        user: Optional[str] = None,
        include_public: bool = True,
        include_templates: bool = False,
        tags: Optional[List[str]] = None
    ) -> List[Dashboard]:
        """
        List available dashboards for a user.

        Args:
            user: Filter by owner (None for all)
            include_public: Include public dashboards
            include_templates: Include template dashboards
            tags: Filter by tags

        Returns:
            List of matching dashboards
        """
        conditions = []

        if user:
            user_condition = f"owner = '{user}'"
            if include_public:
                user_condition = f"({user_condition} OR is_public = true)"
            conditions.append(user_condition)

        if not include_templates:
            conditions.append("is_template = false")

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT config
        FROM {self.DASHBOARDS_TABLE}
        {where_clause}
        ORDER BY updated_at DESC
        """

        try:
            results = self._data_layer.query(query)
            dashboards = []
            for row in results:
                config = json.loads(row["config"])
                dashboard = Dashboard.from_dict(config)

                # Filter by tags if specified
                if tags:
                    if not any(tag in dashboard.tags for tag in tags):
                        continue

                dashboards.append(dashboard)

            return dashboards
        except Exception as e:
            logger.error(f"Failed to list dashboards: {e}")
            return []

    def update_dashboard(self, dashboard_id: str, updates: Dict[str, Any]) -> Optional[Dashboard]:
        """
        Update an existing dashboard.

        Args:
            dashboard_id: Dashboard ID to update
            updates: Dictionary of fields to update

        Returns:
            Updated dashboard if successful
        """
        existing = self.get_dashboard(dashboard_id)
        if not existing:
            logger.warning(f"Dashboard not found: {dashboard_id}")
            return None

        # Apply updates
        dashboard_dict = existing.to_dict()
        for key, value in updates.items():
            if key in dashboard_dict and key not in ["id", "created_at"]:
                dashboard_dict[key] = value

        dashboard_dict["updated_at"] = datetime.utcnow().isoformat()

        # Handle widget updates specially
        if "widgets" in updates:
            dashboard_dict["widgets"] = [
                w if isinstance(w, dict) else w.to_dict()
                for w in updates["widgets"]
            ]

        config_json = json.dumps(dashboard_dict)

        update_sql = f"""
        UPDATE {self.DASHBOARDS_TABLE}
        SET config = '{config_json.replace("'", "''")}',
            name = '{dashboard_dict["name"].replace("'", "''")}',
            description = '{dashboard_dict["description"].replace("'", "''")}',
            is_public = {str(dashboard_dict["is_public"]).lower()},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = '{dashboard_id}'
        """

        try:
            self._data_layer.query(update_sql, force_warehouse=True)
            logger.info(f"Updated dashboard: {dashboard_id}")
            return Dashboard.from_dict(dashboard_dict)
        except Exception as e:
            logger.error(f"Failed to update dashboard: {e}")
            raise

    def delete_dashboard(self, dashboard_id: str) -> bool:
        """
        Delete a dashboard.

        Args:
            dashboard_id: Dashboard ID to delete

        Returns:
            True if deleted successfully
        """
        delete_sql = f"""
        DELETE FROM {self.DASHBOARDS_TABLE}
        WHERE id = '{dashboard_id}'
        """

        try:
            self._data_layer.query(delete_sql, force_warehouse=True)
            logger.info(f"Deleted dashboard: {dashboard_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete dashboard: {e}")
            return False

    # =========================================================================
    # Widget Data Fetching
    # =========================================================================

    def get_widget_data(
        self,
        data_source: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch data for a widget.

        Args:
            data_source: Name of the data source function
            filters: Optional filters to apply

        Returns:
            Widget data in appropriate format
        """
        if data_source not in self._data_sources:
            logger.warning(f"Unknown data source: {data_source}")
            return {"error": f"Unknown data source: {data_source}"}

        try:
            data_func = self._data_sources[data_source]
            return data_func(filters or {})
        except Exception as e:
            logger.error(f"Error fetching widget data for {data_source}: {e}")
            return {"error": str(e)}

    def register_data_source(self, name: str, func: Callable) -> None:
        """Register a custom data source function."""
        self._data_sources[name] = func
        logger.info(f"Registered custom data source: {name}")

    # =========================================================================
    # Built-in Data Sources
    # =========================================================================

    def _get_active_jobs_count(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get count of currently active/running jobs."""
        query = """
        SELECT COUNT(*) as count
        FROM system.lakeflow.job_run_timeline
        WHERE result_state IS NULL
          AND state = 'RUNNING'
        """

        try:
            results = self._data_layer.query(query)
            count = results[0]["count"] if results else 0
            return {
                "value": count,
                "label": "Active Jobs",
                "trend": None,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting active jobs count: {e}")
            return {"value": 0, "error": str(e)}

    def _get_success_rate(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get job success rate for the last 24 hours."""
        hours = filters.get("hours", 24)

        query = f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN result_state = 'SUCCESS' THEN 1 ELSE 0 END) as success_count
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= CURRENT_TIMESTAMP - INTERVAL {hours} HOURS
          AND result_state IS NOT NULL
        """

        try:
            results = self._data_layer.query(query)
            if results and results[0]["total"] > 0:
                total = results[0]["total"]
                success = results[0]["success_count"]
                rate = round((success / total) * 100, 1)
            else:
                rate = 100.0
                total = 0

            return {
                "value": rate,
                "label": "Success Rate",
                "suffix": "%",
                "total_runs": total,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting success rate: {e}")
            return {"value": 0, "error": str(e)}

    def _get_cost_24h(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get total job costs for the last 24 hours."""
        query = """
        SELECT COALESCE(SUM(usage_quantity * pricing.default), 0) as total_cost
        FROM system.billing.usage u
        LEFT JOIN system.billing.list_prices pricing
            ON u.sku_name = pricing.sku_name
        WHERE usage_date >= CURRENT_DATE - INTERVAL 1 DAY
          AND u.usage_metadata.job_id IS NOT NULL
        """

        try:
            results = self._data_layer.query(query)
            cost = results[0]["total_cost"] if results else 0
            return {
                "value": round(float(cost), 2),
                "label": "24h Cost",
                "prefix": "$",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting 24h cost: {e}")
            return {"value": 0, "error": str(e)}

    def _get_failed_count(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get count of failed job runs in the last 24 hours."""
        hours = filters.get("hours", 24)

        query = f"""
        SELECT COUNT(*) as count
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= CURRENT_TIMESTAMP - INTERVAL {hours} HOURS
          AND result_state IN ('FAILED', 'TIMEDOUT', 'CANCELED')
        """

        try:
            results = self._data_layer.query(query)
            count = results[0]["count"] if results else 0
            return {
                "value": count,
                "label": "Failed Jobs",
                "severity": "error" if count > 0 else "success",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting failed count: {e}")
            return {"value": 0, "error": str(e)}

    def _get_run_trend_7d(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get job run trends for the last 7 days."""
        query = """
        SELECT
            DATE(period_start_time) as run_date,
            COUNT(*) as total_runs,
            SUM(CASE WHEN result_state = 'SUCCESS' THEN 1 ELSE 0 END) as success_runs,
            SUM(CASE WHEN result_state IN ('FAILED', 'TIMEDOUT') THEN 1 ELSE 0 END) as failed_runs
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= CURRENT_TIMESTAMP - INTERVAL 7 DAYS
          AND result_state IS NOT NULL
        GROUP BY DATE(period_start_time)
        ORDER BY run_date
        """

        try:
            results = self._data_layer.query(query)
            return {
                "data": [
                    {
                        "date": str(r["run_date"]),
                        "total": r["total_runs"],
                        "success": r["success_runs"],
                        "failed": r["failed_runs"],
                    }
                    for r in results
                ],
                "label": "7-Day Run Trend",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting run trend: {e}")
            return {"data": [], "error": str(e)}

    def _get_cost_by_owner(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get cost breakdown by job owner."""
        limit = filters.get("limit", 10)

        query = f"""
        SELECT
            j.creator_user_name as owner,
            COALESCE(SUM(u.usage_quantity * p.default), 0) as total_cost
        FROM system.lakeflow.jobs j
        JOIN system.billing.usage u
            ON j.job_id = u.usage_metadata.job_id
        LEFT JOIN system.billing.list_prices p
            ON u.sku_name = p.sku_name
        WHERE u.usage_date >= CURRENT_DATE - INTERVAL 7 DAYS
          AND j.delete_time IS NULL
        GROUP BY j.creator_user_name
        ORDER BY total_cost DESC
        LIMIT {limit}
        """

        try:
            results = self._data_layer.query(query)
            return {
                "data": [
                    {"owner": r["owner"] or "Unknown", "cost": round(float(r["total_cost"]), 2)}
                    for r in results
                ],
                "label": "Cost by Owner",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting cost by owner: {e}")
            return {"data": [], "error": str(e)}

    def _get_recent_failures(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent job failures with details."""
        limit = filters.get("limit", 10)

        query = f"""
        SELECT
            j.name as job_name,
            jrt.job_id,
            jrt.run_id,
            jrt.result_state,
            jrt.period_start_time as start_time,
            jrt.period_end_time as end_time,
            j.creator_user_name as owner
        FROM system.lakeflow.job_run_timeline jrt
        JOIN system.lakeflow.jobs j ON jrt.job_id = j.job_id
        WHERE jrt.result_state IN ('FAILED', 'TIMEDOUT', 'CANCELED')
          AND jrt.period_start_time >= CURRENT_TIMESTAMP - INTERVAL 24 HOURS
        ORDER BY jrt.period_start_time DESC
        LIMIT {limit}
        """

        try:
            results = self._data_layer.query(query)
            return {
                "data": [
                    {
                        "job_name": r["job_name"],
                        "job_id": str(r["job_id"]),
                        "run_id": str(r["run_id"]),
                        "result_state": r["result_state"],
                        "start_time": str(r["start_time"]),
                        "owner": r["owner"] or "Unknown",
                    }
                    for r in results
                ],
                "label": "Recent Failures",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting recent failures: {e}")
            return {"data": [], "error": str(e)}

    def _get_running_jobs(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get currently running jobs."""
        limit = filters.get("limit", 20)

        query = f"""
        SELECT
            j.name as job_name,
            jrt.job_id,
            jrt.run_id,
            jrt.state,
            jrt.period_start_time as start_time,
            TIMESTAMPDIFF(MINUTE, jrt.period_start_time, CURRENT_TIMESTAMP) as duration_minutes,
            j.creator_user_name as owner
        FROM system.lakeflow.job_run_timeline jrt
        JOIN system.lakeflow.jobs j ON jrt.job_id = j.job_id
        WHERE jrt.result_state IS NULL
          AND jrt.state = 'RUNNING'
        ORDER BY jrt.period_start_time DESC
        LIMIT {limit}
        """

        try:
            results = self._data_layer.query(query)
            return {
                "data": [
                    {
                        "job_name": r["job_name"],
                        "job_id": str(r["job_id"]),
                        "run_id": str(r["run_id"]),
                        "state": r["state"],
                        "start_time": str(r["start_time"]),
                        "duration_minutes": r["duration_minutes"],
                        "owner": r["owner"] or "Unknown",
                    }
                    for r in results
                ],
                "label": "Running Jobs",
                "count": len(results),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting running jobs: {e}")
            return {"data": [], "error": str(e)}

    def _get_avg_duration(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get average job duration."""
        hours = filters.get("hours", 24)

        query = f"""
        SELECT AVG(
            TIMESTAMPDIFF(SECOND, period_start_time, period_end_time)
        ) as avg_duration_seconds
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= CURRENT_TIMESTAMP - INTERVAL {hours} HOURS
          AND result_state IS NOT NULL
          AND period_end_time IS NOT NULL
        """

        try:
            results = self._data_layer.query(query)
            avg_seconds = results[0]["avg_duration_seconds"] if results and results[0]["avg_duration_seconds"] else 0
            avg_minutes = round(float(avg_seconds) / 60, 1)

            return {
                "value": avg_minutes,
                "label": "Avg Duration",
                "suffix": " min",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting avg duration: {e}")
            return {"value": 0, "error": str(e)}

    def _get_job_status_distribution(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get distribution of job result states."""
        hours = filters.get("hours", 24)

        query = f"""
        SELECT
            result_state,
            COUNT(*) as count
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= CURRENT_TIMESTAMP - INTERVAL {hours} HOURS
          AND result_state IS NOT NULL
        GROUP BY result_state
        """

        try:
            results = self._data_layer.query(query)
            return {
                "data": [
                    {"status": r["result_state"], "count": r["count"]}
                    for r in results
                ],
                "label": "Status Distribution",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting status distribution: {e}")
            return {"data": [], "error": str(e)}

    def _get_top_expensive_jobs(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get top jobs by cost."""
        limit = filters.get("limit", 10)
        days = filters.get("days", 7)

        query = f"""
        SELECT
            j.name as job_name,
            j.job_id,
            j.creator_user_name as owner,
            COALESCE(SUM(u.usage_quantity * p.default), 0) as total_cost,
            COUNT(DISTINCT u.usage_date) as days_active
        FROM system.lakeflow.jobs j
        JOIN system.billing.usage u
            ON j.job_id = u.usage_metadata.job_id
        LEFT JOIN system.billing.list_prices p
            ON u.sku_name = p.sku_name
        WHERE u.usage_date >= CURRENT_DATE - INTERVAL {days} DAYS
          AND j.delete_time IS NULL
        GROUP BY j.name, j.job_id, j.creator_user_name
        ORDER BY total_cost DESC
        LIMIT {limit}
        """

        try:
            results = self._data_layer.query(query)
            return {
                "data": [
                    {
                        "job_name": r["job_name"],
                        "job_id": str(r["job_id"]),
                        "owner": r["owner"] or "Unknown",
                        "cost": round(float(r["total_cost"]), 2),
                        "days_active": r["days_active"],
                    }
                    for r in results
                ],
                "label": "Top Expensive Jobs",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting top expensive jobs: {e}")
            return {"data": [], "error": str(e)}

    def _get_hourly_run_heatmap(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get hourly job run counts for heatmap visualization."""
        days = filters.get("days", 7)

        query = f"""
        SELECT
            DAYOFWEEK(period_start_time) as day_of_week,
            HOUR(period_start_time) as hour_of_day,
            COUNT(*) as run_count
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= CURRENT_TIMESTAMP - INTERVAL {days} DAYS
        GROUP BY DAYOFWEEK(period_start_time), HOUR(period_start_time)
        ORDER BY day_of_week, hour_of_day
        """

        try:
            results = self._data_layer.query(query)

            # Build heatmap matrix
            heatmap = [[0 for _ in range(24)] for _ in range(7)]
            for r in results:
                day = r["day_of_week"] - 1  # Convert to 0-indexed
                hour = r["hour_of_day"]
                heatmap[day][hour] = r["run_count"]

            return {
                "data": heatmap,
                "days": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                "hours": list(range(24)),
                "label": "Run Heatmap",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting hourly heatmap: {e}")
            return {"data": [], "error": str(e)}


# =============================================================================
# Dashboard Templates
# =============================================================================

DASHBOARD_TEMPLATES: Dict[str, Dashboard] = {
    "executive": Dashboard(
        id="template-executive",
        name="Executive Overview",
        description="High-level metrics for executive stakeholders",
        owner="system",
        is_template=True,
        is_public=True,
        tags=["template", "executive", "overview"],
        widgets=[
            WidgetConfig(
                id="exec-1",
                type=WidgetType.METRIC_CARD,
                title="Active Jobs",
                data_source="active_jobs_count",
                position={"x": 0, "y": 0, "width": 3, "height": 2},
            ),
            WidgetConfig(
                id="exec-2",
                type=WidgetType.METRIC_CARD,
                title="Success Rate",
                data_source="success_rate",
                position={"x": 3, "y": 0, "width": 3, "height": 2},
                config={"color": "success"},
            ),
            WidgetConfig(
                id="exec-3",
                type=WidgetType.METRIC_CARD,
                title="24h Cost",
                data_source="cost_24h",
                position={"x": 6, "y": 0, "width": 3, "height": 2},
                config={"color": "info"},
            ),
            WidgetConfig(
                id="exec-4",
                type=WidgetType.METRIC_CARD,
                title="Failed Jobs",
                data_source="failed_count",
                position={"x": 9, "y": 0, "width": 3, "height": 2},
                config={"color": "error"},
            ),
            WidgetConfig(
                id="exec-5",
                type=WidgetType.LINE_CHART,
                title="7-Day Run Trend",
                data_source="run_trend_7d",
                position={"x": 0, "y": 2, "width": 8, "height": 4},
            ),
            WidgetConfig(
                id="exec-6",
                type=WidgetType.PIE_CHART,
                title="Status Distribution",
                data_source="job_status_distribution",
                position={"x": 8, "y": 2, "width": 4, "height": 4},
            ),
        ],
    ),
    "operations": Dashboard(
        id="template-operations",
        name="Operations Dashboard",
        description="Real-time operational monitoring",
        owner="system",
        is_template=True,
        is_public=True,
        tags=["template", "operations", "monitoring"],
        widgets=[
            WidgetConfig(
                id="ops-1",
                type=WidgetType.TABLE,
                title="Running Jobs",
                data_source="running_jobs",
                position={"x": 0, "y": 0, "width": 8, "height": 4},
                config={"columns": ["job_name", "owner", "duration_minutes", "state"]},
                refresh_interval=30,
            ),
            WidgetConfig(
                id="ops-2",
                type=WidgetType.METRIC_CARD,
                title="Active Jobs",
                data_source="active_jobs_count",
                position={"x": 8, "y": 0, "width": 4, "height": 2},
                refresh_interval=30,
            ),
            WidgetConfig(
                id="ops-3",
                type=WidgetType.METRIC_CARD,
                title="Avg Duration",
                data_source="avg_duration",
                position={"x": 8, "y": 2, "width": 4, "height": 2},
            ),
            WidgetConfig(
                id="ops-4",
                type=WidgetType.TABLE,
                title="Recent Failures",
                data_source="recent_failures",
                position={"x": 0, "y": 4, "width": 12, "height": 4},
                config={"columns": ["job_name", "result_state", "start_time", "owner"]},
            ),
            WidgetConfig(
                id="ops-5",
                type=WidgetType.HEATMAP,
                title="Run Activity Heatmap",
                data_source="hourly_run_heatmap",
                position={"x": 0, "y": 8, "width": 12, "height": 4},
            ),
        ],
    ),
    "cost_analysis": Dashboard(
        id="template-cost-analysis",
        name="Cost Analysis",
        description="Detailed cost breakdown and analysis",
        owner="system",
        is_template=True,
        is_public=True,
        tags=["template", "cost", "finance"],
        widgets=[
            WidgetConfig(
                id="cost-1",
                type=WidgetType.METRIC_CARD,
                title="24h Cost",
                data_source="cost_24h",
                position={"x": 0, "y": 0, "width": 4, "height": 2},
                config={"color": "primary"},
            ),
            WidgetConfig(
                id="cost-2",
                type=WidgetType.BAR_CHART,
                title="Cost by Owner",
                data_source="cost_by_owner",
                position={"x": 0, "y": 2, "width": 6, "height": 4},
                config={"orientation": "horizontal"},
            ),
            WidgetConfig(
                id="cost-3",
                type=WidgetType.TABLE,
                title="Top Expensive Jobs",
                data_source="top_expensive_jobs",
                position={"x": 6, "y": 2, "width": 6, "height": 4},
                config={"columns": ["job_name", "owner", "cost", "days_active"]},
                filters={"limit": 10, "days": 7},
            ),
            WidgetConfig(
                id="cost-4",
                type=WidgetType.LINE_CHART,
                title="Cost Trend",
                data_source="run_trend_7d",
                position={"x": 0, "y": 6, "width": 12, "height": 4},
            ),
        ],
    ),
}


# =============================================================================
# Singleton Access
# =============================================================================

_dashboard_service: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    """Get or create the singleton dashboard service."""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
