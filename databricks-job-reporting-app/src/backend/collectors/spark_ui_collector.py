"""
Spark UI REST API Metrics Collector (Tier 1)

This module provides functionality to collect Spark UI metrics via the driver-proxy-api
endpoint in Databricks. It collects executor metrics, stage information, and job details
without requiring an init script.

Usage:
    from databricks.sdk import WorkspaceClient
    from collectors.spark_ui_collector import SparkUICollector

    w = WorkspaceClient()
    collector = SparkUICollector(workspace_client=w, cluster_id="your-cluster-id")

    apps = collector.get_applications()
    for app in apps:
        metrics = collector.collect_executor_metrics(app["id"])
        stages = collector.get_stages(app["id"])
        jobs = collector.get_jobs(app["id"])
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import requests
from urllib.parse import urljoin

from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)


@dataclass
class ExecutorMetrics:
    """
    Dataclass representing metrics for a single Spark executor.

    Attributes:
        executor_id: Unique identifier for the executor (e.g., "driver", "0", "1")
        host_port: Host and port where the executor is running
        is_active: Whether the executor is currently active
        rdd_blocks: Number of RDD blocks cached on this executor
        memory_used: Amount of memory currently used (bytes)
        max_memory: Maximum memory available to executor (bytes)
        disk_used: Amount of disk space used for spilling (bytes)
        total_cores: Total number of cores available to executor
        max_tasks: Maximum number of tasks that can run concurrently
        active_tasks: Number of currently running tasks
        completed_tasks: Total number of tasks completed
        failed_tasks: Total number of tasks that failed
        total_duration: Total time spent executing tasks (ms)
        total_gc_time: Total time spent in garbage collection (ms)
        total_input_bytes: Total bytes read from input sources
        total_shuffle_read: Total bytes read in shuffle operations
        total_shuffle_write: Total bytes written in shuffle operations
        is_blacklisted: Whether executor is blacklisted
        memory_metrics: Optional detailed memory metrics
        peak_memory_metrics: Optional peak memory usage metrics
        collected_at: Timestamp when metrics were collected
    """
    executor_id: str
    host_port: str
    is_active: bool = True
    rdd_blocks: int = 0
    memory_used: int = 0
    max_memory: int = 0
    disk_used: int = 0
    total_cores: int = 0
    max_tasks: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_duration: int = 0
    total_gc_time: int = 0
    total_input_bytes: int = 0
    total_shuffle_read: int = 0
    total_shuffle_write: int = 0
    is_blacklisted: bool = False
    memory_metrics: Optional[Dict[str, int]] = None
    peak_memory_metrics: Optional[Dict[str, int]] = None
    collected_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "ExecutorMetrics":
        """
        Create an ExecutorMetrics instance from Spark UI API response.

        Args:
            data: Dictionary from Spark UI executors API endpoint

        Returns:
            ExecutorMetrics instance populated with data from API
        """
        return cls(
            executor_id=str(data.get("id", "")),
            host_port=data.get("hostPort", ""),
            is_active=data.get("isActive", True),
            rdd_blocks=data.get("rddBlocks", 0),
            memory_used=data.get("memoryUsed", 0),
            max_memory=data.get("maxMemory", 0),
            disk_used=data.get("diskUsed", 0),
            total_cores=data.get("totalCores", 0),
            max_tasks=data.get("maxTasks", 0),
            active_tasks=data.get("activeTasks", 0),
            completed_tasks=data.get("completedTasks", 0),
            failed_tasks=data.get("failedTasks", 0),
            total_duration=data.get("totalDuration", 0),
            total_gc_time=data.get("totalGCTime", 0),
            total_input_bytes=data.get("totalInputBytes", 0),
            total_shuffle_read=data.get("totalShuffleRead", 0),
            total_shuffle_write=data.get("totalShuffleWrite", 0),
            is_blacklisted=data.get("isBlacklisted", False),
            memory_metrics=data.get("memoryMetrics"),
            peak_memory_metrics=data.get("peakMemoryMetrics"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert ExecutorMetrics to a dictionary."""
        return {
            "executor_id": self.executor_id,
            "host_port": self.host_port,
            "is_active": self.is_active,
            "rdd_blocks": self.rdd_blocks,
            "memory_used": self.memory_used,
            "max_memory": self.max_memory,
            "disk_used": self.disk_used,
            "total_cores": self.total_cores,
            "max_tasks": self.max_tasks,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "total_duration": self.total_duration,
            "total_gc_time": self.total_gc_time,
            "total_input_bytes": self.total_input_bytes,
            "total_shuffle_read": self.total_shuffle_read,
            "total_shuffle_write": self.total_shuffle_write,
            "is_blacklisted": self.is_blacklisted,
            "memory_metrics": self.memory_metrics,
            "peak_memory_metrics": self.peak_memory_metrics,
            "collected_at": self.collected_at.isoformat(),
        }

    @property
    def memory_utilization(self) -> float:
        """Calculate memory utilization as a percentage."""
        if self.max_memory == 0:
            return 0.0
        return (self.memory_used / self.max_memory) * 100

    @property
    def gc_time_percentage(self) -> float:
        """Calculate GC time as a percentage of total duration."""
        if self.total_duration == 0:
            return 0.0
        return (self.total_gc_time / self.total_duration) * 100


