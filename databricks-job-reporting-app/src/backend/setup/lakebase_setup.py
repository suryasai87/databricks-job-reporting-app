#!/usr/bin/env python3
"""
Automated Lakebase setup for Jobs Monitor.
Run once during initial deployment or via DAB.

This script creates:
1. A Lakebase instance (PostgreSQL-compatible database)
2. Synced tables that continuously sync from system tables
3. Connection configuration for the app

Usage:
    python -m src.backend.setup.lakebase_setup [--instance-name NAME] [--capacity CU_1|CU_2|CU_4|CU_8]
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Synced tables configuration
SYNCED_TABLES_CONFIG = [
    # Core job tables - CONTINUOUS for real-time dashboard
    {
        "source": "system.lakeflow.jobs",
        "pk_columns": ["workspace_id", "job_id"],
        "scheduling": "CONTINUOUS",
        "description": "Job definitions - continuous sync for real-time updates"
    },
    {
        "source": "system.lakeflow.job_tasks",
        "pk_columns": ["workspace_id", "job_id", "task_key"],
        "scheduling": "CONTINUOUS",
        "description": "Task definitions within jobs"
    },
    {
        "source": "system.lakeflow.job_run_timeline",
        "pk_columns": ["workspace_id", "job_id", "run_id", "period_start_time"],
        "scheduling": "CONTINUOUS",
        "description": "Run timeline - most queried table, needs real-time"
    },
    {
        "source": "system.lakeflow.job_task_run_timeline",
        "pk_columns": ["workspace_id", "job_id", "run_id", "task_run_id"],
        "scheduling": "CONTINUOUS",
        "description": "Task-level run details"
    },
    # Billing tables - TRIGGERED (less frequent updates acceptable)
    {
        "source": "system.billing.usage",
        "pk_columns": ["workspace_id", "record_id"],
        "scheduling": "TRIGGERED",
        "description": "Billing data - hourly sync sufficient"
    },
    {
        "source": "system.billing.list_prices",
        "pk_columns": ["price_start_time", "sku_name", "cloud", "currency_code"],
        "scheduling": "TRIGGERED",
        "description": "Pricing data - daily sync sufficient"
    },
    # Compute tables
    {
        "source": "system.compute.clusters",
        "pk_columns": ["workspace_id", "cluster_id"],
        "scheduling": "CONTINUOUS",
        "description": "Cluster metadata for metrics correlation"
    },
]


def setup_lakebase_for_jobs_monitor(
    instance_name: str = "jobs-monitor-lakebase",
    capacity: str = "CU_1",
    catalog: str = "jobs_monitor",
    schema: str = "synced",
    enable_ha: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Create Lakebase instance and synced tables for Jobs Monitor.

    Args:
        instance_name: Name for the Lakebase instance
        capacity: Capacity unit (CU_1, CU_2, CU_4, CU_8)
        catalog: Unity Catalog name for synced tables
        schema: Schema name for synced tables
        enable_ha: Enable readable secondaries for HA
        dry_run: If True, only print what would be done

    Returns:
        Dictionary with instance info and created tables
    """
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.database import (
            DatabaseInstance,
            SyncedDatabaseTable,
            SyncedTableSpec,
            NewPipelineSpec,
        )
    except ImportError:
        logger.error("databricks-sdk not installed. Run: pip install databricks-sdk")
        return {"error": "databricks-sdk not installed"}

    if dry_run:
        print("=" * 60)
        print("DRY RUN - No changes will be made")
        print("=" * 60)
        print(f"Would create Lakebase instance: {instance_name}")
        print(f"Capacity: {capacity}")
        print(f"HA Enabled: {enable_ha}")
        print(f"\nWould create {len(SYNCED_TABLES_CONFIG)} synced tables:")
        for tc in SYNCED_TABLES_CONFIG:
            target = f"{catalog}.{schema}.{tc['source'].split('.')[-1]}"
            print(f"  - {tc['source']} -> {target} ({tc['scheduling']})")
        return {"dry_run": True}

    w = WorkspaceClient()

    # Step 1: Create Lakebase instance
    print("=" * 60)
    print(f"Creating Lakebase instance: {instance_name}")
    print("=" * 60)

    try:
        instance = w.database.create_database_instance_and_wait(
            DatabaseInstance(
                name=instance_name,
                capacity=capacity,
                enable_readable_secondaries=enable_ha,
            )
        )
        print(f"Instance created: {instance.name} (status: {instance.state})")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"Instance already exists, getting info...")
            instance = w.database.get_database_instance(name=instance_name)
        else:
            logger.error(f"Failed to create instance: {e}")
            return {"error": str(e)}

    # Step 2: Create synced tables
    print("\n" + "=" * 60)
    print("Creating synced tables")
    print("=" * 60)

    created_tables = []
    for table_config in SYNCED_TABLES_CONFIG:
        source_name = table_config["source"].split(".")[-1]
        target_name = f"{catalog}.{schema}.{source_name}"

        print(f"\nCreating: {target_name}")
        print(f"  Source: {table_config['source']}")
        print(f"  Sync mode: {table_config['scheduling']}")

        try:
            synced_table = w.database.create_synced_database_table(
                SyncedDatabaseTable(
                    name=target_name,
                    database_instance_name=instance_name,
                    logical_database_name="jobs_monitor_db",
                    spec=SyncedTableSpec(
                        source_table_full_name=table_config["source"],
                        primary_key_columns=table_config["pk_columns"],
                        scheduling_policy=table_config["scheduling"],
                        create_database_objects_if_missing=True,
                        new_pipeline_spec=NewPipelineSpec(
                            storage_catalog=catalog,
                            storage_schema=f"{schema}_pipelines"
                        )
                    ),
                )
            )
            created_tables.append({
                "name": target_name,
                "source": table_config["source"],
                "status": "created",
                "sync_mode": table_config["scheduling"]
            })
            print(f"  Status: Created")

        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  Status: Already exists")
                created_tables.append({
                    "name": target_name,
                    "source": table_config["source"],
                    "status": "exists",
                    "sync_mode": table_config["scheduling"]
                })
            else:
                print(f"  Status: Failed - {e}")
                created_tables.append({
                    "name": target_name,
                    "source": table_config["source"],
                    "status": "failed",
                    "error": str(e)
                })

    # Step 3: Get connection info
    instance_info = w.database.get_database_instance(name=instance_name)

    result = {
        "instance_name": instance_name,
        "capacity": capacity,
        "host": instance_info.read_write_dns,
        "read_replica_host": instance_info.read_only_dns if enable_ha else None,
        "port": 5432,
        "database": "jobs_monitor_db",
        "synced_tables": created_tables,
        "state": str(instance_info.state),
    }

    # Print summary
    print("\n" + "=" * 60)
    print("Lakebase Setup Complete!")
    print("=" * 60)
    print(f"Instance: {result['instance_name']}")
    print(f"State: {result['state']}")
    print(f"Host: {result['host']}")
    if result['read_replica_host']:
        print(f"Read Replica: {result['read_replica_host']}")
    print(f"Port: {result['port']}")
    print(f"Database: {result['database']}")
    print(f"\nSynced Tables: {len(created_tables)}")

    success_count = sum(1 for t in created_tables if t['status'] in ['created', 'exists'])
    failed_count = sum(1 for t in created_tables if t['status'] == 'failed')
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failed_count}")

    print("\n" + "=" * 60)
    print("Environment Variables to Set:")
    print("=" * 60)
    print(f"export LAKEBASE_HOST='{result['host']}'")
    if result['read_replica_host']:
        print(f"export LAKEBASE_READ_REPLICA_HOST='{result['read_replica_host']}'")
    print(f"export LAKEBASE_DATABASE='{result['database']}'")
    print("export LAKEBASE_ENABLED='true'")

    return result


