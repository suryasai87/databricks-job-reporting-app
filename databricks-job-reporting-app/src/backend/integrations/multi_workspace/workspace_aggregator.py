"""
Multi-Workspace Aggregator Service for Databricks Jobs Monitor.

Provides unified monitoring, alerting, and cost analysis across multiple
Databricks workspaces with parallel data fetching and graceful error handling.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

# Databricks SDK for workspace API access
try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.jobs import RunLifeCycleState, RunResultState
    DATABRICKS_SDK_AVAILABLE = True
except ImportError:
    DATABRICKS_SDK_AVAILABLE = False
    WorkspaceClient = None

# Databricks SQL for Delta table queries
try:
    from databricks import sql as databricks_sql
    DATABRICKS_SQL_AVAILABLE = True
except ImportError:
    DATABRICKS_SQL_AVAILABLE = False

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Severity levels for cross-workspace alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WorkspaceConfig:
    """Configuration for a Databricks workspace connection."""
    workspace_id: str
    workspace_name: str
    host: str
    token: str
    warehouse_id: Optional[str] = None
    region: Optional[str] = None
    cloud_provider: Optional[str] = None  # aws, azure, gcp
    environment: Optional[str] = None  # dev, staging, prod
    tags: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        if self.environment:
            return f"{self.workspace_name} ({self.environment})"
        return self.workspace_name

    def get_client(self) -> Optional["WorkspaceClient"]:
        """Create a WorkspaceClient for this workspace."""
        if not DATABRICKS_SDK_AVAILABLE:
            logger.error("Databricks SDK not available")
            return None
        try:
            return WorkspaceClient(
                host=self.host,
                token=self.token,
            )
        except Exception as e:
            logger.error(f"Failed to create client for {self.workspace_name}: {e}")
            return None

    def get_sql_connection(self):
        """Create a SQL connection for this workspace."""
        if not DATABRICKS_SQL_AVAILABLE:
            logger.error("Databricks SQL connector not available")
            return None
        if not self.warehouse_id:
            logger.warning(f"No warehouse_id configured for {self.workspace_name}")
            return None

        # Clean host URL
        host = self.host
        if host.startswith("https://"):
            host = host[8:]
        if host.startswith("http://"):
            host = host[7:]

        try:
            return databricks_sql.connect(
                server_hostname=host,
                http_path=f"/sql/1.0/warehouses/{self.warehouse_id}",
                access_token=self.token,
            )
        except Exception as e:
            logger.error(f"Failed to create SQL connection for {self.workspace_name}: {e}")
            return None


@dataclass
class WorkspaceMetrics:
    """Aggregated metrics for a single workspace."""
    workspace_id: str
    workspace_name: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Job metrics
    total_jobs: int = 0
    active_jobs: int = 0
    failed_jobs_24h: int = 0
    successful_jobs_24h: int = 0
    running_jobs: int = 0

    # Performance metrics
    avg_run_duration_minutes: float = 0.0
    p95_run_duration_minutes: float = 0.0

    # Cost metrics
    estimated_dbu_usage_24h: float = 0.0
    estimated_cost_24h: float = 0.0

    # Cluster metrics
    active_clusters: int = 0
    running_clusters: int = 0
    total_cluster_dbus: float = 0.0

    # Health indicators
    success_rate_24h: float = 0.0
    health_score: float = 100.0

    # Connection status
    connected: bool = True
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "timestamp": self.timestamp.isoformat(),
            "total_jobs": self.total_jobs,
            "active_jobs": self.active_jobs,
            "failed_jobs_24h": self.failed_jobs_24h,
            "successful_jobs_24h": self.successful_jobs_24h,
            "running_jobs": self.running_jobs,
            "avg_run_duration_minutes": self.avg_run_duration_minutes,
            "p95_run_duration_minutes": self.p95_run_duration_minutes,
            "estimated_dbu_usage_24h": self.estimated_dbu_usage_24h,
            "estimated_cost_24h": self.estimated_cost_24h,
            "active_clusters": self.active_clusters,
            "running_clusters": self.running_clusters,
            "total_cluster_dbus": self.total_cluster_dbus,
            "success_rate_24h": self.success_rate_24h,
            "health_score": self.health_score,
            "connected": self.connected,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
        }


@dataclass
class CrossWorkspaceAlert:
    """Alert that spans or compares across workspaces."""
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    description: str
    workspace_ids: List[str]
    workspace_names: List[str]

    # Alert details
    alert_type: str  # job_failure, sla_breach, cost_spike, health_degradation
    affected_resources: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Resolution
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "workspace_ids": self.workspace_ids,
            "workspace_names": self.workspace_names,
            "alert_type": self.alert_type,
            "affected_resources": self.affected_resources,
            "metrics": self.metrics,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class MultiWorkspaceService:
    """
    Service for aggregating metrics and alerts across multiple Databricks workspaces.

    Features:
    - Parallel metric fetching from multiple workspaces
    - Unified alerting across workspaces
    - Cost comparison and analysis
    - Graceful error handling for unreachable workspaces
    """

    def __init__(self, workspace_configs: Optional[List[WorkspaceConfig]] = None):
        """
        Initialize the multi-workspace service.

        Args:
            workspace_configs: List of workspace configurations. If None,
                              will attempt to load from Delta table.
        """
        self._configs: Dict[str, WorkspaceConfig] = {}
        self._clients: Dict[str, WorkspaceClient] = {}
        self._last_metrics: Dict[str, WorkspaceMetrics] = {}
        self._alerts: List[CrossWorkspaceAlert] = []

        if workspace_configs:
            for config in workspace_configs:
                if config.enabled:
                    self._configs[config.workspace_id] = config

        logger.info(f"MultiWorkspaceService initialized with {len(self._configs)} workspaces")

    def add_workspace(self, config: WorkspaceConfig) -> bool:
        """
        Add a workspace configuration.

        Args:
            config: Workspace configuration to add.

        Returns:
            True if added successfully, False otherwise.
        """
        if not config.enabled:
            logger.info(f"Workspace {config.workspace_name} is disabled, skipping")
            return False

        self._configs[config.workspace_id] = config
        logger.info(f"Added workspace: {config.workspace_name}")
        return True

    def remove_workspace(self, workspace_id: str) -> bool:
        """Remove a workspace from monitoring."""
        if workspace_id in self._configs:
            del self._configs[workspace_id]
            if workspace_id in self._clients:
                del self._clients[workspace_id]
            if workspace_id in self._last_metrics:
                del self._last_metrics[workspace_id]
            logger.info(f"Removed workspace: {workspace_id}")
            return True
        return False

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """List all configured workspaces."""
        return [
            {
                "workspace_id": config.workspace_id,
                "workspace_name": config.workspace_name,
                "display_name": config.display_name,
                "host": config.host,
                "region": config.region,
                "cloud_provider": config.cloud_provider,
                "environment": config.environment,
                "enabled": config.enabled,
                "has_warehouse": bool(config.warehouse_id),
            }
            for config in self._configs.values()
        ]

    def _get_client(self, workspace_id: str) -> Optional[WorkspaceClient]:
        """Get or create a WorkspaceClient for a workspace."""
        if workspace_id not in self._clients:
            config = self._configs.get(workspace_id)
            if config:
                client = config.get_client()
                if client:
                    self._clients[workspace_id] = client
        return self._clients.get(workspace_id)

    def _fetch_workspace_metrics(self, workspace_id: str) -> WorkspaceMetrics:
        """
        Fetch metrics for a single workspace.

        Args:
            workspace_id: The workspace to fetch metrics for.

        Returns:
            WorkspaceMetrics object with current metrics.
        """
        config = self._configs.get(workspace_id)
        if not config:
            return WorkspaceMetrics(
                workspace_id=workspace_id,
                workspace_name="Unknown",
                connected=False,
                error_message="Workspace not configured",
            )

        metrics = WorkspaceMetrics(
            workspace_id=workspace_id,
            workspace_name=config.workspace_name,
        )

        import time
        start_time = time.time()

        try:
            client = self._get_client(workspace_id)
            if not client:
                metrics.connected = False
                metrics.error_message = "Failed to create workspace client"
                return metrics

            # Fetch job metrics
            try:
                jobs = list(client.jobs.list())
                metrics.total_jobs = len(jobs)
                metrics.active_jobs = sum(1 for j in jobs if hasattr(j, 'settings') and j.settings)

                # Count running jobs
                runs = list(client.jobs.list_runs(active_only=True, limit=100))
                metrics.running_jobs = len(runs)

            except Exception as e:
                logger.warning(f"Error fetching jobs for {config.workspace_name}: {e}")

            # Fetch cluster metrics
            try:
                clusters = list(client.clusters.list())
                metrics.active_clusters = len(clusters)
                metrics.running_clusters = sum(
                    1 for c in clusters
                    if hasattr(c, 'state') and c.state and c.state.value == 'RUNNING'
                )
            except Exception as e:
                logger.warning(f"Error fetching clusters for {config.workspace_name}: {e}")

            # Fetch run history for success rate (last 24 hours)
            try:
                cutoff = datetime.now() - timedelta(hours=24)
                cutoff_ms = int(cutoff.timestamp() * 1000)

                recent_runs = list(client.jobs.list_runs(
                    start_time_from=cutoff_ms,
                    limit=1000,
                ))

                completed_runs = [
                    r for r in recent_runs
                    if hasattr(r, 'state') and r.state and
                    hasattr(r.state, 'life_cycle_state') and
                    r.state.life_cycle_state in [
                        RunLifeCycleState.TERMINATED,
                        RunLifeCycleState.INTERNAL_ERROR,
                        RunLifeCycleState.SKIPPED,
                    ]
                ]

                successful = sum(
                    1 for r in completed_runs
                    if hasattr(r.state, 'result_state') and
                    r.state.result_state == RunResultState.SUCCESS
                )
                failed = sum(
                    1 for r in completed_runs
                    if hasattr(r.state, 'result_state') and
                    r.state.result_state == RunResultState.FAILED
                )

                metrics.successful_jobs_24h = successful
                metrics.failed_jobs_24h = failed

                total_completed = len(completed_runs)
                if total_completed > 0:
                    metrics.success_rate_24h = round((successful / total_completed) * 100, 2)

                # Calculate average run duration
                durations = []
                for r in completed_runs:
                    if (hasattr(r, 'start_time') and hasattr(r, 'end_time') and
                        r.start_time and r.end_time):
                        duration_ms = r.end_time - r.start_time
                        durations.append(duration_ms / 60000)  # Convert to minutes

                if durations:
                    metrics.avg_run_duration_minutes = round(sum(durations) / len(durations), 2)
                    sorted_durations = sorted(durations)
                    p95_idx = int(len(sorted_durations) * 0.95)
                    metrics.p95_run_duration_minutes = round(sorted_durations[p95_idx], 2)

            except Exception as e:
                logger.warning(f"Error fetching run history for {config.workspace_name}: {e}")

            # Calculate health score
            metrics.health_score = self._calculate_health_score(metrics)
            metrics.connected = True
            metrics.latency_ms = round((time.time() - start_time) * 1000, 2)

        except Exception as e:
            logger.error(f"Error fetching metrics for {config.workspace_name}: {e}")
            metrics.connected = False
            metrics.error_message = str(e)
            metrics.latency_ms = round((time.time() - start_time) * 1000, 2)

        # Cache metrics
        self._last_metrics[workspace_id] = metrics

        return metrics

    def _calculate_health_score(self, metrics: WorkspaceMetrics) -> float:
        """
        Calculate a health score (0-100) for a workspace.

        Factors:
        - Success rate (40%)
        - Running jobs vs capacity (20%)
        - Failed jobs count (20%)
        - Cluster health (20%)
        """
        score = 100.0

        # Success rate impact (40%)
        if metrics.success_rate_24h < 100:
            rate_penalty = (100 - metrics.success_rate_24h) * 0.4
            score -= rate_penalty

        # Failed jobs impact (20%)
        if metrics.failed_jobs_24h > 0:
            # Scale penalty: 5 failures = 10% penalty, 20 failures = 20% max
            failure_penalty = min(20, metrics.failed_jobs_24h * 2)
            score -= failure_penalty

        # Cluster health (20%) - basic check
        if metrics.active_clusters > 0 and metrics.running_clusters == 0:
            score -= 10  # Clusters configured but none running

        return max(0, round(score, 2))

    def get_aggregated_metrics(
        self,
        parallel: bool = True,
        timeout_seconds: int = 30,
    ) -> Dict[str, Any]:
        """
        Fetch metrics from all configured workspaces.

        Args:
            parallel: If True, fetch from all workspaces in parallel.
            timeout_seconds: Maximum time to wait for each workspace.

        Returns:
            Dictionary with aggregated metrics and per-workspace breakdown.
        """
        if not self._configs:
            return {
                "success": False,
                "error": "No workspaces configured",
                "workspaces": [],
                "aggregated": {},
            }

        workspace_metrics: List[WorkspaceMetrics] = []

        if parallel and len(self._configs) > 1:
            # Parallel fetching with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(10, len(self._configs))) as executor:
                futures = {
                    executor.submit(self._fetch_workspace_metrics, ws_id): ws_id
                    for ws_id in self._configs.keys()
                }

                for future in as_completed(futures, timeout=timeout_seconds):
                    workspace_id = futures[future]
                    try:
                        metrics = future.result(timeout=timeout_seconds)
                        workspace_metrics.append(metrics)
                    except Exception as e:
                        logger.error(f"Failed to fetch metrics for {workspace_id}: {e}")
                        config = self._configs.get(workspace_id)
                        workspace_metrics.append(WorkspaceMetrics(
                            workspace_id=workspace_id,
                            workspace_name=config.workspace_name if config else "Unknown",
                            connected=False,
                            error_message=str(e),
                        ))
        else:
            # Sequential fetching
            for workspace_id in self._configs.keys():
                metrics = self._fetch_workspace_metrics(workspace_id)
                workspace_metrics.append(metrics)

        # Aggregate metrics
        aggregated = self._aggregate_metrics(workspace_metrics)

        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "workspaces": [m.to_dict() for m in workspace_metrics],
            "aggregated": aggregated,
            "workspace_count": len(workspace_metrics),
            "connected_count": sum(1 for m in workspace_metrics if m.connected),
        }

    def _aggregate_metrics(self, metrics_list: List[WorkspaceMetrics]) -> Dict[str, Any]:
        """Aggregate metrics across all workspaces."""
        if not metrics_list:
            return {}

        connected = [m for m in metrics_list if m.connected]

        if not connected:
            return {
                "total_workspaces": len(metrics_list),
                "connected_workspaces": 0,
                "error": "No workspaces connected",
            }

        return {
            "total_workspaces": len(metrics_list),
            "connected_workspaces": len(connected),
            "total_jobs": sum(m.total_jobs for m in connected),
            "total_active_jobs": sum(m.active_jobs for m in connected),
            "total_running_jobs": sum(m.running_jobs for m in connected),
            "total_failed_24h": sum(m.failed_jobs_24h for m in connected),
            "total_successful_24h": sum(m.successful_jobs_24h for m in connected),
            "total_active_clusters": sum(m.active_clusters for m in connected),
            "total_running_clusters": sum(m.running_clusters for m in connected),
            "avg_success_rate_24h": round(
                sum(m.success_rate_24h for m in connected) / len(connected), 2
            ),
            "avg_health_score": round(
                sum(m.health_score for m in connected) / len(connected), 2
            ),
            "total_estimated_cost_24h": sum(m.estimated_cost_24h for m in connected),
            "total_estimated_dbu_usage_24h": sum(m.estimated_dbu_usage_24h for m in connected),
            "avg_latency_ms": round(
                sum(m.latency_ms or 0 for m in connected) / len(connected), 2
            ),
        }

    def get_cross_workspace_failures(
        self,
        hours: int = 24,
        min_severity: AlertSeverity = AlertSeverity.LOW,
    ) -> List[CrossWorkspaceAlert]:
        """
        Get unified alerts for failures across all workspaces.

        Args:
            hours: Lookback period in hours.
            min_severity: Minimum severity level to include.

        Returns:
            List of CrossWorkspaceAlert objects.
        """
        alerts: List[CrossWorkspaceAlert] = []
        severity_order = [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        min_severity_idx = severity_order.index(min_severity)

        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_ms = int(cutoff.timestamp() * 1000)

        # Collect failures from each workspace
        all_failures: List[Dict[str, Any]] = []

        for workspace_id, config in self._configs.items():
            try:
                client = self._get_client(workspace_id)
                if not client:
                    continue

                runs = list(client.jobs.list_runs(
                    start_time_from=cutoff_ms,
                    limit=500,
                ))

                for run in runs:
                    if (hasattr(run, 'state') and run.state and
                        hasattr(run.state, 'result_state') and
                        run.state.result_state == RunResultState.FAILED):

                        all_failures.append({
                            "workspace_id": workspace_id,
                            "workspace_name": config.workspace_name,
                            "run_id": run.run_id,
                            "job_id": run.job_id,
                            "job_name": getattr(run, 'run_name', f"Job {run.job_id}"),
                            "start_time": run.start_time,
                            "end_time": getattr(run, 'end_time', None),
                            "error_message": getattr(run.state, 'state_message', None),
                        })

            except Exception as e:
                logger.error(f"Error fetching failures for {config.workspace_name}: {e}")

        # Group by job name to find patterns
        from collections import defaultdict
        failures_by_job = defaultdict(list)
        for failure in all_failures:
            failures_by_job[failure["job_name"]].append(failure)

        # Create alerts for repeated failures
        import uuid
        for job_name, failures in failures_by_job.items():
            if len(failures) >= 3:
                severity = AlertSeverity.HIGH
            elif len(failures) >= 2:
                severity = AlertSeverity.MEDIUM
            else:
                severity = AlertSeverity.LOW

            if severity_order.index(severity) < min_severity_idx:
                continue

            workspace_ids = list(set(f["workspace_id"] for f in failures))
            workspace_names = list(set(f["workspace_name"] for f in failures))

            alert = CrossWorkspaceAlert(
                alert_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                severity=severity,
                title=f"Job '{job_name}' failed {len(failures)} times",
                description=f"Job has failed {len(failures)} times across {len(workspace_ids)} workspace(s) in the last {hours} hours.",
                workspace_ids=workspace_ids,
                workspace_names=workspace_names,
                alert_type="job_failure",
                affected_resources=[
                    {
                        "type": "job_run",
                        "run_id": f["run_id"],
                        "job_id": f["job_id"],
                        "workspace_id": f["workspace_id"],
                        "error_message": f["error_message"],
                    }
                    for f in failures
                ],
                metrics={
                    "failure_count": len(failures),
                    "workspace_count": len(workspace_ids),
                    "lookback_hours": hours,
                },
            )
            alerts.append(alert)

        # Check for workspace health degradation
        for workspace_id, metrics in self._last_metrics.items():
            if not metrics.connected:
                severity = AlertSeverity.CRITICAL
                if severity_order.index(severity) >= min_severity_idx:
                    config = self._configs.get(workspace_id)
                    alerts.append(CrossWorkspaceAlert(
                        alert_id=str(uuid.uuid4()),
                        timestamp=datetime.now(),
                        severity=severity,
                        title=f"Workspace '{config.workspace_name}' is unreachable",
                        description=f"Unable to connect to workspace: {metrics.error_message}",
                        workspace_ids=[workspace_id],
                        workspace_names=[config.workspace_name] if config else [workspace_id],
                        alert_type="health_degradation",
                        metrics={"error_message": metrics.error_message},
                    ))
            elif metrics.health_score < 50:
                severity = AlertSeverity.HIGH
                if severity_order.index(severity) >= min_severity_idx:
                    config = self._configs.get(workspace_id)
                    alerts.append(CrossWorkspaceAlert(
                        alert_id=str(uuid.uuid4()),
                        timestamp=datetime.now(),
                        severity=severity,
                        title=f"Workspace '{config.workspace_name}' health degraded",
                        description=f"Health score is {metrics.health_score}% with {metrics.failed_jobs_24h} failures in 24h.",
                        workspace_ids=[workspace_id],
                        workspace_names=[config.workspace_name] if config else [workspace_id],
                        alert_type="health_degradation",
                        metrics={
                            "health_score": metrics.health_score,
                            "success_rate_24h": metrics.success_rate_24h,
                            "failed_jobs_24h": metrics.failed_jobs_24h,
                        },
                    ))

        # Sort by severity (critical first) then timestamp
        alerts.sort(key=lambda a: (-severity_order.index(a.severity), a.timestamp), reverse=True)

        # Cache alerts
        self._alerts = alerts

        return alerts

    def get_cost_comparison(self, days: int = 7) -> Dict[str, Any]:
        """
        Compare costs across all workspaces.

        Args:
            days: Number of days to analyze.

        Returns:
            Dictionary with cost comparison data.
        """
        cost_data: Dict[str, Any] = {
            "success": True,
            "period_days": days,
            "start_date": (datetime.now() - timedelta(days=days)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "workspaces": [],
            "total_cost": 0.0,
            "total_dbus": 0.0,
            "by_cloud_provider": {},
            "by_environment": {},
        }

        for workspace_id, config in self._configs.items():
            workspace_cost = {
                "workspace_id": workspace_id,
                "workspace_name": config.workspace_name,
                "cloud_provider": config.cloud_provider,
                "environment": config.environment,
                "region": config.region,
                "cost": 0.0,
                "dbus": 0.0,
                "breakdown": {},
                "error": None,
            }

            # Try to fetch cost data via SQL if warehouse is configured
            if config.warehouse_id:
                try:
                    conn = config.get_sql_connection()
                    if conn:
                        cursor = conn.cursor()

                        # Query billing data for the period
                        query = """
                            SELECT
                                sku_name,
                                SUM(usage_quantity) as total_dbus,
                                SUM(usage_quantity * list_prices.pricing.default) as estimated_cost
                            FROM system.billing.usage u
                            LEFT JOIN system.billing.list_prices lp
                                ON u.sku_name = lp.sku_name
                            WHERE usage_date >= DATE_SUB(CURRENT_DATE(), INTERVAL :days DAY)
                            GROUP BY sku_name
                            ORDER BY estimated_cost DESC
                        """

                        try:
                            cursor.execute(query, {"days": days})
                            rows = cursor.fetchall()

                            for row in rows:
                                sku = row[0]
                                dbus = float(row[1]) if row[1] else 0.0
                                cost = float(row[2]) if row[2] else 0.0

                                workspace_cost["dbus"] += dbus
                                workspace_cost["cost"] += cost
                                workspace_cost["breakdown"][sku] = {
                                    "dbus": dbus,
                                    "cost": cost,
                                }
                        except Exception as e:
                            # Billing query might fail due to permissions
                            logger.warning(f"Billing query failed for {config.workspace_name}: {e}")
                            workspace_cost["error"] = f"Billing query failed: {str(e)}"

                        cursor.close()
                        conn.close()

                except Exception as e:
                    logger.error(f"Error fetching cost data for {config.workspace_name}: {e}")
                    workspace_cost["error"] = str(e)
            else:
                workspace_cost["error"] = "No SQL warehouse configured for cost queries"

            cost_data["workspaces"].append(workspace_cost)
            cost_data["total_cost"] += workspace_cost["cost"]
            cost_data["total_dbus"] += workspace_cost["dbus"]

            # Aggregate by cloud provider
            if config.cloud_provider:
                if config.cloud_provider not in cost_data["by_cloud_provider"]:
                    cost_data["by_cloud_provider"][config.cloud_provider] = {
                        "cost": 0.0,
                        "dbus": 0.0,
                        "workspace_count": 0,
                    }
                cost_data["by_cloud_provider"][config.cloud_provider]["cost"] += workspace_cost["cost"]
                cost_data["by_cloud_provider"][config.cloud_provider]["dbus"] += workspace_cost["dbus"]
                cost_data["by_cloud_provider"][config.cloud_provider]["workspace_count"] += 1

            # Aggregate by environment
            if config.environment:
                if config.environment not in cost_data["by_environment"]:
                    cost_data["by_environment"][config.environment] = {
                        "cost": 0.0,
                        "dbus": 0.0,
                        "workspace_count": 0,
                    }
                cost_data["by_environment"][config.environment]["cost"] += workspace_cost["cost"]
                cost_data["by_environment"][config.environment]["dbus"] += workspace_cost["dbus"]
                cost_data["by_environment"][config.environment]["workspace_count"] += 1

        # Calculate percentages
        if cost_data["total_cost"] > 0:
            for ws in cost_data["workspaces"]:
                ws["cost_percentage"] = round((ws["cost"] / cost_data["total_cost"]) * 100, 2)

        # Sort workspaces by cost (highest first)
        cost_data["workspaces"].sort(key=lambda x: x["cost"], reverse=True)

        return cost_data


def load_workspace_configs() -> List[WorkspaceConfig]:
    """
    Load workspace configurations from Delta table or environment.

    Returns:
        List of WorkspaceConfig objects.
    """
    configs: List[WorkspaceConfig] = []

    # First, try to load from the data layer (Delta table)
    try:
        from data.data_layer import get_data_layer

        data_layer = get_data_layer()

        # Query workspace configurations table
        query = """
            SELECT
                workspace_id,
                workspace_name,
                host,
                token_secret_scope,
                token_secret_key,
                warehouse_id,
                region,
                cloud_provider,
                environment,
                tags,
                enabled
            FROM jobs_monitor.config.workspace_configs
            WHERE enabled = true
        """

        try:
            results = data_layer.query(query)

            for row in results:
                # Token would typically be retrieved from secrets
                # For now, we'll skip rows without direct token access
                config = WorkspaceConfig(
                    workspace_id=row.get("workspace_id", ""),
                    workspace_name=row.get("workspace_name", ""),
                    host=row.get("host", ""),
                    token="",  # Would be loaded from secrets
                    warehouse_id=row.get("warehouse_id"),
                    region=row.get("region"),
                    cloud_provider=row.get("cloud_provider"),
                    environment=row.get("environment"),
                    tags=row.get("tags", {}),
                    enabled=row.get("enabled", True),
                )
                configs.append(config)

            logger.info(f"Loaded {len(configs)} workspace configs from Delta table")

        except Exception as e:
            logger.warning(f"Could not load from Delta table: {e}")

    except ImportError:
        logger.warning("Data layer not available for loading workspace configs")

    # Also check for environment-based configuration
    # Support for WORKSPACE_1_HOST, WORKSPACE_1_TOKEN, etc. pattern
    workspace_idx = 1
    while True:
        host = os.environ.get(f"WORKSPACE_{workspace_idx}_HOST")
        token = os.environ.get(f"WORKSPACE_{workspace_idx}_TOKEN")

        if not host or not token:
            break

        config = WorkspaceConfig(
            workspace_id=os.environ.get(f"WORKSPACE_{workspace_idx}_ID", f"ws_{workspace_idx}"),
            workspace_name=os.environ.get(f"WORKSPACE_{workspace_idx}_NAME", f"Workspace {workspace_idx}"),
            host=host,
            token=token,
            warehouse_id=os.environ.get(f"WORKSPACE_{workspace_idx}_WAREHOUSE_ID"),
            region=os.environ.get(f"WORKSPACE_{workspace_idx}_REGION"),
            cloud_provider=os.environ.get(f"WORKSPACE_{workspace_idx}_CLOUD"),
            environment=os.environ.get(f"WORKSPACE_{workspace_idx}_ENV"),
        )
        configs.append(config)
        workspace_idx += 1

    if workspace_idx > 1:
        logger.info(f"Loaded {workspace_idx - 1} workspace configs from environment variables")

    # Fallback: use default workspace from DATABRICKS_HOST/DATABRICKS_TOKEN
    if not configs:
        default_host = os.environ.get("DATABRICKS_HOST")
        default_token = os.environ.get("DATABRICKS_TOKEN")

        if default_host and default_token:
            configs.append(WorkspaceConfig(
                workspace_id="default",
                workspace_name="Default Workspace",
                host=default_host,
                token=default_token,
                warehouse_id=os.environ.get("WAREHOUSE_ID"),
            ))
            logger.info("Using default workspace configuration from environment")

    return configs


# Singleton instance
_multi_workspace_service: Optional[MultiWorkspaceService] = None


def get_multi_workspace_service() -> MultiWorkspaceService:
    """Get or create the singleton multi-workspace service."""
    global _multi_workspace_service
    if _multi_workspace_service is None:
        configs = load_workspace_configs()
        _multi_workspace_service = MultiWorkspaceService(configs)
    return _multi_workspace_service
