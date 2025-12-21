"""
Unity Catalog Lineage Service for Databricks Jobs Monitor.

Provides lineage tracking by querying Unity Catalog system tables:
- system.access.table_lineage: Table-to-table lineage relationships
- system.access.audit: Job table access patterns (reads/writes)

Features:
- Upstream and downstream lineage traversal
- Job dependency graph construction
- Failure impact analysis
- Plotly-compatible DAG visualizations
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)


class LineageDirection(Enum):
    """Direction for lineage traversal."""
    UPSTREAM = "upstream"      # Tables that feed into this table
    DOWNSTREAM = "downstream"  # Tables that depend on this table
    BOTH = "both"              # Both directions


@dataclass
class TableNode:
    """Represents a table in the lineage graph."""
    catalog: str
    schema: str
    table: str
    table_type: str = "TABLE"  # TABLE, VIEW, MATERIALIZED_VIEW
    description: Optional[str] = None
    owner: Optional[str] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        """Return fully qualified table name."""
        return f"{self.catalog}.{self.schema}.{self.table}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "catalog": self.catalog,
            "schema": self.schema,
            "table": self.table,
            "full_name": self.full_name,
            "table_type": self.table_type,
            "description": self.description,
            "owner": self.owner,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
        }


@dataclass
class JobNode:
    """Represents a job in the lineage graph."""
    job_id: str
    job_name: str
    workspace_id: Optional[str] = None
    creator: Optional[str] = None
    schedule: Optional[str] = None
    last_run_time: Optional[datetime] = None
    last_run_status: Optional[str] = None
    tables_read: List[str] = field(default_factory=list)
    tables_written: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "workspace_id": self.workspace_id,
            "creator": self.creator,
            "schedule": self.schedule,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "last_run_status": self.last_run_status,
            "tables_read": self.tables_read,
            "tables_written": self.tables_written,
        }


@dataclass
class LineageEdge:
    """Represents an edge (relationship) in the lineage graph."""
    source: str        # Source table or job ID
    target: str        # Target table or job ID
    source_type: str   # "table" or "job"
    target_type: str   # "table" or "job"
    relationship: str  # "reads", "writes", "transforms", "depends_on"
    column_mappings: Optional[List[Dict[str, str]]] = None  # Source->target column mappings
    last_access_time: Optional[datetime] = None
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source": self.source,
            "target": self.target,
            "source_type": self.source_type,
            "target_type": self.target_type,
            "relationship": self.relationship,
            "column_mappings": self.column_mappings,
            "last_access_time": self.last_access_time.isoformat() if self.last_access_time else None,
            "access_count": self.access_count,
        }


@dataclass
class JobLineageResult:
    """Result of job lineage analysis."""
    job: JobNode
    upstream_tables: List[TableNode] = field(default_factory=list)
    downstream_tables: List[TableNode] = field(default_factory=list)
    upstream_jobs: List[JobNode] = field(default_factory=list)
    downstream_jobs: List[JobNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "job": self.job.to_dict(),
            "upstream_tables": [t.to_dict() for t in self.upstream_tables],
            "downstream_tables": [t.to_dict() for t in self.downstream_tables],
            "upstream_jobs": [j.to_dict() for j in self.upstream_jobs],
            "downstream_jobs": [j.to_dict() for j in self.downstream_jobs],
            "edges": [e.to_dict() for e in self.edges],
        }


class LineageService:
    """
    Service for querying Unity Catalog lineage information.

    Uses system tables to build lineage graphs:
    - system.access.table_lineage: Direct table-to-table lineage
    - system.access.audit: Job access patterns to tables
    """

    # Cache TTL for job info and table access data
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, data_layer=None):
        """
        Initialize LineageService.

        Args:
            data_layer: Optional data layer instance. If None, uses singleton.
        """
        self._data_layer = data_layer
        self._job_cache: Dict[str, Tuple[JobNode, datetime]] = {}
        self._table_access_cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}

    @property
    def data_layer(self):
        """Get data layer instance (lazy loading)."""
        if self._data_layer is None:
            from data.data_layer import get_data_layer
            self._data_layer = get_data_layer()
        return self._data_layer

    def _is_cache_valid(self, cache_time: datetime) -> bool:
        """Check if cached data is still valid."""
        return (datetime.now() - cache_time).total_seconds() < self.CACHE_TTL_SECONDS

    def _parse_table_name(self, full_name: str) -> Tuple[str, str, str]:
        """Parse fully qualified table name into components."""
        parts = full_name.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid table name format: {full_name}. Expected catalog.schema.table")
        return parts[0], parts[1], parts[2]

    def get_table_lineage(
        self,
        table_full_name: str,
        direction: LineageDirection = LineageDirection.BOTH,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Get lineage for a specific table.

        Args:
            table_full_name: Fully qualified table name (catalog.schema.table)
            direction: Direction to traverse (upstream, downstream, or both)
            max_depth: Maximum depth to traverse in the lineage graph

        Returns:
            Dictionary containing tables, edges, and metadata
        """
        catalog, schema, table = self._parse_table_name(table_full_name)

        tables: Dict[str, TableNode] = {}
        edges: List[LineageEdge] = []
        visited: Set[str] = set()

        # Add the root table
        root_table = TableNode(catalog=catalog, schema=schema, table=table)
        tables[table_full_name] = root_table

        if direction in (LineageDirection.UPSTREAM, LineageDirection.BOTH):
            self._traverse_lineage(
                table_full_name,
                tables,
                edges,
                visited,
                max_depth,
                is_upstream=True
            )

        if direction in (LineageDirection.DOWNSTREAM, LineageDirection.BOTH):
            visited.clear()  # Reset for downstream traversal
            self._traverse_lineage(
                table_full_name,
                tables,
                edges,
                visited,
                max_depth,
                is_upstream=False
            )

        return {
            "root_table": table_full_name,
            "direction": direction.value,
            "max_depth": max_depth,
            "tables": [t.to_dict() for t in tables.values()],
            "edges": [e.to_dict() for e in edges],
            "table_count": len(tables),
            "edge_count": len(edges),
        }

    def _traverse_lineage(
        self,
        table_full_name: str,
        tables: Dict[str, TableNode],
        edges: List[LineageEdge],
        visited: Set[str],
        remaining_depth: int,
        is_upstream: bool
    ):
        """
        Recursively traverse lineage graph.

        Args:
            table_full_name: Current table to traverse from
            tables: Dictionary to accumulate discovered tables
            edges: List to accumulate discovered edges
            visited: Set of already visited tables
            remaining_depth: Remaining depth to traverse
            is_upstream: True for upstream, False for downstream
        """
        if remaining_depth <= 0 or table_full_name in visited:
            return

        visited.add(table_full_name)

        try:
            # Query lineage from system table
            if is_upstream:
                # Find tables that feed into this table
                sql = """
                SELECT DISTINCT
                    source_table_catalog,
                    source_table_schema,
                    source_table_name,
                    target_table_catalog,
                    target_table_schema,
                    target_table_name,
                    source_column_name,
                    target_column_name,
                    event_time
                FROM system.access.table_lineage
                WHERE target_table_catalog = :catalog
                  AND target_table_schema = :schema
                  AND target_table_name = :table
                  AND event_time > :start_time
                ORDER BY event_time DESC
                LIMIT 100
                """
            else:
                # Find tables that depend on this table
                sql = """
                SELECT DISTINCT
                    source_table_catalog,
                    source_table_schema,
                    source_table_name,
                    target_table_catalog,
                    target_table_schema,
                    target_table_name,
                    source_column_name,
                    target_column_name,
                    event_time
                FROM system.access.table_lineage
                WHERE source_table_catalog = :catalog
                  AND source_table_schema = :schema
                  AND source_table_name = :table
                  AND event_time > :start_time
                ORDER BY event_time DESC
                LIMIT 100
                """

            catalog, schema, table = self._parse_table_name(table_full_name)
            start_time = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            results = self.data_layer.query(
                sql,
                params={
                    "catalog": catalog,
                    "schema": schema,
                    "table": table,
                    "start_time": start_time,
                }
            )

            # Process results and build graph
            column_mappings_by_table: Dict[str, List[Dict[str, str]]] = {}

            for row in results:
                if is_upstream:
                    related_catalog = row["source_table_catalog"]
                    related_schema = row["source_table_schema"]
                    related_table = row["source_table_name"]
                else:
                    related_catalog = row["target_table_catalog"]
                    related_schema = row["target_table_schema"]
                    related_table = row["target_table_name"]

                related_full_name = f"{related_catalog}.{related_schema}.{related_table}"

                # Skip self-references
                if related_full_name == table_full_name:
                    continue

                # Add table if not already present
                if related_full_name not in tables:
                    tables[related_full_name] = TableNode(
                        catalog=related_catalog,
                        schema=related_schema,
                        table=related_table
                    )

                # Track column mappings
                if related_full_name not in column_mappings_by_table:
                    column_mappings_by_table[related_full_name] = []

                if row.get("source_column_name") and row.get("target_column_name"):
                    column_mappings_by_table[related_full_name].append({
                        "source_column": row["source_column_name"],
                        "target_column": row["target_column_name"],
                    })

            # Create edges
            for related_full_name, column_mappings in column_mappings_by_table.items():
                if is_upstream:
                    edge = LineageEdge(
                        source=related_full_name,
                        target=table_full_name,
                        source_type="table",
                        target_type="table",
                        relationship="transforms",
                        column_mappings=column_mappings if column_mappings else None,
                    )
                else:
                    edge = LineageEdge(
                        source=table_full_name,
                        target=related_full_name,
                        source_type="table",
                        target_type="table",
                        relationship="transforms",
                        column_mappings=column_mappings if column_mappings else None,
                    )
                edges.append(edge)

                # Recursively traverse
                self._traverse_lineage(
                    related_full_name,
                    tables,
                    edges,
                    visited,
                    remaining_depth - 1,
                    is_upstream
                )

        except Exception as e:
            logger.error(f"Error traversing lineage for {table_full_name}: {e}")

    def _get_job_info(self, job_id: str) -> Optional[JobNode]:
        """Get job information with caching."""
        # Check cache
        if job_id in self._job_cache:
            cached_job, cache_time = self._job_cache[job_id]
            if self._is_cache_valid(cache_time):
                return cached_job

        try:
            sql = """
            SELECT
                job_id,
                name,
                workspace_id,
                creator_user_name,
                settings
            FROM system.lakeflow.jobs
            WHERE job_id = :job_id
              AND delete_time IS NULL
            """

            results = self.data_layer.query(sql, params={"job_id": job_id})

            if results:
                row = results[0]
                settings = row.get("settings", {}) or {}
                schedule = None
                if isinstance(settings, dict) and "schedule" in settings:
                    schedule = settings["schedule"].get("quartz_cron_expression")

                job_node = JobNode(
                    job_id=str(row["job_id"]),
                    job_name=row.get("name", f"Job {job_id}"),
                    workspace_id=str(row.get("workspace_id", "")),
                    creator=row.get("creator_user_name"),
                    schedule=schedule,
                )

                # Cache the result
                self._job_cache[job_id] = (job_node, datetime.now())
                return job_node

        except Exception as e:
            logger.error(f"Error getting job info for {job_id}: {e}")

        return None

    def _get_job_table_access(self, job_id: str) -> Dict[str, List[str]]:
        """
        Get tables read and written by a job from audit logs.

        Returns:
            Dictionary with 'reads' and 'writes' lists of table names
        """
        cache_key = f"access_{job_id}"

        # Check cache
        if cache_key in self._table_access_cache:
            cached_data, cache_time = self._table_access_cache[cache_key]
            if self._is_cache_valid(cache_time):
                return cached_data

        result = {"reads": [], "writes": []}

        try:
            # Query audit logs for table access by job
            sql = """
            SELECT DISTINCT
                request_params.full_name_arg as table_name,
                action_name
            FROM system.access.audit
            WHERE workspace_id = :workspace_id
              AND action_name IN ('readTable', 'writeTable', 'appendData', 'overwriteData')
              AND request_params.job_id = :job_id
              AND event_time > :start_time
            """

            start_time = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            # Get workspace ID (from environment or default)
            import os
            workspace_id = os.environ.get("DATABRICKS_WORKSPACE_ID", "")

            results = self.data_layer.query(
                sql,
                params={
                    "workspace_id": workspace_id,
                    "job_id": job_id,
                    "start_time": start_time,
                }
            )

            for row in results:
                table_name = row.get("table_name")
                action = row.get("action_name", "")

                if not table_name:
                    continue

                if action in ("readTable",):
                    if table_name not in result["reads"]:
                        result["reads"].append(table_name)
                elif action in ("writeTable", "appendData", "overwriteData"):
                    if table_name not in result["writes"]:
                        result["writes"].append(table_name)

            # Cache the result
            self._table_access_cache[cache_key] = (result, datetime.now())

        except Exception as e:
            logger.error(f"Error getting table access for job {job_id}: {e}")

        return result

    def get_job_lineage(
        self,
        job_id: str,
        include_indirect: bool = True
    ) -> Optional[JobLineageResult]:
        """
        Get complete lineage for a job including tables and dependent jobs.

        Args:
            job_id: The job ID to analyze
            include_indirect: Include indirect dependencies (jobs that write to tables this job reads)

        Returns:
            JobLineageResult with complete lineage information
        """
        # Get job info
        job = self._get_job_info(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found")
            return None

        # Get table access
        table_access = self._get_job_table_access(job_id)
        job.tables_read = table_access["reads"]
        job.tables_written = table_access["writes"]

        result = JobLineageResult(job=job)
        edges: List[LineageEdge] = []

        # Create table nodes for directly accessed tables
        for table_name in job.tables_read:
            try:
                catalog, schema, table = self._parse_table_name(table_name)
                table_node = TableNode(catalog=catalog, schema=schema, table=table)
                result.upstream_tables.append(table_node)

                edges.append(LineageEdge(
                    source=table_name,
                    target=job_id,
                    source_type="table",
                    target_type="job",
                    relationship="reads",
                ))
            except ValueError:
                logger.warning(f"Invalid table name format: {table_name}")

        for table_name in job.tables_written:
            try:
                catalog, schema, table = self._parse_table_name(table_name)
                table_node = TableNode(catalog=catalog, schema=schema, table=table)
                result.downstream_tables.append(table_node)

                edges.append(LineageEdge(
                    source=job_id,
                    target=table_name,
                    source_type="job",
                    target_type="table",
                    relationship="writes",
                ))
            except ValueError:
                logger.warning(f"Invalid table name format: {table_name}")

        if include_indirect:
            # Find jobs that write to tables this job reads (upstream jobs)
            for table_name in job.tables_read:
                upstream_jobs = self._find_jobs_writing_to_table(table_name, exclude_job_id=job_id)
                for upstream_job in upstream_jobs:
                    if upstream_job not in [j.job_id for j in result.upstream_jobs]:
                        upstream_job_node = self._get_job_info(upstream_job)
                        if upstream_job_node:
                            result.upstream_jobs.append(upstream_job_node)
                            edges.append(LineageEdge(
                                source=upstream_job,
                                target=job_id,
                                source_type="job",
                                target_type="job",
                                relationship="depends_on",
                            ))

            # Find jobs that read from tables this job writes (downstream jobs)
            for table_name in job.tables_written:
                downstream_jobs = self._find_jobs_reading_from_table(table_name, exclude_job_id=job_id)
                for downstream_job in downstream_jobs:
                    if downstream_job not in [j.job_id for j in result.downstream_jobs]:
                        downstream_job_node = self._get_job_info(downstream_job)
                        if downstream_job_node:
                            result.downstream_jobs.append(downstream_job_node)
                            edges.append(LineageEdge(
                                source=job_id,
                                target=downstream_job,
                                source_type="job",
                                target_type="job",
                                relationship="depends_on",
                            ))

        result.edges = edges
        return result

    def _find_jobs_writing_to_table(self, table_name: str, exclude_job_id: str = None) -> List[str]:
        """Find jobs that write to a specific table."""
        try:
            sql = """
            SELECT DISTINCT request_params.job_id as job_id
            FROM system.access.audit
            WHERE action_name IN ('writeTable', 'appendData', 'overwriteData')
              AND request_params.full_name_arg = :table_name
              AND event_time > :start_time
            """

            start_time = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            results = self.data_layer.query(
                sql,
                params={"table_name": table_name, "start_time": start_time}
            )

            job_ids = []
            for row in results:
                job_id = str(row.get("job_id", ""))
                if job_id and job_id != exclude_job_id:
                    job_ids.append(job_id)

            return job_ids

        except Exception as e:
            logger.error(f"Error finding jobs writing to {table_name}: {e}")
            return []

    def _find_jobs_reading_from_table(self, table_name: str, exclude_job_id: str = None) -> List[str]:
        """Find jobs that read from a specific table."""
        try:
            sql = """
            SELECT DISTINCT request_params.job_id as job_id
            FROM system.access.audit
            WHERE action_name = 'readTable'
              AND request_params.full_name_arg = :table_name
              AND event_time > :start_time
            """

            start_time = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            results = self.data_layer.query(
                sql,
                params={"table_name": table_name, "start_time": start_time}
            )

            job_ids = []
            for row in results:
                job_id = str(row.get("job_id", ""))
                if job_id and job_id != exclude_job_id:
                    job_ids.append(job_id)

            return job_ids

        except Exception as e:
            logger.error(f"Error finding jobs reading from {table_name}: {e}")
            return []

    def build_job_dependency_graph(self, job_ids: List[str]) -> Dict[str, Any]:
        """
        Build a dependency graph for a set of jobs.

        Args:
            job_ids: List of job IDs to include in the graph

        Returns:
            Dictionary with nodes (jobs), edges (dependencies), and metadata
        """
        nodes: Dict[str, JobNode] = {}
        edges: List[LineageEdge] = []
        table_producers: Dict[str, str] = {}  # table_name -> job_id that writes it
        table_consumers: Dict[str, List[str]] = {}  # table_name -> job_ids that read it

        # First pass: gather all job info and table access
        for job_id in job_ids:
            job = self._get_job_info(job_id)
            if job:
                table_access = self._get_job_table_access(job_id)
                job.tables_read = table_access["reads"]
                job.tables_written = table_access["writes"]
                nodes[job_id] = job

                # Track table producers and consumers
                for table in job.tables_written:
                    table_producers[table] = job_id

                for table in job.tables_read:
                    if table not in table_consumers:
                        table_consumers[table] = []
                    table_consumers[table].append(job_id)

        # Second pass: create dependency edges
        for table, consumer_jobs in table_consumers.items():
            if table in table_producers:
                producer_job = table_producers[table]
                for consumer_job in consumer_jobs:
                    if producer_job != consumer_job:
                        edges.append(LineageEdge(
                            source=producer_job,
                            target=consumer_job,
                            source_type="job",
                            target_type="job",
                            relationship="depends_on",
                        ))

        # Calculate graph metrics
        in_degree: Dict[str, int] = {job_id: 0 for job_id in nodes}
        out_degree: Dict[str, int] = {job_id: 0 for job_id in nodes}

        for edge in edges:
            if edge.source in out_degree:
                out_degree[edge.source] += 1
            if edge.target in in_degree:
                in_degree[edge.target] += 1

        # Find root jobs (no dependencies) and leaf jobs (no dependents)
        root_jobs = [job_id for job_id, degree in in_degree.items() if degree == 0]
        leaf_jobs = [job_id for job_id, degree in out_degree.items() if degree == 0]

        return {
            "nodes": [node.to_dict() for node in nodes.values()],
            "edges": [edge.to_dict() for edge in edges],
            "metrics": {
                "total_jobs": len(nodes),
                "total_edges": len(edges),
                "root_jobs": root_jobs,
                "leaf_jobs": leaf_jobs,
                "shared_tables": list(set(table_producers.keys()) & set(table_consumers.keys())),
            },
        }

    def analyze_failure_impact(self, failed_job_id: str) -> Dict[str, Any]:
        """
        Analyze the impact of a job failure on downstream jobs and tables.

        Args:
            failed_job_id: The ID of the failed job

        Returns:
            Dictionary with impact analysis including affected jobs and tables
        """
        lineage = self.get_job_lineage(failed_job_id, include_indirect=True)

        if not lineage:
            return {
                "failed_job_id": failed_job_id,
                "error": "Job not found",
                "impacted_tables": [],
                "impacted_jobs": [],
                "impact_severity": "unknown",
            }

        impacted_tables = [t.full_name for t in lineage.downstream_tables]
        impacted_jobs = [j.to_dict() for j in lineage.downstream_jobs]

        # Calculate cascade depth
        cascade_depth = 0
        visited_jobs: Set[str] = {failed_job_id}
        current_level = [j.job_id for j in lineage.downstream_jobs]

        while current_level and cascade_depth < 10:
            cascade_depth += 1
            next_level = []

            for job_id in current_level:
                if job_id in visited_jobs:
                    continue
                visited_jobs.add(job_id)

                job_lineage = self.get_job_lineage(job_id, include_indirect=True)
                if job_lineage:
                    for downstream_job in job_lineage.downstream_jobs:
                        if downstream_job.job_id not in visited_jobs:
                            next_level.append(downstream_job.job_id)
                            if downstream_job.to_dict() not in impacted_jobs:
                                impacted_jobs.append(downstream_job.to_dict())

                    for table in job_lineage.downstream_tables:
                        if table.full_name not in impacted_tables:
                            impacted_tables.append(table.full_name)

            current_level = next_level

        # Determine severity
        if len(impacted_jobs) == 0:
            severity = "low"
        elif len(impacted_jobs) <= 3:
            severity = "medium"
        elif len(impacted_jobs) <= 10:
            severity = "high"
        else:
            severity = "critical"

        return {
            "failed_job": lineage.job.to_dict(),
            "impacted_tables": impacted_tables,
            "impacted_jobs": impacted_jobs,
            "cascade_depth": cascade_depth,
            "impact_severity": severity,
            "total_impacted_jobs": len(impacted_jobs),
            "total_impacted_tables": len(impacted_tables),
            "recommendations": self._generate_remediation_recommendations(
                lineage.job, impacted_tables, impacted_jobs
            ),
        }

    def _generate_remediation_recommendations(
        self,
        failed_job: JobNode,
        impacted_tables: List[str],
        impacted_jobs: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate remediation recommendations based on impact analysis."""
        recommendations = []

        if len(impacted_jobs) > 5:
            recommendations.append(
                f"High impact failure: {len(impacted_jobs)} downstream jobs affected. "
                "Consider prioritizing this job's recovery."
            )

        if len(impacted_tables) > 0:
            recommendations.append(
                f"Tables at risk of stale data: {', '.join(impacted_tables[:5])}"
                + (f" and {len(impacted_tables) - 5} more" if len(impacted_tables) > 5 else "")
            )

        recommendations.append(
            "Check job logs and cluster status for root cause analysis."
        )

        if failed_job.schedule:
            recommendations.append(
                f"Scheduled job ({failed_job.schedule}): Monitor next scheduled run or trigger manual rerun."
            )

        return recommendations

    def clear_cache(self):
        """Clear all cached data."""
        self._job_cache.clear()
        self._table_access_cache.clear()
        logger.info("Lineage service cache cleared")


class LineageGraphVisualizer:
    """
    Creates Plotly-compatible DAG visualizations for lineage data.

    Generates node positions, colors, and edge configurations suitable
    for rendering with Plotly's graph objects or Dash Cytoscape.
    """

    # Color schemes for different node types
    COLORS = {
        "job": {
            "default": "#3b82f6",    # Blue
            "failed": "#ef4444",      # Red
            "running": "#f59e0b",     # Amber
            "success": "#22c55e",     # Green
        },
        "table": {
            "default": "#8b5cf6",     # Purple
            "source": "#06b6d4",      # Cyan
            "target": "#ec4899",      # Pink
        },
        "edge": {
            "reads": "#94a3b8",       # Slate
            "writes": "#f97316",      # Orange
            "transforms": "#a855f7",  # Purple
            "depends_on": "#3b82f6",  # Blue
        },
    }

    def __init__(self):
        """Initialize the visualizer."""
        pass

    def create_dag_visualization(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        layout: str = "dagre"
    ) -> Dict[str, Any]:
        """
        Create a Plotly-compatible DAG visualization.

        Args:
            nodes: List of node dictionaries with id, label, type
            edges: List of edge dictionaries with source, target, relationship
            layout: Layout algorithm (dagre, hierarchical, force)

        Returns:
            Dictionary with Plotly figure data and Cytoscape elements
        """
        # Calculate node positions based on layout
        positions = self._calculate_positions(nodes, edges, layout)

        # Build Cytoscape elements
        cytoscape_elements = []

        for node in nodes:
            node_id = node.get("job_id") or node.get("full_name") or node.get("id")
            node_type = node.get("type", "job" if "job_id" in node else "table")
            node_label = node.get("job_name") or node.get("table") or node.get("label", node_id)
            status = node.get("last_run_status", "default")

            color = self.COLORS.get(node_type, {}).get(status, self.COLORS[node_type]["default"])

            cytoscape_elements.append({
                "data": {
                    "id": str(node_id),
                    "label": node_label,
                    "type": node_type,
                    "color": color,
                    **{k: v for k, v in node.items() if k not in ("id", "label", "type")},
                },
                "position": positions.get(str(node_id), {"x": 0, "y": 0}),
            })

        for edge in edges:
            relationship = edge.get("relationship", "depends_on")
            edge_color = self.COLORS["edge"].get(relationship, self.COLORS["edge"]["depends_on"])

            cytoscape_elements.append({
                "data": {
                    "id": f"{edge['source']}-{edge['target']}",
                    "source": str(edge["source"]),
                    "target": str(edge["target"]),
                    "relationship": relationship,
                    "color": edge_color,
                },
            })

        # Build Plotly traces
        plotly_data = self._create_plotly_traces(nodes, edges, positions)

        return {
            "cytoscape_elements": cytoscape_elements,
            "plotly_data": plotly_data,
            "layout": layout,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def _calculate_positions(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        layout: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate node positions based on the layout algorithm.

        For simple cases, uses a hierarchical layout based on topological sort.
        """
        positions = {}

        # Build adjacency list
        adjacency: Dict[str, List[str]] = {}
        reverse_adjacency: Dict[str, List[str]] = {}

        for node in nodes:
            node_id = str(node.get("job_id") or node.get("full_name") or node.get("id"))
            adjacency[node_id] = []
            reverse_adjacency[node_id] = []

        for edge in edges:
            source = str(edge["source"])
            target = str(edge["target"])
            if source in adjacency:
                adjacency[source].append(target)
            if target in reverse_adjacency:
                reverse_adjacency[target].append(source)

        # Calculate levels using BFS from root nodes
        in_degree = {node_id: len(deps) for node_id, deps in reverse_adjacency.items()}
        root_nodes = [node_id for node_id, degree in in_degree.items() if degree == 0]

        levels: Dict[str, int] = {}
        queue = [(node_id, 0) for node_id in root_nodes]

        while queue:
            node_id, level = queue.pop(0)
            if node_id in levels:
                levels[node_id] = max(levels[node_id], level)
            else:
                levels[node_id] = level

            for child in adjacency.get(node_id, []):
                queue.append((child, level + 1))

        # Assign default level for unvisited nodes
        for node in nodes:
            node_id = str(node.get("job_id") or node.get("full_name") or node.get("id"))
            if node_id not in levels:
                levels[node_id] = 0

        # Group nodes by level
        level_groups: Dict[int, List[str]] = {}
        for node_id, level in levels.items():
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(node_id)

        # Calculate positions
        x_spacing = 200
        y_spacing = 100

        for level, node_ids in level_groups.items():
            for i, node_id in enumerate(node_ids):
                x = level * x_spacing
                y = (i - len(node_ids) / 2) * y_spacing
                positions[node_id] = {"x": x, "y": y}

        return positions

    def _create_plotly_traces(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        positions: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        """Create Plotly trace data for the graph."""
        # Edge trace
        edge_x = []
        edge_y = []

        for edge in edges:
            source = str(edge["source"])
            target = str(edge["target"])

            if source in positions and target in positions:
                x0, y0 = positions[source]["x"], positions[source]["y"]
                x1, y1 = positions[target]["x"], positions[target]["y"]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

        edge_trace = {
            "x": edge_x,
            "y": edge_y,
            "mode": "lines",
            "line": {"width": 1, "color": "#888"},
            "hoverinfo": "none",
            "type": "scatter",
        }

        # Node trace
        node_x = []
        node_y = []
        node_text = []
        node_colors = []
        node_sizes = []

        for node in nodes:
            node_id = str(node.get("job_id") or node.get("full_name") or node.get("id"))
            node_type = "job" if "job_id" in node else "table"
            node_label = node.get("job_name") or node.get("table") or node_id

            if node_id in positions:
                node_x.append(positions[node_id]["x"])
                node_y.append(positions[node_id]["y"])
                node_text.append(node_label)
                node_colors.append(self.COLORS[node_type]["default"])
                node_sizes.append(20 if node_type == "job" else 15)

        node_trace = {
            "x": node_x,
            "y": node_y,
            "mode": "markers+text",
            "marker": {
                "size": node_sizes,
                "color": node_colors,
                "line": {"width": 2, "color": "white"},
            },
            "text": node_text,
            "textposition": "top center",
            "hoverinfo": "text",
            "type": "scatter",
        }

        return {
            "data": [edge_trace, node_trace],
            "layout": {
                "showlegend": False,
                "hovermode": "closest",
                "margin": {"b": 20, "l": 20, "r": 20, "t": 40},
                "xaxis": {"showgrid": False, "zeroline": False, "showticklabels": False},
                "yaxis": {"showgrid": False, "zeroline": False, "showticklabels": False},
            },
        }

    def create_job_lineage_visualization(
        self,
        lineage_result: JobLineageResult,
        highlight_failed: bool = False
    ) -> Dict[str, Any]:
        """
        Create a visualization specifically for job lineage results.

        Args:
            lineage_result: JobLineageResult from LineageService
            highlight_failed: Whether to highlight failed jobs

        Returns:
            Plotly-compatible visualization data
        """
        nodes = []
        edges = []

        # Add central job
        job_dict = lineage_result.job.to_dict()
        job_dict["type"] = "job"
        nodes.append(job_dict)

        # Add upstream tables
        for table in lineage_result.upstream_tables:
            table_dict = table.to_dict()
            table_dict["type"] = "table"
            nodes.append(table_dict)

        # Add downstream tables
        for table in lineage_result.downstream_tables:
            table_dict = table.to_dict()
            table_dict["type"] = "table"
            nodes.append(table_dict)

        # Add upstream jobs
        for job in lineage_result.upstream_jobs:
            job_dict = job.to_dict()
            job_dict["type"] = "job"
            nodes.append(job_dict)

        # Add downstream jobs
        for job in lineage_result.downstream_jobs:
            job_dict = job.to_dict()
            job_dict["type"] = "job"
            nodes.append(job_dict)

        # Add edges
        edges = [e.to_dict() for e in lineage_result.edges]

        return self.create_dag_visualization(nodes, edges)

    def create_failure_impact_visualization(
        self,
        impact_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a visualization for failure impact analysis.

        Args:
            impact_analysis: Result from LineageService.analyze_failure_impact()

        Returns:
            Plotly-compatible visualization with severity coloring
        """
        nodes = []
        edges = []

        # Add failed job (highlighted)
        failed_job = impact_analysis.get("failed_job", {})
        failed_job["type"] = "job"
        failed_job["last_run_status"] = "failed"
        nodes.append(failed_job)

        # Add impacted jobs
        for job in impact_analysis.get("impacted_jobs", []):
            job["type"] = "job"
            job["last_run_status"] = "default"
            nodes.append(job)

        # Add impacted tables
        for table_name in impact_analysis.get("impacted_tables", []):
            parts = table_name.split(".")
            if len(parts) == 3:
                nodes.append({
                    "type": "table",
                    "full_name": table_name,
                    "catalog": parts[0],
                    "schema": parts[1],
                    "table": parts[2],
                })

        # Create edges from failed job to impacted jobs
        failed_job_id = failed_job.get("job_id")
        for job in impact_analysis.get("impacted_jobs", []):
            edges.append({
                "source": failed_job_id,
                "target": job.get("job_id"),
                "relationship": "impacts",
            })

        return self.create_dag_visualization(nodes, edges)


# Singleton instance
_lineage_service: Optional[LineageService] = None


def get_lineage_service() -> LineageService:
    """Get or create the singleton LineageService instance."""
    global _lineage_service
    if _lineage_service is None:
        _lineage_service = LineageService()
    return _lineage_service
