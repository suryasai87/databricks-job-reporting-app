"""
Anomaly Detection Service for Databricks Jobs Monitor.

Provides ML-based and statistical anomaly detection for:
- Job duration anomalies
- Failure pattern detection
- Cost spike detection
- Real-time prediction capabilities
"""

import logging
import uuid
import pickle
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

# Optional ML imports with graceful fallback
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from data.data_layer import get_data_layer

logger = logging.getLogger(__name__)


class AnomalySeverity(Enum):
    """Severity levels for detected anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    DURATION = "duration"
    FAILURE_PATTERN = "failure_pattern"
    COST = "cost"
    RESOURCE_USAGE = "resource_usage"
    FREQUENCY = "frequency"


class ModelType(Enum):
    """Types of ML models for anomaly detection."""
    ISOLATION_FOREST = "isolation_forest"
    STATISTICAL = "statistical"


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    id: str
    job_id: str
    run_id: Optional[str]
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    score: float  # Anomaly score (0-1, higher = more anomalous)
    description: str
    detected_at: datetime
    metric_name: str
    metric_value: float
    expected_value: Optional[float] = None
    threshold: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "run_id": self.run_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "score": self.score,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "expected_value": self.expected_value,
            "threshold": self.threshold,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Anomaly":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            job_id=data["job_id"],
            run_id=data.get("run_id"),
            anomaly_type=AnomalyType(data["anomaly_type"]),
            severity=AnomalySeverity(data["severity"]),
            score=data["score"],
            description=data["description"],
            detected_at=datetime.fromisoformat(data["detected_at"]) if isinstance(data["detected_at"], str) else data["detected_at"],
            metric_name=data["metric_name"],
            metric_value=data["metric_value"],
            expected_value=data.get("expected_value"),
            threshold=data.get("threshold"),
            context=data.get("context", {}),
        )


@dataclass
class AnomalyModel:
    """Represents a trained anomaly detection model."""
    id: str
    job_id: str
    model_type: ModelType
    created_at: datetime
    updated_at: datetime
    training_samples: int
    feature_names: List[str]
    model_data: bytes  # Serialized model
    scaler_data: Optional[bytes] = None  # Serialized scaler
    metrics: Dict[str, float] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "model_type": self.model_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "training_samples": self.training_samples,
            "feature_names": self.feature_names,
            "model_data": base64.b64encode(self.model_data).decode("utf-8"),
            "scaler_data": base64.b64encode(self.scaler_data).decode("utf-8") if self.scaler_data else None,
            "metrics": self.metrics,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnomalyModel":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            job_id=data["job_id"],
            model_type=ModelType(data["model_type"]),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
            updated_at=datetime.fromisoformat(data["updated_at"]) if isinstance(data["updated_at"], str) else data["updated_at"],
            training_samples=data["training_samples"],
            feature_names=data["feature_names"],
            model_data=base64.b64decode(data["model_data"]) if isinstance(data["model_data"], str) else data["model_data"],
            scaler_data=base64.b64decode(data["scaler_data"]) if data.get("scaler_data") else None,
            metrics=data.get("metrics", {}),
            config=data.get("config", {}),
        )


@dataclass
class DetectionResult:
    """Result of an anomaly detection run."""
    job_id: str
    detection_type: AnomalyType
    run_at: datetime
    samples_analyzed: int
    anomalies_found: int
    anomalies: List[Anomaly]
    execution_time_ms: float
    model_used: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "detection_type": self.detection_type.value,
            "run_at": self.run_at.isoformat(),
            "samples_analyzed": self.samples_analyzed,
            "anomalies_found": self.anomalies_found,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "execution_time_ms": self.execution_time_ms,
            "model_used": self.model_used,
            "metadata": self.metadata,
        }


class BaseDetector(ABC):
    """Abstract base class for anomaly detectors."""

    @abstractmethod
    def detect(
        self,
        data: np.ndarray,
        feature_names: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect anomalies in data.

        Args:
            data: 2D array of shape (n_samples, n_features)
            feature_names: Names of features

        Returns:
            Tuple of (labels, scores) where:
                - labels: -1 for anomalies, 1 for normal
                - scores: anomaly scores (higher = more anomalous)
        """
        pass

    @abstractmethod
    def fit(self, data: np.ndarray) -> None:
        """Fit the detector on training data."""
        pass