def get_lakebase_connection_string(instance_name: str) -> Dict[str, str]:
    """Get connection details for Lakebase instance."""
    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        return {"error": "databricks-sdk not installed"}

    w = WorkspaceClient()
    instance = w.database.get_database_instance(name=instance_name)

    return {
        "host": instance.read_write_dns,
        "read_replica_host": instance.read_only_dns,
        "port": "5432",
        "database": "jobs_monitor_db",
        "ssl_mode": "require",
        "user": "token",
        # password should be set to DATABRICKS_TOKEN
    }


def check_sync_status(instance_name: str) -> List[Dict[str, Any]]:
    """Check status of all synced tables."""
    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        return [{"error": "databricks-sdk not installed"}]

    w = WorkspaceClient()
    results = []

    for tc in SYNCED_TABLES_CONFIG:
        source_name = tc["source"].split(".")[-1]
        table_name = f"jobs_monitor.synced.{source_name}"

        try:
            status = w.database.get_synced_database_table(name=table_name)
            sync_state = status.data_synchronization_status

            results.append({
                "table": table_name,
                "source": tc["source"],
                "state": sync_state.detailed_state if sync_state else "UNKNOWN",
                "last_sync": str(sync_state.last_sync_time) if sync_state and sync_state.last_sync_time else None,
            })
        except Exception as e:
            results.append({
                "table": table_name,
                "source": tc["source"],
                "state": "ERROR",
                "error": str(e),
            })

    return results


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Set up Lakebase for Databricks Jobs Monitor"
    )
    parser.add_argument(
        "--instance-name",
        default="jobs-monitor-lakebase",
        help="Name for the Lakebase instance"
    )
    parser.add_argument(
        "--capacity",
        choices=["CU_1", "CU_2", "CU_4", "CU_8"],
        default="CU_1",
        help="Capacity unit for the instance"
    )
    parser.add_argument(
        "--catalog",
        default="jobs_monitor",
        help="Unity Catalog name for synced tables"
    )
    parser.add_argument(
        "--schema",
        default="synced",
        help="Schema name for synced tables"
    )
    parser.add_argument(
        "--no-ha",
        action="store_true",
        help="Disable high availability (readable secondaries)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes"
    )
    parser.add_argument(
        "--check-status",
        action="store_true",
        help="Check sync status of existing tables"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.check_status:
        print("Checking sync status...")
        results = check_sync_status(args.instance_name)
        print("\n" + "=" * 60)
        print("Sync Status")
        print("=" * 60)
        for r in results:
            status_icon = "OK" if r.get("state") == "ONLINE" else "WARN" if r.get("state") == "SYNCING" else "ERR"
            print(f"[{status_icon}] {r['table']}: {r.get('state', 'UNKNOWN')}")
            if r.get("last_sync"):
                print(f"     Last sync: {r['last_sync']}")
            if r.get("error"):
                print(f"     Error: {r['error']}")
        return

    result = setup_lakebase_for_jobs_monitor(
        instance_name=args.instance_name,
        capacity=args.capacity,
        catalog=args.catalog,
        schema=args.schema,
        enable_ha=not args.no_ha,
        dry_run=args.dry_run,
    )

    if result.get("error"):
        print(f"\nError: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
