"""
Unified data access layer with Lakebase acceleration.
Falls back to SQL Warehouse if Lakebase unavailable.

Lakebase provides PostgreSQL-compatible access to synced Delta tables
with sub-100ms query latency compared to 500ms-5s for SQL Warehouse.
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

# PostgreSQL driver for Lakebase
try:
    import psycopg2
    from psycopg2 import pool, OperationalError, InterfaceError
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available - Lakebase support disabled")

# Databricks SQL for fallback
try:
    from databricks import sql as databricks_sql
    DATABRICKS_SQL_AVAILABLE = True
except ImportError:
    DATABRICKS_SQL_AVAILABLE = False
    logger.warning("databricks-sql-connector not available")


class DataSource(Enum):
    """Data source types."""
    LAKEBASE = "lakebase"
    SQL_WAREHOUSE = "sql_warehouse"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5      # Failures before opening
    recovery_timeout: int = 30      # Seconds before trying again
    half_open_max_calls: int = 3    # Test calls in half-open state


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_calls: int = 0

    def can_execute(self) -> bool:
        """Check if request should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.config.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    return True
            return False

        return self.half_open_calls < self.config.half_open_max_calls

    def record_success(self):
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.config.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker CLOSED (recovered)")
        self.failure_count = 0

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker OPEN (failed during recovery)")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN (threshold {self.config.failure_threshold} reached)")


@dataclass
class LakebaseConfig:
    """Configuration for Lakebase connection."""
    host: str = ""
    port: int = 5432
    database: str = "jobs_monitor_db"
    user: str = "token"  # Databricks PAT auth
    password: str = ""   # Databricks PAT
    ssl_mode: str = "require"
    min_connections: int = 2
    max_connections: int = 10
    connect_timeout: int = 10
    statement_timeout: int = 30000  # 30 seconds

    # HA configuration
    read_replica_host: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LakebaseConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.environ.get("LAKEBASE_HOST", ""),
            port=int(os.environ.get("LAKEBASE_PORT", "5432")),
            database=os.environ.get("LAKEBASE_DATABASE", "jobs_monitor_db"),
            password=os.environ.get("DATABRICKS_TOKEN", ""),
            read_replica_host=os.environ.get("LAKEBASE_READ_REPLICA_HOST"),
        )

    @property
    def is_configured(self) -> bool:
        """Check if Lakebase is configured."""
        return bool(self.host and self.password)


@dataclass
class SQLWarehouseConfig:
    """Configuration for SQL Warehouse connection."""
    host: str = ""
    http_path: str = ""
    token: str = ""
    warehouse_id: str = ""

    @classmethod
    def from_env(cls) -> "SQLWarehouseConfig":
        """Create configuration from environment variables."""
        host = os.environ.get("DATABRICKS_HOST", "")
        # Remove https:// prefix if present
        if host.startswith("https://"):
            host = host[8:]
        if host.startswith("http://"):
            host = host[7:]

        warehouse_id = os.environ.get("WAREHOUSE_ID", "")
        http_path = os.environ.get("SQL_WAREHOUSE_HTTP_PATH", "")
        if not http_path and warehouse_id:
            http_path = f"/sql/1.0/warehouses/{warehouse_id}"

        return cls(
            host=host,
            http_path=http_path,
            token=os.environ.get("DATABRICKS_TOKEN", ""),
            warehouse_id=warehouse_id,
        )

    @property
    def is_configured(self) -> bool:
        """Check if SQL Warehouse is configured."""
        return bool(self.host and self.http_path and self.token)