class StatisticalDetector(BaseDetector):
    """Z-score based statistical anomaly detection."""

    def __init__(self, z_threshold: float = 3.0):
        """
        Initialize statistical detector.

        Args:
            z_threshold: Z-score threshold for anomaly classification
        """
        if not SCIPY_AVAILABLE:
            raise RuntimeError("scipy is required for StatisticalDetector")

        self.z_threshold = z_threshold
        self.mean: Optional[np.ndarray] = None
        self.std: Optional[np.ndarray] = None
        self.fitted = False

    def fit(self, data: np.ndarray) -> None:
        """Calculate mean and std from training data."""
        self.mean = np.mean(data, axis=0)
        self.std = np.std(data, axis=0)
        # Avoid division by zero
        self.std = np.where(self.std == 0, 1e-10, self.std)
        self.fitted = True

    def detect(
        self,
        data: np.ndarray,
        feature_names: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Detect anomalies using Z-score method."""
        if not self.fitted:
            # If not fitted, fit on the data itself
            self.fit(data)

        # Calculate Z-scores
        z_scores = np.abs((data - self.mean) / self.std)

        # Max Z-score across features for each sample
        max_z_scores = np.max(z_scores, axis=1)

        # Convert to labels (-1 = anomaly, 1 = normal)
        labels = np.where(max_z_scores > self.z_threshold, -1, 1)

        # Normalize scores to 0-1 range
        scores = np.clip(max_z_scores / (self.z_threshold * 2), 0, 1)

        return labels, scores

    def get_z_scores(self, data: np.ndarray) -> np.ndarray:
        """Get Z-scores for each feature."""
        if not self.fitted:
            self.fit(data)
        return np.abs((data - self.mean) / self.std)


class MLBasedDetector(BaseDetector):
    """Isolation Forest based ML anomaly detection."""

    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        random_state: int = 42
    ):
        """
        Initialize ML-based detector.

        Args:
            contamination: Expected proportion of anomalies
            n_estimators: Number of trees in the forest
            random_state: Random state for reproducibility
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn is required for MLBasedDetector")

        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.fitted = False

    def fit(self, data: np.ndarray) -> None:
        """Train Isolation Forest model."""
        # Scale the data
        self.scaler = StandardScaler()
        scaled_data = self.scaler.fit_transform(data)

        # Train Isolation Forest
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1
        )
        self.model.fit(scaled_data)
        self.fitted = True

    def detect(
        self,
        data: np.ndarray,
        feature_names: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Detect anomalies using Isolation Forest."""
        if not self.fitted or self.model is None or self.scaler is None:
            raise RuntimeError("Model must be fitted before detection")

        # Scale input data
        scaled_data = self.scaler.transform(data)

        # Predict labels (-1 = anomaly, 1 = normal)
        labels = self.model.predict(scaled_data)

        # Get anomaly scores (negative = more anomalous)
        raw_scores = self.model.decision_function(scaled_data)

        # Convert to 0-1 range (higher = more anomalous)
        # decision_function returns negative values for anomalies
        scores = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-10)

        return labels, scores

    def serialize(self) -> Tuple[bytes, bytes]:
        """Serialize model and scaler for storage."""
        if not self.fitted:
            raise RuntimeError("Model must be fitted before serialization")
        model_data = pickle.dumps(self.model)
        scaler_data = pickle.dumps(self.scaler)
        return model_data, scaler_data

    @classmethod
    def deserialize(cls, model_data: bytes, scaler_data: bytes) -> "MLBasedDetector":
        """Deserialize model and scaler from storage."""
        detector = cls()
        detector.model = pickle.loads(model_data)
        detector.scaler = pickle.loads(scaler_data)
        detector.fitted = True
        return detector


class AnomalyDetector:
    """
    Main anomaly detection service for job monitoring.

    Provides detection for:
    - Duration anomalies (runs taking unusually long/short)
    - Failure patterns (clusters of failures)
    - Cost anomalies (unusual spending spikes)
    """

    def __init__(self):
        """Initialize the anomaly detector."""
        self.data_layer = get_data_layer()
        self._models: Dict[str, AnomalyModel] = {}

    def detect_duration_anomalies(
        self,
        job_id: str,
        lookback_days: int = 30,
        z_threshold: float = 3.0,
        use_ml: bool = True
    ) -> DetectionResult:
        """
        Detect runs with unusual duration.

        Args:
            job_id: Job ID to analyze
            lookback_days: Number of days of history to analyze
            z_threshold: Z-score threshold for statistical detection
            use_ml: Use ML-based detection if available

        Returns:
            DetectionResult with detected anomalies
        """
        import time
        start_time = time.time()

        # Fetch run history
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        query = """
            SELECT
                run_id,
                job_id,
                result_state,
                TIMESTAMPDIFF(SECOND, period.start_time, period.end_time) as duration_seconds,
                period.start_time as start_time,
                period.end_time as end_time
            FROM system.lakeflow.job_run_timeline
            WHERE job_id = %(job_id)s
                AND period.start_time >= %(cutoff_date)s
                AND period.end_time IS NOT NULL
            ORDER BY period.start_time DESC
        """

        try:
            runs = self.data_layer.query(query, {"job_id": job_id, "cutoff_date": cutoff_date})
        except Exception as e:
            logger.error(f"Failed to fetch runs for job {job_id}: {e}")
            return DetectionResult(
                job_id=job_id,
                detection_type=AnomalyType.DURATION,
                run_at=datetime.now(),
                samples_analyzed=0,
                anomalies_found=0,
                anomalies=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )

        if len(runs) < 5:
            return DetectionResult(
                job_id=job_id,
                detection_type=AnomalyType.DURATION,
                run_at=datetime.now(),
                samples_analyzed=len(runs),
                anomalies_found=0,
                anomalies=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"reason": "Insufficient data for analysis"}
            )

        # Prepare data
        durations = np.array([r["duration_seconds"] for r in runs if r["duration_seconds"] is not None]).reshape(-1, 1)

        # Choose detector
        anomalies = []
        model_used = None

        if use_ml and SKLEARN_AVAILABLE and len(durations) >= 20:
            detector = MLBasedDetector(contamination=0.1)
            detector.fit(durations)
            labels, scores = detector.detect(durations, ["duration_seconds"])
            model_used = "isolation_forest"
        elif SCIPY_AVAILABLE:
            detector = StatisticalDetector(z_threshold=z_threshold)
            detector.fit(durations)
            labels, scores = detector.detect(durations, ["duration_seconds"])
            model_used = "statistical_z_score"
        else:
            # Fallback to simple percentile-based detection
            p5, p95 = np.percentile(durations, [5, 95])
            labels = np.where((durations.flatten() < p5) | (durations.flatten() > p95), -1, 1)
            scores = np.zeros_like(labels, dtype=float)
            model_used = "percentile"

        # Create anomaly records
        mean_duration = np.mean(durations)
        std_duration = np.std(durations)

        for i, (run, label, score) in enumerate(zip(runs, labels, scores)):
            if label == -1:
                duration = run["duration_seconds"]
                deviation = abs(duration - mean_duration) / (std_duration + 1e-10)

                # Determine severity based on deviation
                if deviation > 5:
                    severity = AnomalySeverity.CRITICAL
                elif deviation > 4:
                    severity = AnomalySeverity.HIGH
                elif deviation > 3:
                    severity = AnomalySeverity.MEDIUM
                else:
                    severity = AnomalySeverity.LOW

                anomaly = Anomaly(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    run_id=run["run_id"],
                    anomaly_type=AnomalyType.DURATION,
                    severity=severity,
                    score=float(score),
                    description=f"Run duration ({duration}s) deviates {deviation:.1f} std from mean ({mean_duration:.1f}s)",
                    detected_at=datetime.now(),
                    metric_name="duration_seconds",
                    metric_value=float(duration),
                    expected_value=float(mean_duration),
                    threshold=float(z_threshold * std_duration),
                    context={
                        "start_time": run["start_time"].isoformat() if run["start_time"] else None,
                        "end_time": run["end_time"].isoformat() if run["end_time"] else None,
                        "result_state": run["result_state"],
                        "deviation_std": deviation,
                    }
                )
                anomalies.append(anomaly)

        # Store detected anomalies
        self._store_anomalies(anomalies)

        return DetectionResult(
            job_id=job_id,
            detection_type=AnomalyType.DURATION,
            run_at=datetime.now(),
            samples_analyzed=len(runs),
            anomalies_found=len(anomalies),
            anomalies=anomalies,
            execution_time_ms=(time.time() - start_time) * 1000,
            model_used=model_used,
            metadata={
                "mean_duration": float(mean_duration),
                "std_duration": float(std_duration),
                "lookback_days": lookback_days,
            }
        )

    def detect_failure_patterns(
        self,
        job_id: str,
        lookback_days: int = 30,
        failure_window_hours: int = 24,
        min_failures_for_pattern: int = 3
    ) -> DetectionResult:
        """
        Identify failure clusters and patterns.

        Args:
            job_id: Job ID to analyze
            lookback_days: Number of days of history to analyze
            failure_window_hours: Time window to consider failures as clustered
            min_failures_for_pattern: Minimum failures in window to detect pattern

        Returns:
            DetectionResult with detected failure patterns
        """
        import time
        start_time = time.time()

        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        query = """
            SELECT
                run_id,
                job_id,
                result_state,
                period.start_time as start_time,
                period.end_time as end_time,
                error_message
            FROM system.lakeflow.job_run_timeline
            WHERE job_id = %(job_id)s
                AND period.start_time >= %(cutoff_date)s
                AND result_state IN ('FAILED', 'TIMED_OUT', 'CANCELED')
            ORDER BY period.start_time DESC
        """

        try:
            failures = self.data_layer.query(query, {"job_id": job_id, "cutoff_date": cutoff_date})
        except Exception as e:
            logger.error(f"Failed to fetch failures for job {job_id}: {e}")
            return DetectionResult(
                job_id=job_id,
                detection_type=AnomalyType.FAILURE_PATTERN,
                run_at=datetime.now(),
                samples_analyzed=0,
                anomalies_found=0,
                anomalies=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )

        if len(failures) < min_failures_for_pattern:
            return DetectionResult(
                job_id=job_id,
                detection_type=AnomalyType.FAILURE_PATTERN,
                run_at=datetime.now(),
                samples_analyzed=len(failures),
                anomalies_found=0,
                anomalies=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"reason": "Insufficient failures for pattern analysis"}
            )

        anomalies = []
        window_delta = timedelta(hours=failure_window_hours)

        # Find failure clusters
        for i, failure in enumerate(failures):
            failure_time = failure["start_time"]
            if not failure_time:
                continue

            # Count failures in window
            window_start = failure_time - window_delta
            window_end = failure_time + window_delta

            cluster_failures = [
                f for f in failures
                if f["start_time"] and window_start <= f["start_time"] <= window_end
            ]

            if len(cluster_failures) >= min_failures_for_pattern:
                # Check if we already reported this cluster
                cluster_id = f"{job_id}_{failure_time.date()}_{len(cluster_failures)}"
                existing = [a for a in anomalies if a.context.get("cluster_id") == cluster_id]

                if not existing:
                    # Determine severity based on cluster size
                    if len(cluster_failures) >= 10:
                        severity = AnomalySeverity.CRITICAL
                    elif len(cluster_failures) >= 7:
                        severity = AnomalySeverity.HIGH
                    elif len(cluster_failures) >= 5:
                        severity = AnomalySeverity.MEDIUM
                    else:
                        severity = AnomalySeverity.LOW

                    # Analyze error messages for patterns
                    error_messages = [f.get("error_message", "") for f in cluster_failures if f.get("error_message")]
                    common_patterns = self._find_common_error_patterns(error_messages)

                    anomaly = Anomaly(
                        id=str(uuid.uuid4()),
                        job_id=job_id,
                        run_id=failure["run_id"],
                        anomaly_type=AnomalyType.FAILURE_PATTERN,
                        severity=severity,
                        score=min(len(cluster_failures) / 10.0, 1.0),
                        description=f"Failure cluster detected: {len(cluster_failures)} failures in {failure_window_hours}h window",
                        detected_at=datetime.now(),
                        metric_name="failure_count",
                        metric_value=float(len(cluster_failures)),
                        expected_value=0.0,
                        threshold=float(min_failures_for_pattern),
                        context={
                            "cluster_id": cluster_id,
                            "window_start": window_start.isoformat(),
                            "window_end": window_end.isoformat(),
                            "failure_run_ids": [f["run_id"] for f in cluster_failures],
                            "common_error_patterns": common_patterns,
                            "failure_types": list(set(f["result_state"] for f in cluster_failures)),
                        }
                    )
                    anomalies.append(anomaly)

        # Store detected anomalies
        self._store_anomalies(anomalies)

        return DetectionResult(
            job_id=job_id,
            detection_type=AnomalyType.FAILURE_PATTERN,
            run_at=datetime.now(),
            samples_analyzed=len(failures),
            anomalies_found=len(anomalies),
            anomalies=anomalies,
            execution_time_ms=(time.time() - start_time) * 1000,
            metadata={
                "total_failures": len(failures),
                "lookback_days": lookback_days,
                "failure_window_hours": failure_window_hours,
            }
        )

    def detect_cost_anomalies(
        self,
        job_id: str,
        lookback_days: int = 30,
        z_threshold: float = 2.5
    ) -> DetectionResult:
        """
        Detect unusual cost spikes for a job.

        Args:
            job_id: Job ID to analyze
            lookback_days: Number of days of history to analyze
            z_threshold: Z-score threshold for anomaly detection

        Returns:
            DetectionResult with detected cost anomalies
        """
        import time
        start_time = time.time()

        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        # Query cost data from billing tables
        query = """
            SELECT
                usage_date,
                SUM(usage_quantity * list_price) as daily_cost,
                SUM(usage_quantity) as dbu_usage
            FROM system.billing.usage u
            JOIN system.billing.list_prices p
                ON u.sku_name = p.sku_name
                AND u.usage_date >= p.price_start_time
                AND (p.price_end_time IS NULL OR u.usage_date < p.price_end_time)
            WHERE u.usage_metadata.job_id = %(job_id)s
                AND u.usage_date >= %(cutoff_date)s
            GROUP BY usage_date
            ORDER BY usage_date DESC
        """

        try:
            costs = self.data_layer.query(query, {"job_id": job_id, "cutoff_date": cutoff_date})
        except Exception as e:
            logger.error(f"Failed to fetch costs for job {job_id}: {e}")
            return DetectionResult(
                job_id=job_id,
                detection_type=AnomalyType.COST,
                run_at=datetime.now(),
                samples_analyzed=0,
                anomalies_found=0,
                anomalies=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )

        if len(costs) < 5:
            return DetectionResult(
                job_id=job_id,
                detection_type=AnomalyType.COST,
                run_at=datetime.now(),
                samples_analyzed=len(costs),
                anomalies_found=0,
                anomalies=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"reason": "Insufficient cost data for analysis"}
            )

        # Prepare data
        daily_costs = np.array([c["daily_cost"] for c in costs if c["daily_cost"] is not None])

        if len(daily_costs) < 5:
            return DetectionResult(
                job_id=job_id,
                detection_type=AnomalyType.COST,
                run_at=datetime.now(),
                samples_analyzed=len(costs),
                anomalies_found=0,
                anomalies=[],
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"reason": "Insufficient valid cost values"}
            )

        mean_cost = np.mean(daily_costs)
        std_cost = np.std(daily_costs)

        anomalies = []

        if SCIPY_AVAILABLE:
            detector = StatisticalDetector(z_threshold=z_threshold)
            detector.fit(daily_costs.reshape(-1, 1))
            labels, scores = detector.detect(daily_costs.reshape(-1, 1), ["daily_cost"])

            for i, (cost_data, label, score) in enumerate(zip(costs, labels, scores)):
                if label == -1:
                    cost = cost_data["daily_cost"]
                    if cost is None:
                        continue

                    deviation = abs(cost - mean_cost) / (std_cost + 1e-10)

                    # Higher severity for cost spikes
                    if deviation > 4 or cost > mean_cost * 3:
                        severity = AnomalySeverity.CRITICAL
                    elif deviation > 3 or cost > mean_cost * 2:
                        severity = AnomalySeverity.HIGH
                    elif deviation > 2.5:
                        severity = AnomalySeverity.MEDIUM
                    else:
                        severity = AnomalySeverity.LOW

                    anomaly = Anomaly(
                        id=str(uuid.uuid4()),
                        job_id=job_id,
                        run_id=None,
                        anomaly_type=AnomalyType.COST,
                        severity=severity,
                        score=float(score),
                        description=f"Cost spike on {cost_data['usage_date']}: ${cost:.2f} ({deviation:.1f}x std from mean ${mean_cost:.2f})",
                        detected_at=datetime.now(),
                        metric_name="daily_cost",
                        metric_value=float(cost),
                        expected_value=float(mean_cost),
                        threshold=float(z_threshold * std_cost),
                        context={
                            "usage_date": str(cost_data["usage_date"]),
                            "dbu_usage": cost_data.get("dbu_usage"),
                            "deviation_std": deviation,
                            "cost_multiplier": cost / mean_cost if mean_cost > 0 else 0,
                        }
                    )
                    anomalies.append(anomaly)

        # Store detected anomalies
        self._store_anomalies(anomalies)

        return DetectionResult(
            job_id=job_id,
            detection_type=AnomalyType.COST,
            run_at=datetime.now(),
            samples_analyzed=len(costs),
            anomalies_found=len(anomalies),
            anomalies=anomalies,
            execution_time_ms=(time.time() - start_time) * 1000,
            model_used="statistical_z_score",
            metadata={
                "mean_daily_cost": float(mean_cost),
                "std_daily_cost": float(std_cost),
                "total_cost": float(np.sum(daily_costs)),
                "lookback_days": lookback_days,
            }
        )

    def train_model(
        self,
        job_id: str,
        model_type: ModelType = ModelType.ISOLATION_FOREST,
        lookback_days: int = 90,
        feature_columns: Optional[List[str]] = None
    ) -> AnomalyModel:
        """
        Train an anomaly detection model for a specific job.

        Args:
            job_id: Job ID to train model for
            model_type: Type of model to train
            lookback_days: Days of historical data to use
            feature_columns: Features to include in model

        Returns:
            Trained AnomalyModel
        """
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn is required for model training")

        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        # Default features
        if feature_columns is None:
            feature_columns = ["duration_seconds", "task_count", "attempt_number"]

        # Fetch training data
        query = """
            SELECT
                run_id,
                TIMESTAMPDIFF(SECOND, period.start_time, period.end_time) as duration_seconds,
                COALESCE(attempt_number, 1) as attempt_number
            FROM system.lakeflow.job_run_timeline
            WHERE job_id = %(job_id)s
                AND period.start_time >= %(cutoff_date)s
                AND period.end_time IS NOT NULL
                AND result_state = 'SUCCESS'
            ORDER BY period.start_time DESC
        """

        runs = self.data_layer.query(query, {"job_id": job_id, "cutoff_date": cutoff_date})

        if len(runs) < 20:
            raise ValueError(f"Insufficient training data: {len(runs)} runs (minimum 20 required)")

        # Prepare feature matrix
        features = []
        available_features = []

        for col in feature_columns:
            if col in runs[0]:
                values = [r.get(col, 0) or 0 for r in runs]
                features.append(values)
                available_features.append(col)

        if not features:
            raise ValueError("No valid features found in data")

        X = np.array(features).T

        # Train model based on type
        if model_type == ModelType.ISOLATION_FOREST:
            detector = MLBasedDetector(contamination=0.1)
            detector.fit(X)
            model_data, scaler_data = detector.serialize()
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        # Create model record
        model = AnomalyModel(
            id=str(uuid.uuid4()),
            job_id=job_id,
            model_type=model_type,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            training_samples=len(runs),
            feature_names=available_features,
            model_data=model_data,
            scaler_data=scaler_data,
            metrics={
                "training_samples": len(runs),
                "features_count": len(available_features),
            },
            config={
                "lookback_days": lookback_days,
                "contamination": 0.1,
            }
        )

        # Store model
        self._store_model(model)
        self._models[job_id] = model

        return model

    def predict(
        self,
        job_id: str,
        metrics: Dict[str, float]
    ) -> Tuple[bool, float, str]:
        """
        Predict if given metrics are anomalous.

        Args:
            job_id: Job ID to predict for
            metrics: Dictionary of metric values

        Returns:
            Tuple of (is_anomaly, score, description)
        """
        # Load model if not cached
        if job_id not in self._models:
            model = self._load_model(job_id)
            if model is None:
                return False, 0.0, "No model available for this job"
            self._models[job_id] = model

        model = self._models[job_id]

        # Prepare features in correct order
        features = []
        for feature_name in model.feature_names:
            if feature_name not in metrics:
                return False, 0.0, f"Missing required feature: {feature_name}"
            features.append(metrics[feature_name])

        X = np.array([features])

        # Deserialize and predict
        detector = MLBasedDetector.deserialize(model.model_data, model.scaler_data)
        labels, scores = detector.detect(X, model.feature_names)

        is_anomaly = labels[0] == -1
        score = float(scores[0])

        if is_anomaly:
            description = f"Anomaly detected with score {score:.2f}"
        else:
            description = f"Normal behavior (score: {score:.2f})"

        return is_anomaly, score, description

    def _find_common_error_patterns(self, error_messages: List[str]) -> List[str]:
        """Find common patterns in error messages."""
        if not error_messages:
            return []

        # Simple keyword extraction
        common_patterns = []
        keywords = ["timeout", "memory", "oom", "disk", "network", "connection",
                    "permission", "quota", "limit", "resource", "spark", "driver"]

        for keyword in keywords:
            count = sum(1 for msg in error_messages if keyword.lower() in msg.lower())
            if count >= len(error_messages) * 0.3:  # Present in 30%+ of errors
                common_patterns.append(f"{keyword}: {count}/{len(error_messages)}")

        return common_patterns

    def _store_anomalies(self, anomalies: List[Anomaly]) -> None:
        """Store detected anomalies to database."""
        if not anomalies:
            return

        try:
            for anomaly in anomalies:
                query = """
                    INSERT INTO jobs_monitor.ml.detected_anomalies
                    (id, job_id, run_id, anomaly_type, severity, score, description,
                     detected_at, metric_name, metric_value, expected_value, threshold, context)
                    VALUES (%(id)s, %(job_id)s, %(run_id)s, %(anomaly_type)s, %(severity)s,
                            %(score)s, %(description)s, %(detected_at)s, %(metric_name)s,
                            %(metric_value)s, %(expected_value)s, %(threshold)s, %(context)s)
                """
                self.data_layer.query(query, {
                    "id": anomaly.id,
                    "job_id": anomaly.job_id,
                    "run_id": anomaly.run_id,
                    "anomaly_type": anomaly.anomaly_type.value,
                    "severity": anomaly.severity.value,
                    "score": anomaly.score,
                    "description": anomaly.description,
                    "detected_at": anomaly.detected_at,
                    "metric_name": anomaly.metric_name,
                    "metric_value": anomaly.metric_value,
                    "expected_value": anomaly.expected_value,
                    "threshold": anomaly.threshold,
                    "context": str(anomaly.context),
                })
        except Exception as e:
            logger.error(f"Failed to store anomalies: {e}")

    def _store_model(self, model: AnomalyModel) -> None:
        """Store trained model to database."""
        try:
            query = """
                INSERT INTO jobs_monitor.ml.anomaly_models
                (id, job_id, model_type, created_at, updated_at, training_samples,
                 feature_names, model_data, scaler_data, metrics, config)
                VALUES (%(id)s, %(job_id)s, %(model_type)s, %(created_at)s, %(updated_at)s,
                        %(training_samples)s, %(feature_names)s, %(model_data)s,
                        %(scaler_data)s, %(metrics)s, %(config)s)
            """
            model_dict = model.to_dict()
            self.data_layer.query(query, model_dict)
        except Exception as e:
            logger.error(f"Failed to store model: {e}")

    def _load_model(self, job_id: str) -> Optional[AnomalyModel]:
        """Load model from database."""
        try:
            query = """
                SELECT * FROM jobs_monitor.ml.anomaly_models
                WHERE job_id = %(job_id)s
                ORDER BY updated_at DESC
                LIMIT 1
            """
            results = self.data_layer.query(query, {"job_id": job_id})
            if results:
                return AnomalyModel.from_dict(results[0])
            return None
        except Exception as e:
            logger.error(f"Failed to load model for job {job_id}: {e}")
            return None


class AnomalyAlertService:
    """Service to create alerts from detected anomalies."""

    def __init__(self):
        """Initialize alert service."""
        self.data_layer = get_data_layer()

    def create_alert_from_anomaly(
        self,
        anomaly: Anomaly,
        notify_channels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create an alert from a detected anomaly.

        Args:
            anomaly: Detected anomaly
            notify_channels: Notification channels (email, slack, etc.)

        Returns:
            Created alert record
        """
        alert = {
            "id": str(uuid.uuid4()),
            "anomaly_id": anomaly.id,
            "job_id": anomaly.job_id,
            "severity": anomaly.severity.value,
            "title": f"{anomaly.anomaly_type.value.title()} Anomaly Detected",
            "message": anomaly.description,
            "created_at": datetime.now().isoformat(),
            "status": "open",
            "notify_channels": notify_channels or [],
            "metadata": {
                "anomaly_type": anomaly.anomaly_type.value,
                "score": anomaly.score,
                "metric_name": anomaly.metric_name,
                "metric_value": anomaly.metric_value,
            }
        }

        # Store alert
        try:
            query = """
                INSERT INTO jobs_monitor.alerts
                (id, anomaly_id, job_id, severity, title, message, created_at, status, metadata)
                VALUES (%(id)s, %(anomaly_id)s, %(job_id)s, %(severity)s, %(title)s,
                        %(message)s, %(created_at)s, %(status)s, %(metadata)s)
            """
            self.data_layer.query(query, alert)
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")

        return alert

    def create_alerts_from_detection_result(
        self,
        result: DetectionResult,
        min_severity: AnomalySeverity = AnomalySeverity.MEDIUM,
        notify_channels: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Create alerts from all anomalies in a detection result.

        Args:
            result: Detection result containing anomalies
            min_severity: Minimum severity to create alert for
            notify_channels: Notification channels

        Returns:
            List of created alerts
        """
        severity_order = {
            AnomalySeverity.LOW: 0,
            AnomalySeverity.MEDIUM: 1,
            AnomalySeverity.HIGH: 2,
            AnomalySeverity.CRITICAL: 3,
        }

        alerts = []
        for anomaly in result.anomalies:
            if severity_order[anomaly.severity] >= severity_order[min_severity]:
                alert = self.create_alert_from_anomaly(anomaly, notify_channels)
                alerts.append(alert)

        return alerts

    def get_open_alerts(
        self,
        job_id: Optional[str] = None,
        min_severity: Optional[AnomalySeverity] = None
    ) -> List[Dict[str, Any]]:
        """
        Get open alerts, optionally filtered by job and severity.

        Args:
            job_id: Filter by job ID
            min_severity: Filter by minimum severity

        Returns:
            List of open alerts
        """
        query = "SELECT * FROM jobs_monitor.alerts WHERE status = 'open'"
        params = {}

        if job_id:
            query += " AND job_id = %(job_id)s"
            params["job_id"] = job_id

        if min_severity:
            severity_order = {
                AnomalySeverity.LOW: 0,
                AnomalySeverity.MEDIUM: 1,
                AnomalySeverity.HIGH: 2,
                AnomalySeverity.CRITICAL: 3,
            }
            severities = [s.value for s, order in severity_order.items()
                         if order >= severity_order[min_severity]]
            query += f" AND severity IN ({','.join(['%s'] * len(severities))})"
            # Note: This would need parameter handling for IN clause

        query += " ORDER BY created_at DESC"

        try:
            return self.data_layer.query(query, params)
        except Exception as e:
            logger.error(f"Failed to fetch alerts: {e}")
            return []

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert ID
            acknowledged_by: User who acknowledged

        Returns:
            Success status
        """
        try:
            query = """
                UPDATE jobs_monitor.alerts
                SET status = 'acknowledged',
                    acknowledged_by = %(acknowledged_by)s,
                    acknowledged_at = %(acknowledged_at)s
                WHERE id = %(alert_id)s
            """
            self.data_layer.query(query, {
                "alert_id": alert_id,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": datetime.now().isoformat(),
            })
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False

    def resolve_alert(self, alert_id: str, resolved_by: str, resolution_notes: str = "") -> bool:
        """
        Resolve an alert.

        Args:
            alert_id: Alert ID
            resolved_by: User who resolved
            resolution_notes: Notes about resolution

        Returns:
            Success status
        """
        try:
            query = """
                UPDATE jobs_monitor.alerts
                SET status = 'resolved',
                    resolved_by = %(resolved_by)s,
                    resolved_at = %(resolved_at)s,
                    resolution_notes = %(resolution_notes)s
                WHERE id = %(alert_id)s
            """
            self.data_layer.query(query, {
                "alert_id": alert_id,
                "resolved_by": resolved_by,
                "resolved_at": datetime.now().isoformat(),
                "resolution_notes": resolution_notes,
            })
            return True
        except Exception as e:
            logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False


# Singleton instance
_anomaly_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get or create the singleton anomaly detector."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector
