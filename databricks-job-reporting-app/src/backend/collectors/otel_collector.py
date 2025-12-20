"""
OpenTelemetry (OTEL) Collector for Databricks Job Monitoring

This module provides functionality to check for and collect OTEL metrics
from Databricks environments, including status checks and metric queries.
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class OTELStatus:
    """
    Status of OpenTelemetry integration in the Databricks environment.

    Attributes:
        metrics_available: Whether OTEL metrics are available in Delta table
        native_runtime: Whether using Databricks native OTEL runtime support
        init_script_installed: Whether the OTEL init script is installed on clusters
        active_exporters: List of active metric exporters (e.g., 'cloudwatch', 'azure_monitor', 'prometheus')
        last_metric_time: Timestamp of the most recent metric collected
    """
    metrics_available: bool = False
    native_runtime: bool = False
    init_script_installed: bool = False
    active_exporters: List[str] = field(default_factory=list)
    last_metric_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metrics_available": self.metrics_available,
            "native_runtime": self.native_runtime,
            "init_script_installed": self.init_script_installed,
            "active_exporters": self.active_exporters,
            "last_metric_time": self.last_metric_time.isoformat() if self.last_metric_time else None,
        }


class OTELCollector:
    """
    Collector for OpenTelemetry metrics from Databricks environments.

    This collector queries the Delta table `jobs_monitor.metrics.otel_metrics`
    to retrieve OTEL metrics if they are available.

    Usage:
        collector = OTELCollector(workspace_client)
        status = collector.get_status()
        if status.metrics_available:
            metrics = collector.get_metrics(hours=24)
    """

    OTEL_METRICS_TABLE = "jobs_monitor.metrics.otel_metrics"
    OTEL_CONFIG_TABLE = "jobs_monitor.metrics.otel_config"

    def __init__(self, workspace_client: Optional[Any] = None, warehouse_id: Optional[str] = None):
        """
        Initialize the OTEL Collector.

        Args:
            workspace_client: Databricks WorkspaceClient instance
            warehouse_id: SQL Warehouse ID for executing queries
        """
        self.workspace_client = workspace_client
        self.warehouse_id = warehouse_id or os.getenv("WAREHOUSE_ID")
        self._status_cache: Optional[OTELStatus] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minute cache

    def _execute_sql(self, query: str, timeout: str = "60s") -> List[Dict[str, Any]]:
        """
        Execute a SQL query against the Databricks SQL Warehouse.

        Args:
            query: SQL query to execute
            timeout: Query timeout

        Returns:
            List of result rows as dictionaries
        """
        if not self.workspace_client or not self.warehouse_id:
            logger.warning("No workspace client or warehouse ID configured")
            return []

        try:
            from databricks.sdk.service.sql import StatementState

            response = self.workspace_client.statement_execution.execute_statement(
                warehouse_id=self.warehouse_id,
                statement=query,
                wait_timeout=timeout,
            )

            if response.status.state == StatementState.SUCCEEDED:
                if response.result and response.result.data_array:
                    columns = [col.name for col in response.manifest.schema.columns]
                    return [dict(zip(columns, row)) for row in response.result.data_array]
            else:
                logger.warning(f"SQL execution did not succeed: {response.status}")
            return []
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            return []

    def _check_table_exists(self, table_name: str) -> bool:
        """
        Check if a Delta table exists.

        Args:
            table_name: Fully qualified table name (catalog.schema.table)

        Returns:
            True if table exists, False otherwise
        """
        query = f"SHOW TABLES IN {'.'.join(table_name.split('.')[:-1])} LIKE '{table_name.split('.')[-1]}'"
        try:
            results = self._execute_sql(query)
            return len(results) > 0
        except Exception as e:
            logger.debug(f"Table check failed for {table_name}: {e}")
            return False

    def _check_metrics_available(self) -> bool:
        """Check if OTEL metrics table exists and has data."""
        # First check if table exists
        if not self._check_table_exists(self.OTEL_METRICS_TABLE):
            return False

        # Then check if it has recent data
        query = f"""
        SELECT COUNT(*) as cnt
        FROM {self.OTEL_METRICS_TABLE}
        WHERE metric_time >= current_timestamp() - INTERVAL 1 HOUR
        LIMIT 1
        """
        try:
            results = self._execute_sql(query)
            return results and int(results[0].get("cnt", 0)) > 0
        except Exception:
            return False

    def _check_native_runtime(self) -> bool:
        """
        Check if Databricks native OTEL runtime support is enabled.

        This checks for the presence of native OTEL configuration in the
        workspace or cluster settings.
        """
        # Check for native OTEL configuration via system tables or config
        query = """
        SELECT value
        FROM system.workspace.settings
        WHERE key = 'otel.enabled'
        LIMIT 1
        """
        try:
            results = self._execute_sql(query)
            if results and results[0].get("value", "").lower() in ("true", "1", "enabled"):
                return True
        except Exception as e:
            logger.debug(f"Native runtime check failed: {e}")
        return False

    def _check_init_script_installed(self) -> bool:
        """
        Check if the OTEL init script is installed on any clusters.

        Returns True if at least one cluster has the OTEL init script configured.
        """
        if not self.workspace_client:
            return False

        try:
            # List cluster policies or global init scripts
            global_scripts = list(self.workspace_client.global_init_scripts.list())
            for script in global_scripts:
                if script.name and "otel" in script.name.lower():
                    return True
        except Exception as e:
            logger.debug(f"Init script check failed: {e}")

        # Also check the config table if it exists
        if self._check_table_exists(self.OTEL_CONFIG_TABLE):
            query = f"""
            SELECT 1 FROM {self.OTEL_CONFIG_TABLE}
            WHERE config_key = 'init_script_enabled' AND config_value = 'true'
            LIMIT 1
            """
            try:
                results = self._execute_sql(query)
                return len(results) > 0
            except Exception:
                pass

        return False

    def _get_active_exporters(self) -> List[str]:
        """
        Get list of active OTEL exporters.

        Returns:
            List of exporter names (e.g., 'cloudwatch', 'azure_monitor', 'prometheus')
        """
        exporters = []

        # Check from config table if available
        if self._check_table_exists(self.OTEL_CONFIG_TABLE):
            query = f"""
            SELECT config_value
            FROM {self.OTEL_CONFIG_TABLE}
            WHERE config_key = 'active_exporters'
            LIMIT 1
            """
            try:
                results = self._execute_sql(query)
                if results:
                    # Assume comma-separated list
                    value = results[0].get("config_value", "")
                    exporters = [e.strip() for e in value.split(",") if e.strip()]
            except Exception as e:
                logger.debug(f"Failed to get exporters from config: {e}")

        # If no config, try to detect from metrics table
        if not exporters and self._check_table_exists(self.OTEL_METRICS_TABLE):
            query = f"""
            SELECT DISTINCT exporter
            FROM {self.OTEL_METRICS_TABLE}
            WHERE metric_time >= current_timestamp() - INTERVAL 1 HOUR
            """
            try:
                results = self._execute_sql(query)
                exporters = [r.get("exporter") for r in results if r.get("exporter")]
            except Exception as e:
                logger.debug(f"Failed to detect exporters from metrics: {e}")

        return exporters

    def _get_last_metric_time(self) -> Optional[datetime]:
        """Get the timestamp of the most recent metric."""
        if not self._check_table_exists(self.OTEL_METRICS_TABLE):
            return None

        query = f"""
        SELECT MAX(metric_time) as last_time
        FROM {self.OTEL_METRICS_TABLE}
        """
        try:
            results = self._execute_sql(query)
            if results and results[0].get("last_time"):
                last_time = results[0]["last_time"]
                if isinstance(last_time, str):
                    return datetime.fromisoformat(last_time.replace("Z", "+00:00"))
                return last_time
        except Exception as e:
            logger.debug(f"Failed to get last metric time: {e}")
        return None

    def get_status(self, use_cache: bool = True) -> OTELStatus:
        """
        Get the current OTEL integration status.

        Args:
            use_cache: Whether to use cached status (default: True)

        Returns:
            OTELStatus dataclass with current status information
        """
        # Check cache
        if use_cache and self._status_cache and self._cache_time:
            cache_age = (datetime.now() - self._cache_time).total_seconds()
            if cache_age < self._cache_ttl_seconds:
                return self._status_cache

        # Build fresh status
        status = OTELStatus(
            metrics_available=self._check_metrics_available(),
            native_runtime=self._check_native_runtime(),
            init_script_installed=self._check_init_script_installed(),
            active_exporters=self._get_active_exporters(),
            last_metric_time=self._get_last_metric_time(),
        )

        # Update cache
        self._status_cache = status
        self._cache_time = datetime.now()

        return status

    def get_metrics(
        self,
        hours: int = 24,
        metric_names: Optional[List[str]] = None,
        cluster_id: Optional[str] = None,
        job_id: Optional[str] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """
        Query OTEL metrics from the Delta table.

        Args:
            hours: Number of hours of historical data to retrieve
            metric_names: Optional list of specific metric names to filter
            cluster_id: Optional cluster ID to filter metrics
            job_id: Optional job ID to filter metrics
            limit: Maximum number of rows to return

        Returns:
            List of metric records as dictionaries
        """
        status = self.get_status()
        if not status.metrics_available:
            logger.warning("OTEL metrics not available")
            return []

        # Build query with filters
        where_clauses = [f"metric_time >= current_timestamp() - INTERVAL {hours} HOUR"]

        if metric_names:
            names_str = ", ".join([f"'{n}'" for n in metric_names])
            where_clauses.append(f"metric_name IN ({names_str})")

        if cluster_id:
            where_clauses.append(f"cluster_id = '{cluster_id}'")

        if job_id:
            where_clauses.append(f"job_id = '{job_id}'")

        where_clause = " AND ".join(where_clauses)

        query = f"""
        SELECT
            metric_time,
            metric_name,
            metric_value,
            metric_type,
            cluster_id,
            job_id,
            run_id,
            exporter,
            labels
        FROM {self.OTEL_METRICS_TABLE}
        WHERE {where_clause}
        ORDER BY metric_time DESC
        LIMIT {limit}
        """

        return self._execute_sql(query)

    def get_spark_metrics(
        self,
        hours: int = 24,
        cluster_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get Spark-specific metrics from OTEL data.

        This retrieves metrics like executor memory, shuffle read/write,
        and other Spark Prometheus metrics.

        Args:
            hours: Number of hours of historical data
            cluster_id: Optional cluster ID filter

        Returns:
            List of Spark metric records
        """
        spark_metric_names = [
            "spark_executor_memoryUsed_bytes",
            "spark_executor_diskUsed_bytes",
            "spark_executor_totalInputBytes_total",
            "spark_executor_totalShuffleRead_total",
            "spark_executor_totalShuffleWrite_total",
            "spark_executor_totalGCTime_ms",
            "spark_executor_activeTasks",
            "spark_executor_completedTasks_total",
            "spark_executor_failedTasks_total",
            "spark_stage_executorRunTime_ms",
            "spark_job_completedStages",
            "spark_job_activeStages",
        ]

        return self.get_metrics(
            hours=hours,
            metric_names=spark_metric_names,
            cluster_id=cluster_id,
        )

    def get_cluster_metrics_summary(
        self,
        cluster_id: str,
        hours: int = 1,
    ) -> Dict[str, Any]:
        """
        Get a summary of OTEL metrics for a specific cluster.

        Args:
            cluster_id: The cluster ID to get metrics for
            hours: Number of hours of data to summarize

        Returns:
            Dictionary with summarized metrics
        """
        status = self.get_status()
        if not status.metrics_available:
            return {"error": "OTEL metrics not available"}

        query = f"""
        SELECT
            metric_name,
            AVG(metric_value) as avg_value,
            MIN(metric_value) as min_value,
            MAX(metric_value) as max_value,
            COUNT(*) as sample_count
        FROM {self.OTEL_METRICS_TABLE}
        WHERE cluster_id = '{cluster_id}'
            AND metric_time >= current_timestamp() - INTERVAL {hours} HOUR
        GROUP BY metric_name
        """

        results = self._execute_sql(query)

        return {
            "cluster_id": cluster_id,
            "time_range_hours": hours,
            "metrics": {
                r["metric_name"]: {
                    "avg": float(r.get("avg_value", 0) or 0),
                    "min": float(r.get("min_value", 0) or 0),
                    "max": float(r.get("max_value", 0) or 0),
                    "samples": int(r.get("sample_count", 0)),
                }
                for r in results
            },
        }


# Factory function for creating collector instances
def create_otel_collector(
    workspace_client: Optional[Any] = None,
    warehouse_id: Optional[str] = None,
) -> OTELCollector:
    """
    Factory function to create an OTELCollector instance.

    Args:
        workspace_client: Optional WorkspaceClient instance
        warehouse_id: Optional SQL Warehouse ID

    Returns:
        Configured OTELCollector instance
    """
    return OTELCollector(
        workspace_client=workspace_client,
        warehouse_id=warehouse_id,
    )