@dataclass
class StageInfo:
    """
    Dataclass representing information about a Spark stage.
    """
    stage_id: int
    attempt_id: int
    name: str
    status: str
    num_tasks: int
    num_active_tasks: int
    num_complete_tasks: int
    num_failed_tasks: int
    executor_run_time: int
    executor_cpu_time: int
    input_bytes: int
    input_records: int
    output_bytes: int
    output_records: int
    shuffle_read_bytes: int
    shuffle_read_records: int
    shuffle_write_bytes: int
    shuffle_write_records: int
    memory_bytes_spilled: int
    disk_bytes_spilled: int
    submission_time: Optional[str] = None
    completion_time: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "StageInfo":
        """Create a StageInfo instance from Spark UI API response."""
        return cls(
            stage_id=data.get("stageId", 0),
            attempt_id=data.get("attemptId", 0),
            name=data.get("name", ""),
            status=data.get("status", ""),
            num_tasks=data.get("numTasks", 0),
            num_active_tasks=data.get("numActiveTasks", 0),
            num_complete_tasks=data.get("numCompleteTasks", 0),
            num_failed_tasks=data.get("numFailedTasks", 0),
            executor_run_time=data.get("executorRunTime", 0),
            executor_cpu_time=data.get("executorCpuTime", 0),
            input_bytes=data.get("inputBytes", 0),
            input_records=data.get("inputRecords", 0),
            output_bytes=data.get("outputBytes", 0),
            output_records=data.get("outputRecords", 0),
            shuffle_read_bytes=data.get("shuffleReadBytes", 0),
            shuffle_read_records=data.get("shuffleReadRecords", 0),
            shuffle_write_bytes=data.get("shuffleWriteBytes", 0),
            shuffle_write_records=data.get("shuffleWriteRecords", 0),
            memory_bytes_spilled=data.get("memoryBytesSpilled", 0),
            disk_bytes_spilled=data.get("diskBytesSpilled", 0),
            submission_time=data.get("submissionTime"),
            completion_time=data.get("completionTime"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert StageInfo to a dictionary."""
        return {
            "stage_id": self.stage_id,
            "attempt_id": self.attempt_id,
            "name": self.name,
            "status": self.status,
            "num_tasks": self.num_tasks,
            "num_active_tasks": self.num_active_tasks,
            "num_complete_tasks": self.num_complete_tasks,
            "num_failed_tasks": self.num_failed_tasks,
            "executor_run_time": self.executor_run_time,
            "executor_cpu_time": self.executor_cpu_time,
            "input_bytes": self.input_bytes,
            "input_records": self.input_records,
            "output_bytes": self.output_bytes,
            "output_records": self.output_records,
            "shuffle_read_bytes": self.shuffle_read_bytes,
            "shuffle_read_records": self.shuffle_read_records,
            "shuffle_write_bytes": self.shuffle_write_bytes,
            "shuffle_write_records": self.shuffle_write_records,
            "memory_bytes_spilled": self.memory_bytes_spilled,
            "disk_bytes_spilled": self.disk_bytes_spilled,
            "submission_time": self.submission_time,
            "completion_time": self.completion_time,
        }


@dataclass
class JobInfo:
    """
    Dataclass representing information about a Spark job.
    """
    job_id: int
    name: str
    status: str
    submission_time: Optional[str] = None
    completion_time: Optional[str] = None
    stage_ids: List[int] = field(default_factory=list)
    num_tasks: int = 0
    num_active_tasks: int = 0
    num_completed_tasks: int = 0
    num_skipped_tasks: int = 0
    num_failed_tasks: int = 0
    num_active_stages: int = 0
    num_completed_stages: int = 0
    num_skipped_stages: int = 0
    num_failed_stages: int = 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "JobInfo":
        """Create a JobInfo instance from Spark UI API response."""
        return cls(
            job_id=data.get("jobId", 0),
            name=data.get("name", ""),
            status=data.get("status", ""),
            submission_time=data.get("submissionTime"),
            completion_time=data.get("completionTime"),
            stage_ids=data.get("stageIds", []),
            num_tasks=data.get("numTasks", 0),
            num_active_tasks=data.get("numActiveTasks", 0),
            num_completed_tasks=data.get("numCompletedTasks", 0),
            num_skipped_tasks=data.get("numSkippedTasks", 0),
            num_failed_tasks=data.get("numFailedTasks", 0),
            num_active_stages=data.get("numActiveStages", 0),
            num_completed_stages=data.get("numCompletedStages", 0),
            num_skipped_stages=data.get("numSkippedStages", 0),
            num_failed_stages=data.get("numFailedStages", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert JobInfo to a dictionary."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status,
            "submission_time": self.submission_time,
            "completion_time": self.completion_time,
            "stage_ids": self.stage_ids,
            "num_tasks": self.num_tasks,
            "num_active_tasks": self.num_active_tasks,
            "num_completed_tasks": self.num_completed_tasks,
            "num_skipped_tasks": self.num_skipped_tasks,
            "num_failed_tasks": self.num_failed_tasks,
            "num_active_stages": self.num_active_stages,
            "num_completed_stages": self.num_completed_stages,
            "num_skipped_stages": self.num_skipped_stages,
            "num_failed_stages": self.num_failed_stages,
        }


class SparkUICollectorError(Exception):
    """Base exception for SparkUICollector errors."""
    pass


class ClusterNotRunningError(SparkUICollectorError):
    """Raised when the cluster is not in a running state."""
    pass


class SparkUICollector:
    """
    Collector for Spark UI REST API metrics via Databricks driver-proxy-api.

    This collector connects to the Spark UI through Databricks' driver-proxy-api
    endpoint, which provides secure access to the Spark UI without requiring
    an init script or direct network access to the cluster.

    The driver-proxy-api is available on port 40001 for the Spark UI.

    Attributes:
        workspace_client: Databricks WorkspaceClient instance for authentication
        cluster_id: ID of the Databricks cluster to collect metrics from
        spark_ui_port: Port for Spark UI (default: 40001)
        timeout: Request timeout in seconds (default: 30)
    """

    SPARK_UI_PORT = 40001
    ORG_ID = "0"  # Organization ID placeholder for driver-proxy-api

    def __init__(
        self,
        workspace_client: Optional[WorkspaceClient] = None,
        cluster_id: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize the SparkUICollector.

        Args:
            workspace_client: Databricks WorkspaceClient. If not provided,
                            will create one using default configuration.
            cluster_id: ID of the cluster to collect metrics from.
                       Can also be set later via set_cluster_id().
            timeout: Request timeout in seconds.
        """
        self.workspace_client = workspace_client or WorkspaceClient()
        self.cluster_id = cluster_id
        self.timeout = timeout
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        """Get or create a requests session with authentication headers."""
        if self._session is None:
            self._session = requests.Session()
            # Get authentication headers from workspace client
            self._session.headers.update(self._get_auth_headers())
        return self._session

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers from the Databricks SDK.

        Returns:
            Dictionary of headers including Authorization token.
        """
        # Get the API client's headers which include the auth token
        config = self.workspace_client.config
        headers = {}

        # Use the SDK's authentication mechanism
        # This handles OAuth, PAT tokens, and other auth methods
        if hasattr(config, 'authenticate'):
            # SDK v0.12+ uses authenticate() method
            auth_headers = config.authenticate()
            if auth_headers:
                headers.update(auth_headers)
        else:
            # Fallback for older SDK versions
            if config.token:
                headers["Authorization"] = f"Bearer {config.token}"

        return headers

    @property
    def workspace_url(self) -> str:
        """Get the workspace URL from the client configuration."""
        host = self.workspace_client.config.host
        # Ensure no trailing slash
        return host.rstrip("/") if host else ""

    def _build_spark_ui_url(self, app_id: str, endpoint: str) -> str:
        """
        Build the full URL for a Spark UI API endpoint.

        Args:
            app_id: Spark application ID
            endpoint: API endpoint (e.g., "executors", "stages", "jobs")

        Returns:
            Full URL for the API request
        """
        if not self.cluster_id:
            raise SparkUICollectorError("cluster_id must be set before making requests")

        base_url = (
            f"{self.workspace_url}/driver-proxy-api/o/{self.ORG_ID}/"
            f"{self.cluster_id}/{self.SPARK_UI_PORT}/api/v1/applications/{app_id}"
        )
        return f"{base_url}/{endpoint}" if endpoint else base_url

    def _build_applications_url(self) -> str:
        """
        Build the URL for listing all Spark applications.

        Returns:
            Full URL for the applications list endpoint
        """
        if not self.cluster_id:
            raise SparkUICollectorError("cluster_id must be set before making requests")

        return (
            f"{self.workspace_url}/driver-proxy-api/o/{self.ORG_ID}/"
            f"{self.cluster_id}/{self.SPARK_UI_PORT}/api/v1/applications"
        )

    def _make_request(self, url: str) -> Any:
        """
        Make an authenticated request to the Spark UI API.

        Args:
            url: Full URL to request

        Returns:
            Parsed JSON response

        Raises:
            SparkUICollectorError: If the request fails
            ClusterNotRunningError: If the cluster is not running
        """
        try:
            logger.debug(f"Making request to: {url}")
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 404:
                raise SparkUICollectorError(
                    f"Resource not found. The cluster may not be running or "
                    f"the Spark application may not exist. URL: {url}"
                )
            elif response.status_code == 502 or response.status_code == 503:
                raise ClusterNotRunningError(
                    f"Cluster {self.cluster_id} is not running or not accessible"
                )
            elif response.status_code == 401 or response.status_code == 403:
                raise SparkUICollectorError(
                    f"Authentication failed. Status: {response.status_code}"
                )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise SparkUICollectorError(
                f"Request timed out after {self.timeout} seconds"
            )
        except requests.exceptions.ConnectionError as e:
            raise SparkUICollectorError(f"Connection error: {e}")
        except requests.exceptions.JSONDecodeError:
            raise SparkUICollectorError(
                f"Invalid JSON response from Spark UI. Response: {response.text[:500]}"
            )

    def set_cluster_id(self, cluster_id: str) -> None:
        """
        Set the cluster ID for subsequent requests.

        Args:
            cluster_id: The Databricks cluster ID
        """
        self.cluster_id = cluster_id
        # Reset session to clear any cached state
        if self._session:
            self._session.close()
            self._session = None

    def verify_cluster_running(self) -> bool:
        """
        Verify that the cluster is running and accessible.

        Returns:
            True if cluster is running and Spark UI is accessible

        Raises:
            SparkUICollectorError: If cluster_id is not set
            ClusterNotRunningError: If cluster is not running
        """
        if not self.cluster_id:
            raise SparkUICollectorError("cluster_id must be set")

        # Use the Databricks API to check cluster state
        cluster_info = self.workspace_client.clusters.get(self.cluster_id)

        if cluster_info.state.value not in ("RUNNING", "RESIZING"):
            raise ClusterNotRunningError(
                f"Cluster {self.cluster_id} is in state {cluster_info.state.value}, "
                f"not RUNNING"
            )

        return True

    def get_applications(self) -> List[Dict[str, Any]]:
        """
        Get a list of all Spark applications on the cluster.

        Returns:
            List of application dictionaries containing:
            - id: Application ID
            - name: Application name
            - attempts: List of attempt information

        Raises:
            SparkUICollectorError: If the request fails
            ClusterNotRunningError: If the cluster is not running
        """
        url = self._build_applications_url()
        applications = self._make_request(url)

        logger.info(f"Found {len(applications)} Spark applications")
        return applications

    def collect_executor_metrics(self, app_id: str) -> List[ExecutorMetrics]:
        """
        Collect executor metrics for a specific Spark application.

        Args:
            app_id: The Spark application ID

        Returns:
            List of ExecutorMetrics objects for each executor

        Raises:
            SparkUICollectorError: If the request fails
        """
        url = self._build_spark_ui_url(app_id, "executors")
        executors_data = self._make_request(url)

        metrics = [
            ExecutorMetrics.from_api_response(executor)
            for executor in executors_data
        ]

        logger.info(
            f"Collected metrics for {len(metrics)} executors "
            f"(app: {app_id})"
        )

        return metrics

    def collect_all_executor_metrics(
        self, app_id: str, include_dead: bool = False
    ) -> List[ExecutorMetrics]:
        """
        Collect all executor metrics including optionally dead executors.

        Args:
            app_id: The Spark application ID
            include_dead: Whether to include dead/removed executors

        Returns:
            List of ExecutorMetrics objects
        """
        endpoint = "allexecutors" if include_dead else "executors"
        url = self._build_spark_ui_url(app_id, endpoint)
        executors_data = self._make_request(url)

        metrics = [
            ExecutorMetrics.from_api_response(executor)
            for executor in executors_data
        ]

        return metrics

    def get_stages(
        self,
        app_id: str,
        status: Optional[str] = None
    ) -> List[StageInfo]:
        """
        Get stage information for a Spark application.

        Args:
            app_id: The Spark application ID
            status: Optional filter by status (active, complete, pending, failed)

        Returns:
            List of StageInfo objects
        """
        endpoint = "stages"
        if status:
            endpoint = f"stages?status={status}"

        url = self._build_spark_ui_url(app_id, endpoint)
        stages_data = self._make_request(url)

        stages = [
            StageInfo.from_api_response(stage)
            for stage in stages_data
        ]

        logger.info(f"Retrieved {len(stages)} stages (app: {app_id})")
        return stages

    def get_stage_details(
        self,
        app_id: str,
        stage_id: int,
        attempt_id: int = 0
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific stage.

        Args:
            app_id: The Spark application ID
            stage_id: The stage ID
            attempt_id: The attempt ID (default: 0)

        Returns:
            Dictionary with detailed stage information
        """
        url = self._build_spark_ui_url(app_id, f"stages/{stage_id}/{attempt_id}")
        return self._make_request(url)

    def get_jobs(self, app_id: str, status: Optional[str] = None) -> List[JobInfo]:
        """
        Get job information for a Spark application.

        Args:
            app_id: The Spark application ID
            status: Optional filter by status (running, succeeded, failed, unknown)

        Returns:
            List of JobInfo objects
        """
        endpoint = "jobs"
        if status:
            endpoint = f"jobs?status={status}"

        url = self._build_spark_ui_url(app_id, endpoint)
        jobs_data = self._make_request(url)

        jobs = [
            JobInfo.from_api_response(job)
            for job in jobs_data
        ]

        logger.info(f"Retrieved {len(jobs)} jobs (app: {app_id})")
        return jobs

    def get_job_details(self, app_id: str, job_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific job.

        Args:
            app_id: The Spark application ID
            job_id: The job ID

        Returns:
            Dictionary with detailed job information
        """
        url = self._build_spark_ui_url(app_id, f"jobs/{job_id}")
        return self._make_request(url)

    def get_environment(self, app_id: str) -> Dict[str, Any]:
        """
        Get the environment information for a Spark application.

        Args:
            app_id: The Spark application ID

        Returns:
            Dictionary with Spark configuration and environment details
        """
        url = self._build_spark_ui_url(app_id, "environment")
        return self._make_request(url)

    def get_storage(self, app_id: str) -> List[Dict[str, Any]]:
        """
        Get storage (RDD) information for a Spark application.

        Args:
            app_id: The Spark application ID

        Returns:
            List of RDD storage information
        """
        url = self._build_spark_ui_url(app_id, "storage/rdd")
        return self._make_request(url)

    def get_summary_metrics(self, app_id: str) -> Dict[str, Any]:
        """
        Get a summary of key metrics for a Spark application.

        This method aggregates metrics from multiple endpoints to provide
        a high-level overview of the application's performance.

        Args:
            app_id: The Spark application ID

        Returns:
            Dictionary with aggregated summary metrics:
            - executor_count: Number of active executors
            - total_memory_used: Total memory used across all executors
            - total_memory_max: Total max memory across all executors
            - total_gc_time: Total GC time across all executors
            - total_shuffle_read: Total shuffle read bytes
            - total_shuffle_write: Total shuffle write bytes
            - active_tasks: Total active tasks
            - completed_tasks: Total completed tasks
            - failed_tasks: Total failed tasks
            - stage_counts: Count of stages by status
            - job_counts: Count of jobs by status
        """
        # Collect executor metrics
        executors = self.collect_executor_metrics(app_id)
        active_executors = [e for e in executors if e.is_active]

        # Aggregate executor metrics
        total_memory_used = sum(e.memory_used for e in active_executors)
        total_memory_max = sum(e.max_memory for e in active_executors)
        total_gc_time = sum(e.total_gc_time for e in active_executors)
        total_shuffle_read = sum(e.total_shuffle_read for e in active_executors)
        total_shuffle_write = sum(e.total_shuffle_write for e in active_executors)
        active_tasks = sum(e.active_tasks for e in active_executors)
        completed_tasks = sum(e.completed_tasks for e in active_executors)
        failed_tasks = sum(e.failed_tasks for e in active_executors)

        # Get stage and job counts
        stages = self.get_stages(app_id)
        jobs = self.get_jobs(app_id)

        stage_status_counts = {}
        for stage in stages:
            status = stage.status.lower()
            stage_status_counts[status] = stage_status_counts.get(status, 0) + 1

        job_status_counts = {}
        for job in jobs:
            status = job.status.lower()
            job_status_counts[status] = job_status_counts.get(status, 0) + 1

        return {
            "app_id": app_id,
            "collected_at": datetime.utcnow().isoformat(),
            "executor_count": len(active_executors),
            "total_memory_used": total_memory_used,
            "total_memory_max": total_memory_max,
            "memory_utilization_pct": (
                (total_memory_used / total_memory_max * 100)
                if total_memory_max > 0 else 0
            ),
            "total_gc_time_ms": total_gc_time,
            "total_shuffle_read_bytes": total_shuffle_read,
            "total_shuffle_write_bytes": total_shuffle_write,
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "stage_counts": stage_status_counts,
            "job_counts": job_status_counts,
        }

    def close(self) -> None:
        """Close the HTTP session and release resources."""
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self) -> "SparkUICollector":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close resources."""
        self.close()


# Example usage
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Example: Collect metrics from a cluster
    # Usage: python spark_ui_collector.py <cluster_id>

    if len(sys.argv) < 2:
        print("Usage: python spark_ui_collector.py <cluster_id>")
        sys.exit(1)

    cluster_id = sys.argv[1]

    with SparkUICollector(cluster_id=cluster_id) as collector:
        try:
            # Verify cluster is running
            collector.verify_cluster_running()
            print(f"Cluster {cluster_id} is running")

            # Get applications
            apps = collector.get_applications()
            print(f"\nFound {len(apps)} applications:")

            for app in apps:
                app_id = app["id"]
                app_name = app.get("name", "Unknown")
                print(f"\n  Application: {app_name} ({app_id})")

                # Collect executor metrics
                metrics = collector.collect_executor_metrics(app_id)
                print(f"    Executors: {len(metrics)}")

                for m in metrics:
                    print(f"      - {m.executor_id}: "
                          f"Memory {m.memory_used/1024/1024:.1f}MB / "
                          f"{m.max_memory/1024/1024:.1f}MB, "
                          f"GC Time {m.total_gc_time}ms")

                # Get summary
                summary = collector.get_summary_metrics(app_id)
                print(f"    Summary:")
                print(f"      Memory Utilization: {summary['memory_utilization_pct']:.1f}%")
                print(f"      Total GC Time: {summary['total_gc_time_ms']}ms")
                print(f"      Shuffle Read: {summary['total_shuffle_read_bytes']/1024/1024:.2f}MB")
                print(f"      Shuffle Write: {summary['total_shuffle_write_bytes']/1024/1024:.2f}MB")

        except ClusterNotRunningError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except SparkUICollectorError as e:
            print(f"Error collecting metrics: {e}")
            sys.exit(1)
