"""
MLflow Integration Service for Databricks Jobs Monitor.

Provides experiment tracking, model registry, and serving endpoint
monitoring with integration to the unified data access layer.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# MLflow client import
try:
    from mlflow.tracking import MlflowClient
    from mlflow.entities import ViewType
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("mlflow not available - MLflow integration disabled")

# Import data layer for SQL queries
from data.data_layer import get_data_layer


@dataclass
class ExperimentSummary:
    """Summary of an MLflow experiment."""
    experiment_id: str
    name: str
    artifact_location: str
    lifecycle_stage: str
    creation_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    running_count: int = 0
    tags: Dict[str, str] = field(default_factory=dict)
    associated_job_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "artifact_location": self.artifact_location,
            "lifecycle_stage": self.lifecycle_stage,
            "creation_time": self.creation_time.isoformat() if self.creation_time else None,
            "last_update_time": self.last_update_time.isoformat() if self.last_update_time else None,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "running_count": self.running_count,
            "tags": self.tags,
            "associated_job_ids": self.associated_job_ids,
            "success_rate": round(self.successful_runs / self.total_runs * 100, 2) if self.total_runs > 0 else 0,
        }


@dataclass
class RunMetrics:
    """Metrics and metadata for an MLflow run."""
    run_id: str
    experiment_id: str
    run_name: Optional[str] = None
    status: str = "UNKNOWN"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    artifact_uri: Optional[str] = None
    user_id: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    job_id: Optional[str] = None
    job_run_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "run_name": self.run_name,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "metrics": self.metrics,
            "params": self.params,
            "tags": self.tags,
            "artifact_uri": self.artifact_uri,
            "user_id": self.user_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "job_id": self.job_id,
            "job_run_id": self.job_run_id,
        }


@dataclass
class ModelVersion:
    """Model version from the MLflow Model Registry."""
    name: str
    version: str
    creation_timestamp: Optional[datetime] = None
    last_updated_timestamp: Optional[datetime] = None
    current_stage: str = "None"
    description: Optional[str] = None
    source: Optional[str] = None
    run_id: Optional[str] = None
    run_link: Optional[str] = None
    status: str = "READY"
    status_message: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)

    # Performance metrics from the training run
    training_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "version": self.version,
            "creation_timestamp": self.creation_timestamp.isoformat() if self.creation_timestamp else None,
            "last_updated_timestamp": self.last_updated_timestamp.isoformat() if self.last_updated_timestamp else None,
            "current_stage": self.current_stage,
            "description": self.description,
            "source": self.source,
            "run_id": self.run_id,
            "run_link": self.run_link,
            "status": self.status,
            "status_message": self.status_message,
            "tags": self.tags,
            "aliases": self.aliases,
            "training_metrics": self.training_metrics,
        }


@dataclass
class ServingEndpoint:
    """Model serving endpoint information."""
    name: str
    creator: Optional[str] = None
    creation_timestamp: Optional[datetime] = None
    last_updated_timestamp: Optional[datetime] = None
    state: str = "UNKNOWN"
    config: Dict[str, Any] = field(default_factory=dict)

    # Served models/entities
    served_entities: List[Dict[str, Any]] = field(default_factory=list)

    # Performance metrics
    total_requests: int = 0
    avg_latency_ms: Optional[float] = None
    p50_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    p99_latency_ms: Optional[float] = None
    error_rate: Optional[float] = None
    requests_per_second: Optional[float] = None

    # Resource utilization
    gpu_utilization: Optional[float] = None
    memory_utilization: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "creator": self.creator,
            "creation_timestamp": self.creation_timestamp.isoformat() if self.creation_timestamp else None,
            "last_updated_timestamp": self.last_updated_timestamp.isoformat() if self.last_updated_timestamp else None,
            "state": self.state,
            "config": self.config,
            "served_entities": self.served_entities,
            "total_requests": self.total_requests,
            "avg_latency_ms": self.avg_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "error_rate": self.error_rate,
            "requests_per_second": self.requests_per_second,
            "gpu_utilization": self.gpu_utilization,
            "memory_utilization": self.memory_utilization,
        }


class MLflowService:
    """
    Service for MLflow experiment tracking, model registry, and serving monitoring.

    Integrates with:
    - MLflow Tracking API for experiments and runs
    - MLflow Model Registry for registered models
    - System tables for job-experiment associations
    - Serving endpoints for inference monitoring
    """

    def __init__(self, tracking_uri: Optional[str] = None):
        """
        Initialize MLflow service.

        Args:
            tracking_uri: MLflow tracking server URI. If None, uses environment variable.
        """
        if not MLFLOW_AVAILABLE:
            raise RuntimeError("mlflow package is not available. Install with: pip install mlflow")

        self.tracking_uri = tracking_uri or os.environ.get(
            "MLFLOW_TRACKING_URI",
            "databricks"
        )
        self._client: Optional[MlflowClient] = None
        self._data_layer = get_data_layer()

    @property
    def client(self) -> MlflowClient:
        """Get or create MLflow client."""
        if self._client is None:
            self._client = MlflowClient(tracking_uri=self.tracking_uri)
        return self._client

    def get_all_experiments(
        self,
        view_type: str = "ACTIVE_ONLY",
        max_results: int = 1000
    ) -> List[ExperimentSummary]:
        """
        Get all MLflow experiments with summary statistics.

        Args:
            view_type: One of "ACTIVE_ONLY", "DELETED_ONLY", "ALL"
            max_results: Maximum number of experiments to return

        Returns:
            List of ExperimentSummary objects
        """
        # Map view type string to ViewType enum
        view_type_map = {
            "ACTIVE_ONLY": ViewType.ACTIVE_ONLY,
            "DELETED_ONLY": ViewType.DELETED_ONLY,
            "ALL": ViewType.ALL,
        }
        vt = view_type_map.get(view_type.upper(), ViewType.ACTIVE_ONLY)

        experiments = self.client.search_experiments(
            view_type=vt,
            max_results=max_results
        )

        summaries = []
        for exp in experiments:
            # Get run statistics for this experiment
            runs = self.client.search_runs(
                experiment_ids=[exp.experiment_id],
                max_results=10000,  # Get all runs for stats
            )

            total_runs = len(runs)
            successful_runs = sum(1 for r in runs if r.info.status == "FINISHED")
            failed_runs = sum(1 for r in runs if r.info.status == "FAILED")
            running_count = sum(1 for r in runs if r.info.status == "RUNNING")

            # Get latest update time from runs
            last_update_time = None
            if runs:
                last_update_ms = max(
                    r.info.end_time or r.info.start_time or 0
                    for r in runs
                )
                if last_update_ms:
                    last_update_time = datetime.fromtimestamp(last_update_ms / 1000)

            summary = ExperimentSummary(
                experiment_id=exp.experiment_id,
                name=exp.name,
                artifact_location=exp.artifact_location or "",
                lifecycle_stage=exp.lifecycle_stage,
                creation_time=datetime.fromtimestamp(exp.creation_time / 1000) if exp.creation_time else None,
                last_update_time=last_update_time,
                total_runs=total_runs,
                successful_runs=successful_runs,
                failed_runs=failed_runs,
                running_count=running_count,
                tags=exp.tags or {},
            )
            summaries.append(summary)

        return summaries

    def get_experiment_runs(
        self,
        experiment_id: str,
        max_results: int = 100,
        filter_string: Optional[str] = None,
        order_by: Optional[List[str]] = None
    ) -> List[RunMetrics]:
        """
        Get runs for a specific experiment with full metrics.

        Args:
            experiment_id: ID of the experiment
            max_results: Maximum number of runs to return
            filter_string: Filter expression (e.g., "metrics.accuracy > 0.9")
            order_by: List of columns to order by (e.g., ["metrics.accuracy DESC"])

        Returns:
            List of RunMetrics objects
        """
        runs = self.client.search_runs(
            experiment_ids=[experiment_id],
            filter_string=filter_string or "",
            max_results=max_results,
            order_by=order_by or ["start_time DESC"],
        )

        run_metrics_list = []
        for run in runs:
            info = run.info
            data = run.data

            # Calculate duration
            duration_seconds = None
            if info.start_time and info.end_time:
                duration_seconds = (info.end_time - info.start_time) / 1000

            # Extract job association from tags
            job_id = data.tags.get("mlflow.databricks.jobId")
            job_run_id = data.tags.get("mlflow.databricks.jobRunId")

            run_metrics = RunMetrics(
                run_id=info.run_id,
                experiment_id=experiment_id,
                run_name=info.run_name,
                status=info.status,
                start_time=datetime.fromtimestamp(info.start_time / 1000) if info.start_time else None,
                end_time=datetime.fromtimestamp(info.end_time / 1000) if info.end_time else None,
                duration_seconds=duration_seconds,
                metrics=data.metrics,
                params=data.params,
                tags=data.tags,
                artifact_uri=info.artifact_uri,
                user_id=info.user_id,
                source_name=data.tags.get("mlflow.source.name"),
                source_type=data.tags.get("mlflow.source.type"),
                job_id=job_id,
                job_run_id=job_run_id,
            )
            run_metrics_list.append(run_metrics)

        return run_metrics_list

    def get_job_experiment_mapping(
        self,
        job_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get mapping of jobs to their associated MLflow experiments and runs.

        Uses system.mlflow.experiment_runs table for accurate job associations.

        Args:
            job_ids: List of job IDs to look up

        Returns:
            Dictionary mapping job_id to list of experiment/run info
        """
        if not job_ids:
            return {}

        # Build parameterized query for job IDs
        job_id_placeholders = ", ".join([f"'{jid}'" for jid in job_ids])

        query = f"""
        SELECT
            er.experiment_id,
            er.run_id,
            er.run_name,
            er.status,
            er.start_time,
            er.end_time,
            er.artifact_uri,
            t.value as job_id
        FROM system.mlflow.experiment_runs er
        LEFT JOIN system.mlflow.run_tags t
            ON er.run_id = t.run_id
            AND t.key = 'mlflow.databricks.jobId'
        WHERE t.value IN ({job_id_placeholders})
        ORDER BY er.start_time DESC
        """

        try:
            results = self._data_layer.query(query)
        except Exception as e:
            logger.error(f"Failed to query job-experiment mapping: {e}")
            # Fallback to MLflow API search
            return self._get_job_experiment_mapping_fallback(job_ids)

        # Group results by job_id
        mapping: Dict[str, List[Dict[str, Any]]] = {jid: [] for jid in job_ids}
        for row in results:
            job_id = row.get("job_id")
            if job_id in mapping:
                mapping[job_id].append({
                    "experiment_id": row.get("experiment_id"),
                    "run_id": row.get("run_id"),
                    "run_name": row.get("run_name"),
                    "status": row.get("status"),
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time"),
                    "artifact_uri": row.get("artifact_uri"),
                })

        return mapping

    def _get_job_experiment_mapping_fallback(
        self,
        job_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fallback method to get job-experiment mapping using MLflow API."""
        mapping: Dict[str, List[Dict[str, Any]]] = {jid: [] for jid in job_ids}

        # Search across all experiments for runs with matching job tags
        experiments = self.client.search_experiments(view_type=ViewType.ACTIVE_ONLY)

        for exp in experiments:
            for job_id in job_ids:
                filter_str = f"tags.`mlflow.databricks.jobId` = '{job_id}'"
                try:
                    runs = self.client.search_runs(
                        experiment_ids=[exp.experiment_id],
                        filter_string=filter_str,
                        max_results=100,
                    )
                    for run in runs:
                        mapping[job_id].append({
                            "experiment_id": exp.experiment_id,
                            "run_id": run.info.run_id,
                            "run_name": run.info.run_name,
                            "status": run.info.status,
                            "start_time": datetime.fromtimestamp(run.info.start_time / 1000) if run.info.start_time else None,
                            "end_time": datetime.fromtimestamp(run.info.end_time / 1000) if run.info.end_time else None,
                            "artifact_uri": run.info.artifact_uri,
                        })
                except Exception as e:
                    logger.debug(f"Error searching runs in experiment {exp.experiment_id}: {e}")

        return mapping

    def get_registered_models(
        self,
        max_results: int = 100,
        filter_string: Optional[str] = None
    ) -> List[ModelVersion]:
        """
        Get registered models from the Model Registry.

        Args:
            max_results: Maximum number of models to return
            filter_string: Optional filter expression

        Returns:
            List of ModelVersion objects (latest version of each model)
        """
        models = self.client.search_registered_models(
            max_results=max_results,
            filter_string=filter_string,
        )

        model_versions = []
        for model in models:
            # Get the latest version
            if model.latest_versions:
                latest = model.latest_versions[0]
                for v in model.latest_versions:
                    if int(v.version) > int(latest.version):
                        latest = v

                # Get training metrics from the source run
                training_metrics = {}
                if latest.run_id:
                    try:
                        run = self.client.get_run(latest.run_id)
                        training_metrics = run.data.metrics
                    except Exception as e:
                        logger.debug(f"Could not fetch training metrics for run {latest.run_id}: {e}")

                # Get aliases for this model
                aliases = []
                try:
                    for alias in self.client.get_model_version_by_alias(model.name, "champion"):
                        aliases.append("champion")
                except Exception:
                    pass

                mv = ModelVersion(
                    name=model.name,
                    version=latest.version,
                    creation_timestamp=datetime.fromtimestamp(latest.creation_timestamp / 1000) if latest.creation_timestamp else None,
                    last_updated_timestamp=datetime.fromtimestamp(latest.last_updated_timestamp / 1000) if latest.last_updated_timestamp else None,
                    current_stage=latest.current_stage,
                    description=latest.description,
                    source=latest.source,
                    run_id=latest.run_id,
                    run_link=latest.run_link,
                    status=latest.status,
                    status_message=latest.status_message,
                    tags=latest.tags or {},
                    aliases=aliases,
                    training_metrics=training_metrics,
                )
                model_versions.append(mv)

        return model_versions

    def get_model_version_metrics(
        self,
        model_name: str,
        version: str
    ) -> Dict[str, Any]:
        """
        Get detailed metrics for a specific model version.

        Args:
            model_name: Name of the registered model
            version: Version number

        Returns:
            Dictionary with model version details and metrics
        """
        model_version = self.client.get_model_version(model_name, version)

        result = {
            "name": model_name,
            "version": version,
            "stage": model_version.current_stage,
            "status": model_version.status,
            "description": model_version.description,
            "source": model_version.source,
            "run_id": model_version.run_id,
            "creation_timestamp": model_version.creation_timestamp,
            "tags": model_version.tags or {},
        }

        # Get training run metrics
        if model_version.run_id:
            try:
                run = self.client.get_run(model_version.run_id)
                result["training_metrics"] = run.data.metrics
                result["training_params"] = run.data.params
                result["training_tags"] = run.data.tags
                result["artifact_uri"] = run.info.artifact_uri

                # Calculate training duration
                if run.info.start_time and run.info.end_time:
                    result["training_duration_seconds"] = (run.info.end_time - run.info.start_time) / 1000
            except Exception as e:
                logger.warning(f"Could not fetch training run details: {e}")

        return result

    def get_serving_endpoints(self) -> List[ServingEndpoint]:
        """
        Get all model serving endpoints with their current state.

        Returns:
            List of ServingEndpoint objects
        """
        # Use Databricks SDK or API for serving endpoints
        # This requires the databricks-sdk package
        try:
            from databricks.sdk import WorkspaceClient

            w = WorkspaceClient()
            endpoints = w.serving_endpoints.list()

            serving_endpoints = []
            for ep in endpoints:
                served_entities = []
                if ep.config and ep.config.served_entities:
                    for entity in ep.config.served_entities:
                        served_entities.append({
                            "name": entity.name,
                            "entity_name": entity.entity_name,
                            "entity_version": entity.entity_version,
                            "scale_to_zero_enabled": entity.scale_to_zero_enabled,
                        })

                endpoint = ServingEndpoint(
                    name=ep.name,
                    creator=ep.creator,
                    creation_timestamp=datetime.fromtimestamp(ep.creation_timestamp / 1000) if ep.creation_timestamp else None,
                    last_updated_timestamp=datetime.fromtimestamp(ep.last_updated_timestamp / 1000) if ep.last_updated_timestamp else None,
                    state=ep.state.ready if ep.state else "UNKNOWN",
                    config=ep.config.to_dict() if ep.config else {},
                    served_entities=served_entities,
                )
                serving_endpoints.append(endpoint)

            return serving_endpoints

        except ImportError:
            logger.warning("databricks-sdk not available for serving endpoints")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch serving endpoints: {e}")
            return []

    def get_serving_metrics(
        self,
        endpoint_name: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get serving metrics for a specific endpoint.

        Uses system.serving.served_entities_requests table for metrics.

        Args:
            endpoint_name: Name of the serving endpoint
            hours: Number of hours to look back

        Returns:
            Dictionary with serving metrics
        """
        start_time = datetime.now() - timedelta(hours=hours)

        query = f"""
        SELECT
            COUNT(*) as total_requests,
            AVG(response_time_ms) as avg_latency_ms,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) as p50_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_latency_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99_latency_ms,
            SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count,
            MIN(request_time) as first_request,
            MAX(request_time) as last_request
        FROM system.serving.served_entities_requests
        WHERE endpoint_name = '{endpoint_name}'
            AND request_time >= '{start_time.isoformat()}'
        """

        try:
            results = self._data_layer.query(query)
            if results:
                row = results[0]
                total_requests = row.get("total_requests", 0)
                error_count = row.get("error_count", 0)

                # Calculate requests per second
                first_request = row.get("first_request")
                last_request = row.get("last_request")
                rps = None
                if first_request and last_request and total_requests > 1:
                    duration = (last_request - first_request).total_seconds()
                    if duration > 0:
                        rps = total_requests / duration

                return {
                    "endpoint_name": endpoint_name,
                    "time_range_hours": hours,
                    "total_requests": total_requests,
                    "avg_latency_ms": row.get("avg_latency_ms"),
                    "p50_latency_ms": row.get("p50_latency_ms"),
                    "p95_latency_ms": row.get("p95_latency_ms"),
                    "p99_latency_ms": row.get("p99_latency_ms"),
                    "error_count": error_count,
                    "error_rate": error_count / total_requests if total_requests > 0 else 0,
                    "requests_per_second": rps,
                }
        except Exception as e:
            logger.error(f"Failed to fetch serving metrics: {e}")

        return {
            "endpoint_name": endpoint_name,
            "time_range_hours": hours,
            "total_requests": 0,
            "error": "Could not fetch metrics",
        }

    def compare_model_versions(
        self,
        model_name: str,
        versions: List[str]
    ) -> Dict[str, Any]:
        """
        Compare metrics across multiple model versions.

        Args:
            model_name: Name of the registered model
            versions: List of version numbers to compare

        Returns:
            Dictionary with comparison data
        """
        comparison = {
            "model_name": model_name,
            "versions": {},
            "metric_names": set(),
            "param_names": set(),
        }

        for version in versions:
            try:
                metrics = self.get_model_version_metrics(model_name, version)
                comparison["versions"][version] = metrics

                # Collect metric and param names
                if "training_metrics" in metrics:
                    comparison["metric_names"].update(metrics["training_metrics"].keys())
                if "training_params" in metrics:
                    comparison["param_names"].update(metrics["training_params"].keys())
            except Exception as e:
                logger.warning(f"Could not fetch metrics for version {version}: {e}")
                comparison["versions"][version] = {"error": str(e)}

        # Convert sets to lists for JSON serialization
        comparison["metric_names"] = list(comparison["metric_names"])
        comparison["param_names"] = list(comparison["param_names"])

        # Calculate metric deltas between versions
        if len(versions) >= 2:
            comparison["deltas"] = self._calculate_metric_deltas(comparison["versions"])

        return comparison

    def _calculate_metric_deltas(
        self,
        versions_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        """Calculate metric changes between consecutive versions."""
        deltas = {}
        sorted_versions = sorted(versions_data.keys(), key=lambda x: int(x))

        for i in range(1, len(sorted_versions)):
            prev_version = sorted_versions[i - 1]
            curr_version = sorted_versions[i]

            prev_metrics = versions_data[prev_version].get("training_metrics", {})
            curr_metrics = versions_data[curr_version].get("training_metrics", {})

            delta_key = f"{prev_version}_to_{curr_version}"
            deltas[delta_key] = {}

            for metric_name in set(prev_metrics.keys()) | set(curr_metrics.keys()):
                prev_val = prev_metrics.get(metric_name)
                curr_val = curr_metrics.get(metric_name)

                if prev_val is not None and curr_val is not None:
                    deltas[delta_key][metric_name] = {
                        "previous": prev_val,
                        "current": curr_val,
                        "absolute_change": curr_val - prev_val,
                        "percent_change": ((curr_val - prev_val) / prev_val * 100) if prev_val != 0 else None,
                    }

        return deltas


class MLObservabilityDashboard:
    """
    Dashboard component provider for ML observability.

    Generates data structures for dashboard visualization of
    ML experiments, models, and serving endpoints.
    """

    def __init__(self, mlflow_service: Optional[MLflowService] = None):
        """Initialize dashboard with MLflow service."""
        self._service = mlflow_service or MLflowService()

    def get_experiments_overview(self) -> Dict[str, Any]:
        """Get overview data for experiments dashboard."""
        experiments = self._service.get_all_experiments()

        total_experiments = len(experiments)
        total_runs = sum(e.total_runs for e in experiments)
        successful_runs = sum(e.successful_runs for e in experiments)
        failed_runs = sum(e.failed_runs for e in experiments)
        running = sum(e.running_count for e in experiments)

        return {
            "summary": {
                "total_experiments": total_experiments,
                "total_runs": total_runs,
                "successful_runs": successful_runs,
                "failed_runs": failed_runs,
                "running": running,
                "overall_success_rate": round(successful_runs / total_runs * 100, 2) if total_runs > 0 else 0,
            },
            "experiments": [e.to_dict() for e in experiments[:20]],  # Top 20
            "by_lifecycle_stage": self._group_by_lifecycle(experiments),
        }

    def _group_by_lifecycle(self, experiments: List[ExperimentSummary]) -> Dict[str, int]:
        """Group experiments by lifecycle stage."""
        groups = {}
        for exp in experiments:
            stage = exp.lifecycle_stage
            groups[stage] = groups.get(stage, 0) + 1
        return groups

    def get_models_overview(self) -> Dict[str, Any]:
        """Get overview data for models dashboard."""
        models = self._service.get_registered_models()

        by_stage = {}
        for model in models:
            stage = model.current_stage
            by_stage[stage] = by_stage.get(stage, 0) + 1

        return {
            "summary": {
                "total_models": len(models),
                "by_stage": by_stage,
            },
            "models": [m.to_dict() for m in models[:20]],  # Top 20
            "recent_versions": self._get_recent_versions(models),
        }

    def _get_recent_versions(self, models: List[ModelVersion]) -> List[Dict[str, Any]]:
        """Get most recently updated model versions."""
        sorted_models = sorted(
            models,
            key=lambda m: m.last_updated_timestamp or datetime.min,
            reverse=True
        )
        return [m.to_dict() for m in sorted_models[:10]]

    def get_serving_overview(self) -> Dict[str, Any]:
        """Get overview data for serving endpoints dashboard."""
        endpoints = self._service.get_serving_endpoints()

        by_state = {}
        for ep in endpoints:
            state = ep.state
            by_state[state] = by_state.get(state, 0) + 1

        # Get metrics for each endpoint
        endpoints_with_metrics = []
        for ep in endpoints[:10]:  # Limit to top 10
            metrics = self._service.get_serving_metrics(ep.name, hours=24)
            ep_dict = ep.to_dict()
            ep_dict.update(metrics)
            endpoints_with_metrics.append(ep_dict)

        return {
            "summary": {
                "total_endpoints": len(endpoints),
                "by_state": by_state,
            },
            "endpoints": endpoints_with_metrics,
        }

    def get_job_ml_correlation(self, job_ids: List[str]) -> Dict[str, Any]:
        """
        Get correlation between jobs and their ML experiments.

        Args:
            job_ids: List of job IDs to analyze

        Returns:
            Dictionary with job-ML correlation data
        """
        mapping = self._service.get_job_experiment_mapping(job_ids)

        jobs_with_ml = sum(1 for runs in mapping.values() if runs)
        total_ml_runs = sum(len(runs) for runs in mapping.values())

        return {
            "summary": {
                "total_jobs": len(job_ids),
                "jobs_with_ml": jobs_with_ml,
                "jobs_without_ml": len(job_ids) - jobs_with_ml,
                "total_ml_runs": total_ml_runs,
                "avg_runs_per_job": round(total_ml_runs / jobs_with_ml, 2) if jobs_with_ml > 0 else 0,
            },
            "job_mapping": mapping,
        }

    def get_full_dashboard_data(self, job_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get all dashboard data in one call.

        Args:
            job_ids: Optional list of job IDs for correlation analysis

        Returns:
            Complete dashboard data structure
        """
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "experiments": self.get_experiments_overview(),
            "models": self.get_models_overview(),
            "serving": self.get_serving_overview(),
        }

        if job_ids:
            dashboard["job_correlation"] = self.get_job_ml_correlation(job_ids)

        return dashboard


# Singleton service instance
_mlflow_service: Optional[MLflowService] = None


def get_mlflow_service() -> MLflowService:
    """Get or create singleton MLflow service."""
    global _mlflow_service
    if _mlflow_service is None:
        _mlflow_service = MLflowService()
    return _mlflow_service