class DataAccessLayer:
    """
    Unified data access with Lakebase acceleration and SQL Warehouse fallback.

    Priority:
    1. Lakebase (if configured and healthy) - Sub-100ms queries
    2. SQL Warehouse (fallback) - 500ms-5s queries
    """

    # Table mappings: Delta table -> Lakebase synced table
    TABLE_MAPPINGS = {
        "system.lakeflow.jobs": "jobs_monitor.synced.jobs",
        "system.lakeflow.job_tasks": "jobs_monitor.synced.job_tasks",
        "system.lakeflow.job_run_timeline": "jobs_monitor.synced.job_run_timeline",
        "system.lakeflow.job_task_run_timeline": "jobs_monitor.synced.job_task_run_timeline",
        "system.billing.usage": "jobs_monitor.synced.billing_usage",
        "system.billing.list_prices": "jobs_monitor.synced.list_prices",
        "system.compute.clusters": "jobs_monitor.synced.clusters",
    }

    def __init__(
        self,
        lakebase_config: Optional[LakebaseConfig] = None,
        warehouse_config: Optional[SQLWarehouseConfig] = None,
        prefer_lakebase: bool = True
    ):
        """Initialize data access layer with optional configurations."""
        self.lakebase_config = lakebase_config or LakebaseConfig.from_env()
        self.warehouse_config = warehouse_config or SQLWarehouseConfig.from_env()
        self.prefer_lakebase = prefer_lakebase

        # Connection pools
        self._lakebase_pool: Optional[pool.ThreadedConnectionPool] = None
        self._lakebase_replica_pool: Optional[pool.ThreadedConnectionPool] = None
        self._lakebase_healthy = False

        # Circuit breaker for Lakebase
        self._circuit_breaker = CircuitBreaker()

        # Initialize Lakebase if configured
        if self.lakebase_config.is_configured and PSYCOPG2_AVAILABLE:
            self._init_lakebase_pool()

    def _init_lakebase_pool(self):
        """Initialize Lakebase connection pool."""
        try:
            self._lakebase_pool = pool.ThreadedConnectionPool(
                minconn=self.lakebase_config.min_connections,
                maxconn=self.lakebase_config.max_connections,
                host=self.lakebase_config.host,
                port=self.lakebase_config.port,
                database=self.lakebase_config.database,
                user=self.lakebase_config.user,
                password=self.lakebase_config.password,
                sslmode=self.lakebase_config.ssl_mode,
                connect_timeout=self.lakebase_config.connect_timeout,
                options=f"-c statement_timeout={self.lakebase_config.statement_timeout}",
            )
            # Test connection
            conn = self._lakebase_pool.getconn()
            conn.cursor().execute("SELECT 1")
            self._lakebase_pool.putconn(conn)
            self._lakebase_healthy = True
            logger.info(f"Lakebase connection pool initialized: {self.lakebase_config.host}")

            # Initialize read replica pool if configured
            if self.lakebase_config.read_replica_host:
                self._init_replica_pool()

        except Exception as e:
            logger.error(f"Lakebase initialization failed: {e}")
            self._lakebase_healthy = False

    def _init_replica_pool(self):
        """Initialize read replica connection pool for HA."""
        try:
            self._lakebase_replica_pool = pool.ThreadedConnectionPool(
                minconn=self.lakebase_config.min_connections,
                maxconn=self.lakebase_config.max_connections * 2,  # More read capacity
                host=self.lakebase_config.read_replica_host,
                port=self.lakebase_config.port,
                database=self.lakebase_config.database,
                user=self.lakebase_config.user,
                password=self.lakebase_config.password,
                sslmode=self.lakebase_config.ssl_mode,
                connect_timeout=self.lakebase_config.connect_timeout,
                options=f"-c statement_timeout={self.lakebase_config.statement_timeout} -c default_transaction_read_only=on",
            )
            logger.info(f"Lakebase read replica pool initialized: {self.lakebase_config.read_replica_host}")
        except Exception as e:
            logger.warning(f"Read replica pool initialization failed: {e}")
            self._lakebase_replica_pool = None

    @contextmanager
    def _get_lakebase_connection(self, read_only: bool = True):
        """Get connection from Lakebase pool."""
        conn = None
        pool_to_use = self._lakebase_pool

        # Use replica pool for read operations if available
        if read_only and self._lakebase_replica_pool:
            try:
                conn = self._lakebase_replica_pool.getconn()
                yield conn
                return
            except Exception:
                # Fall through to primary
                if conn:
                    try:
                        self._lakebase_replica_pool.putconn(conn)
                    except Exception:
                        pass
                conn = None

        try:
            conn = pool_to_use.getconn()
            yield conn
        finally:
            if conn and pool_to_use:
                pool_to_use.putconn(conn)

    def _get_warehouse_connection(self):
        """Get SQL Warehouse connection."""
        if not DATABRICKS_SQL_AVAILABLE:
            raise RuntimeError("databricks-sql-connector not available")
        return databricks_sql.connect(
            server_hostname=self.warehouse_config.host,
            http_path=self.warehouse_config.http_path,
            access_token=self.warehouse_config.token,
        )

    def _translate_table_name(self, query: str, to_lakebase: bool = True) -> str:
        """Translate table names between Delta and Lakebase schemas."""
        translated = query
        if to_lakebase:
            for delta_table, lakebase_table in self.TABLE_MAPPINGS.items():
                translated = translated.replace(delta_table, lakebase_table)
        else:
            for delta_table, lakebase_table in self.TABLE_MAPPINGS.items():
                translated = translated.replace(lakebase_table, delta_table)
        return translated

    def get_active_source(self) -> DataSource:
        """Get currently active data source."""
        if (self.prefer_lakebase and
            self._lakebase_healthy and
            self._circuit_breaker.can_execute()):
            return DataSource.LAKEBASE
        return DataSource.SQL_WAREHOUSE

    def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        force_warehouse: bool = False,
        allow_fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Execute query with automatic source selection.

        Args:
            sql: SQL query (use Delta table names, auto-translated for Lakebase)
            params: Query parameters
            force_warehouse: Force SQL Warehouse even if Lakebase available
            allow_fallback: Allow fallback to SQL Warehouse on Lakebase failure

        Returns:
            List of dictionaries with query results
        """
        source = DataSource.SQL_WAREHOUSE if force_warehouse else self.get_active_source()

        if source == DataSource.LAKEBASE:
            try:
                result = self._query_lakebase(sql, params)
                self._circuit_breaker.record_success()
                return result
            except Exception as e:
                self._circuit_breaker.record_failure()
                logger.error(f"Lakebase query failed: {e}")

                if allow_fallback:
                    logger.info("Falling back to SQL Warehouse")
                    return self._query_warehouse(sql, params)
                raise
        else:
            return self._query_warehouse(sql, params)

    def _query_lakebase(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute query against Lakebase."""
        translated_sql = self._translate_table_name(sql, to_lakebase=True)

        with self._get_lakebase_connection(read_only=True) as conn:
            with conn.cursor() as cur:
                cur.execute(translated_sql, params)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                return []

    def _query_warehouse(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute query against SQL Warehouse."""
        with self._get_warehouse_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)

            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            return []

    def health_check(self) -> Dict[str, Any]:
        """Check health of all data sources."""
        status = {
            "lakebase": {
                "configured": self.lakebase_config.is_configured,
                "healthy": False,
                "latency_ms": None,
                "circuit_breaker_state": self._circuit_breaker.state.value,
                "failure_count": self._circuit_breaker.failure_count,
            },
            "sql_warehouse": {
                "configured": self.warehouse_config.is_configured,
                "healthy": False,
                "latency_ms": None,
            },
            "active_source": None,
        }

        # Test Lakebase
        if self.lakebase_config.is_configured and self._lakebase_pool:
            try:
                start = time.time()
                with self._get_lakebase_connection() as conn:
                    conn.cursor().execute("SELECT 1")
                status["lakebase"]["healthy"] = True
                status["lakebase"]["latency_ms"] = round((time.time() - start) * 1000, 2)
                self._lakebase_healthy = True
            except Exception as e:
                status["lakebase"]["error"] = str(e)
                self._lakebase_healthy = False

        # Test SQL Warehouse
        if self.warehouse_config.is_configured and DATABRICKS_SQL_AVAILABLE:
            try:
                start = time.time()
                with self._get_warehouse_connection() as conn:
                    conn.cursor().execute("SELECT 1")
                status["sql_warehouse"]["healthy"] = True
                status["sql_warehouse"]["latency_ms"] = round((time.time() - start) * 1000, 2)
            except Exception as e:
                status["sql_warehouse"]["error"] = str(e)

        status["active_source"] = self.get_active_source().value

        return status

    def get_performance_comparison(self) -> Dict[str, Any]:
        """Compare query performance between Lakebase and SQL Warehouse."""
        test_query = "SELECT COUNT(*) as cnt FROM system.lakeflow.jobs WHERE delete_time IS NULL"
        results = {}

        # Test Lakebase
        if self.lakebase_config.is_configured and self._lakebase_healthy:
            try:
                start = time.time()
                self._query_lakebase(test_query)
                results["lakebase_ms"] = round((time.time() - start) * 1000, 2)
            except Exception as e:
                results["lakebase_error"] = str(e)

        # Test SQL Warehouse
        if self.warehouse_config.is_configured:
            try:
                start = time.time()
                self._query_warehouse(test_query)
                results["sql_warehouse_ms"] = round((time.time() - start) * 1000, 2)
            except Exception as e:
                results["sql_warehouse_error"] = str(e)

        # Calculate speedup
        if "lakebase_ms" in results and "sql_warehouse_ms" in results:
            results["speedup_factor"] = round(results["sql_warehouse_ms"] / results["lakebase_ms"], 1)

        return results


# Singleton instance for app-wide use
_data_layer: Optional[DataAccessLayer] = None


def get_data_layer() -> DataAccessLayer:
    """Get or create the singleton data access layer."""
    global _data_layer
    if _data_layer is None:
        _data_layer = DataAccessLayer()
    return _data_layer


def reset_data_layer():
    """Reset the singleton data layer (for testing)."""
    global _data_layer
    _data_layer = None
