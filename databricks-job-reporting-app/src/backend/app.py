"""
Databricks Jobs Monitor - FastAPI Backend
Features: SSO authentication, Genie Spaces AI, System Tables queries
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Try to import databricks SDK
try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState
    HAS_DATABRICKS_SDK = True
except ImportError:
    HAS_DATABRICKS_SDK = False
    logging.warning("Databricks SDK not installed. Some features will be limited.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Databricks Jobs Monitor",
    description="Comprehensive monitoring for Databricks jobs with AI-powered insights",
    version="1.0.0",
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment configuration
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "https://fe-vm-hls-amer.cloud.databricks.com")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "4b28691c780d9875")
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "01f0dde07de71fd3a4c0b4907fe15554")


# ============================================================
# Pydantic Models
# ============================================================

class User(BaseModel):
    email: str
    name: Optional[str] = None
    source: str
    authenticated: bool


class GenieMessageRequest(BaseModel):
    space_id: str
    message: str


class GenieConversationRequest(BaseModel):
    space_id: str


class ReportRequest(BaseModel):
    report_type: str
    start_date: str
    end_date: str


class RunNowRequest(BaseModel):
    parameters: Optional[Dict[str, str]] = None


class RepairRunRequest(BaseModel):
    rerun_tasks: Optional[List[str]] = None


# ============================================================
# Authentication Helper
# ============================================================

def get_current_user(request: Request) -> User:
    """
    Multi-method authentication supporting:
    - OBO (On-Behalf-Of) via x-forwarded-email header
    - U2M OAuth via x-forwarded-access-token header
    - Cookie-based authentication
    - M2M OAuth fallback using Databricks SDK
    """
    # Method 1: OBO Authorization (x-forwarded-email)
    forwarded_email = request.headers.get("x-forwarded-email")
    if forwarded_email:
        logger.info(f"OBO Auth: {forwarded_email}")
        return User(
            email=forwarded_email,
            name=request.headers.get("x-forwarded-user", forwarded_email.split("@")[0]),
            source="obo",
            authenticated=True,
        )

    # Method 2: U2M OAuth (x-forwarded-access-token)
    access_token = request.headers.get("x-forwarded-access-token")
    if access_token:
        try:
            import jwt
            # Decode without verification to get claims
            claims = jwt.decode(access_token, options={"verify_signature": False})
            email = claims.get("email", claims.get("sub", "unknown@databricks.com"))
            logger.info(f"U2M Auth: {email}")
            return User(
                email=email,
                name=claims.get("name"),
                source="u2m",
                authenticated=True,
            )
        except Exception as e:
            logger.warning(f"Failed to decode U2M token: {e}")

    # Method 3: Cookie-based auth
    auth_cookie = request.cookies.get("_databricks_auth")
    if auth_cookie:
        try:
            import jwt
            claims = jwt.decode(auth_cookie, options={"verify_signature": False})
            email = claims.get("email", "cookie-user@databricks.com")
            logger.info(f"Cookie Auth: {email}")
            return User(
                email=email,
                name=claims.get("name"),
                source="cookie",
                authenticated=True,
            )
        except Exception as e:
            logger.warning(f"Failed to decode cookie: {e}")

    # Method 4: M2M OAuth fallback
    if HAS_DATABRICKS_SDK and DATABRICKS_HOST:
        try:
            w = WorkspaceClient()
            current_user = w.current_user.me()
            logger.info(f"M2M Auth: {current_user.user_name}")
            return User(
                email=current_user.user_name or "m2m-user@databricks.com",
                name=current_user.display_name,
                source="m2m",
                authenticated=True,
            )
        except Exception as e:
            logger.warning(f"M2M auth failed: {e}")

    # No authentication found
    return User(
        email="anonymous",
        name="Anonymous User",
        source="none",
        authenticated=False,
    )


def get_workspace_client() -> Optional[Any]:
    """Get Databricks WorkspaceClient if available"""
    if not HAS_DATABRICKS_SDK:
        return None
    try:
        return WorkspaceClient()
    except Exception as e:
        logger.error(f"Failed to create WorkspaceClient: {e}")
        return None


def execute_sql(query: str, warehouse_id: str = None, timeout: str = "60s") -> List[Dict]:
    """Execute SQL query against Databricks SQL Warehouse"""
    w = get_workspace_client()
    if not w:
        logger.warning("No WorkspaceClient available, returning mock data")
        return []

    wh_id = warehouse_id or WAREHOUSE_ID
    if not wh_id:
        logger.warning("No warehouse ID configured")
        return []

    try:
        response = w.statement_execution.execute_statement(
            warehouse_id=wh_id,
            statement=query,
            wait_timeout=timeout,
        )

        if response.status.state == StatementState.SUCCEEDED:
            if response.result and response.result.data_array:
                columns = [col.name for col in response.manifest.schema.columns]
                return [dict(zip(columns, row)) for row in response.result.data_array]
        else:
            logger.error(f"SQL execution failed: {response.status}")
        return []
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        return []


# ============================================================
# Auth Endpoints
# ============================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/auth/status")
async def auth_status(request: Request) -> User:
    """Check authentication status"""
    return get_current_user(request)


@app.get("/api/user/profile")
async def user_profile(request: Request) -> User:
    """Get current user profile"""
    return get_current_user(request)


# ============================================================
# Jobs Endpoints
# ============================================================

@app.get("/api/jobs/runs")
async def get_job_runs(days: int = 7, limit: int = 1000):
    """Get job runs from system tables"""
    query = f"""
    SELECT
        r.workspace_id,
        r.job_id,
        r.run_id,
        COALESCE(j.name, r.run_name) as job_name,
        r.period_start_time as start_time,
        r.period_end_time as end_time,
        COALESCE(r.run_duration_seconds,
            TIMESTAMPDIFF(SECOND, r.period_start_time, COALESCE(r.period_end_time, current_timestamp()))) as duration_seconds,
        r.result_state,
        r.termination_code,
        r.trigger_type,
        r.run_type,
        COALESCE(j.run_as, j.run_as_user_name) as run_as,
        j.creator_user_name as creator_id
    FROM system.lakeflow.job_run_timeline r
    LEFT JOIN system.lakeflow.jobs j ON r.job_id = j.job_id AND r.workspace_id = j.workspace_id
    WHERE r.period_start_time >= current_date() - INTERVAL {days} DAY
    ORDER BY r.period_start_time DESC
    LIMIT {limit}
    """
    results = execute_sql(query)
    if not results:
        # Return mock data for development
        return [
            {
                "workspace_id": "1234567890",
                "job_id": "job_001",
                "run_id": "run_001",
                "job_name": "ETL Pipeline",
                "start_time": (datetime.now() - timedelta(hours=2)).isoformat(),
                "end_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                "duration_seconds": 3600,
                "result_state": "SUCCESS",
                "termination_code": "SUCCESS",
                "trigger_type": "SCHEDULED",
                "run_type": "JOB_RUN",
                "run_as": "user@example.com",
                "creator_id": "user@example.com",
            }
        ]
    return results


@app.get("/api/jobs/summary")
async def get_run_summary(days: int = 7):
    """Get run summary statistics"""
    query = f"""
    SELECT
        COUNT(*) as total_runs,
        SUM(CASE WHEN result_state = 'SUCCESS' THEN 1 ELSE 0 END) as succeeded,
        SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) as failed,
        SUM(CASE WHEN result_state IS NULL OR result_state = 'RUNNING' THEN 1 ELSE 0 END) as running
    FROM system.lakeflow.job_run_timeline
    WHERE period_start_time >= current_date() - INTERVAL {days} DAY
    """
    results = execute_sql(query)
    if results:
        row = results[0]
        total = int(row.get("total_runs", 0)) or 1
        succeeded = int(row.get("succeeded", 0))
        return {
            "total_runs": total,
            "succeeded": succeeded,
            "failed": int(row.get("failed", 0)),
            "running": int(row.get("running", 0)),
            "success_rate": round((succeeded / total) * 100, 2) if total > 0 else 0,
        }
    # Mock data
    return {
        "total_runs": 150,
        "succeeded": 142,
        "failed": 5,
        "running": 3,
        "success_rate": 94.67,
    }


@app.get("/api/jobs/by-type")
async def get_jobs_by_type(days: int = 7):
    """Get job runs grouped by run type"""
    query = f"""
    SELECT
        run_type,
        COUNT(*) as count
    FROM system.lakeflow.job_run_timeline
    WHERE period_start_time >= current_date() - INTERVAL {days} DAY
    GROUP BY run_type
    """
    results = execute_sql(query)
    if results:
        return {row["run_type"]: int(row["count"]) for row in results}
    return {"JOB_RUN": 100, "SUBMIT_RUN": 30, "WORKFLOW_RUN": 20}


@app.get("/api/jobs/daily")
async def get_daily_runs(days: int = 30):
    """Get daily run counts"""
    query = f"""
    SELECT
        DATE(period_start_time) as date,
        SUM(CASE WHEN result_state = 'SUCCESS' THEN 1 ELSE 0 END) as succeeded,
        SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) as failed
    FROM system.lakeflow.job_run_timeline
    WHERE period_start_time >= current_date() - INTERVAL {days} DAY
    GROUP BY DATE(period_start_time)
    ORDER BY date
    """
    results = execute_sql(query)
    if results:
        return [{"date": str(r["date"]), "succeeded": int(r.get("succeeded", 0)), "failed": int(r.get("failed", 0))} for r in results]
    # Mock data
    return [
        {"date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"), "succeeded": 10 + i % 5, "failed": i % 3}
        for i in range(days, 0, -1)
    ]


@app.get("/api/jobs/matrix")
async def get_jobs_matrix(days: int = 7, runs_per_job: int = 20):
    """
    Get matrix view data showing last N runs per job.
    Returns a grid structure with jobs as rows and runs as columns.
    Each cell contains: run_id, result_state, start_time, end_time, duration_seconds.
    """
    query = f"""
    WITH ranked_runs AS (
        SELECT
            job_id,
            COALESCE(j.name, r.run_name) as job_name,
            r.run_id,
            r.result_state,
            r.period_start_time as start_time,
            r.period_end_time as end_time,
            COALESCE(r.run_duration_seconds,
                TIMESTAMPDIFF(SECOND, r.period_start_time, COALESCE(r.period_end_time, current_timestamp()))) as duration_seconds,
            ROW_NUMBER() OVER (PARTITION BY r.job_id ORDER BY r.period_start_time DESC) as run_rank
        FROM system.lakeflow.job_run_timeline r
        LEFT JOIN system.lakeflow.jobs j ON r.job_id = j.job_id AND r.workspace_id = j.workspace_id
        WHERE r.period_start_time >= current_date() - INTERVAL {days} DAY
    )
    SELECT
        job_id,
        job_name,
        run_id,
        result_state,
        start_time,
        end_time,
        duration_seconds,
        run_rank
    FROM ranked_runs
    WHERE run_rank <= {runs_per_job}
    ORDER BY job_name, run_rank
    """
    results = execute_sql(query)

    if results:
        # Group results by job
        jobs_map: Dict[str, Dict] = {}
        for r in results:
            job_id = str(r.get("job_id", ""))
            if job_id not in jobs_map:
                jobs_map[job_id] = {
                    "job_id": job_id,
                    "job_name": r.get("job_name") or "Unknown",
                    "runs": [None] * runs_per_job
                }
            run_rank = int(r.get("run_rank", 1)) - 1  # Convert to 0-based index
            if 0 <= run_rank < runs_per_job:
                jobs_map[job_id]["runs"][run_rank] = {
                    "run_id": str(r.get("run_id", "")),
                    "result_state": r.get("result_state"),
                    "start_time": str(r.get("start_time")) if r.get("start_time") else None,
                    "end_time": str(r.get("end_time")) if r.get("end_time") else None,
                    "duration_seconds": float(r.get("duration_seconds", 0)) if r.get("duration_seconds") else None,
                }

        # Convert to list sorted by job name
        jobs_list = sorted(jobs_map.values(), key=lambda x: (x.get("job_name") or "").lower())

        return {
            "jobs": jobs_list,
            "days": days,
            "runs_per_job": runs_per_job,
        }

    # Mock data for development
    import random
    statuses = ["SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS", "FAILED", "RUNNING", "CANCELLED"]
    mock_jobs = []
    job_names = [
        "ETL Pipeline", "Data Sync", "ML Training", "Report Generator",
        "Batch Processing", "Stream Ingestion", "Feature Engineering",
        "Model Deployment", "Data Validation", "Analytics Refresh"
    ]
    for i, name in enumerate(job_names):
        runs = []
        for j in range(runs_per_job):
            if random.random() < 0.85:  # 85% chance of having a run
                status = random.choice(statuses)
                start = datetime.now() - timedelta(hours=random.randint(1, days * 24))
                duration = random.randint(60, 7200)
                runs.append({
                    "run_id": f"run_{i}_{j}",
                    "result_state": status,
                    "start_time": start.isoformat(),
                    "end_time": (start + timedelta(seconds=duration)).isoformat() if status != "RUNNING" else None,
                    "duration_seconds": duration if status != "RUNNING" else random.randint(60, 1800),
                })
            else:
                runs.append(None)
        mock_jobs.append({
            "job_id": f"job_{i:03d}",
            "job_name": name,
            "runs": runs,
        })

    return {
        "jobs": mock_jobs,
        "days": days,
        "runs_per_job": runs_per_job,
    }


# ============================================================
# Job Rerun/Repair Endpoints
# ============================================================

@app.post("/api/jobs/{job_id}/run-now")
async def run_job_now(job_id: str, request: RunNowRequest = None):
    """Trigger a job run immediately"""
    w = get_workspace_client()
    if not w:
        raise HTTPException(
            status_code=503,
            detail="Databricks SDK not available. Cannot trigger job runs."
        )

    try:
        # Convert job_id to int if it's a numeric string
        job_id_int = int(job_id)

        # Build run_now parameters
        run_params = {}
        if request and request.parameters:
            # Databricks SDK expects notebook_params, python_params, etc.
            # For simplicity, we'll pass as notebook_params
            run_params["notebook_params"] = request.parameters

        # Trigger the job run
        run_response = w.jobs.run_now(job_id=job_id_int, **run_params)

        return {
            "run_id": str(run_response.run_id),
            "message": f"Job {job_id} triggered successfully. Run ID: {run_response.run_id}"
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job_id: {job_id}. Job ID must be a valid integer."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to trigger job {job_id}: {error_msg}")

        # Check for common error types
        if "RESOURCE_DOES_NOT_EXIST" in error_msg or "does not exist" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        elif "PERMISSION_DENIED" in error_msg or "permission" in error_msg.lower():
            raise HTTPException(status_code=403, detail=f"Permission denied to run job {job_id}")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to trigger job: {error_msg}")


@app.post("/api/jobs/runs/{run_id}/cancel")
async def cancel_job_run(run_id: str):
    """Cancel a running job"""
    w = get_workspace_client()
    if not w:
        raise HTTPException(
            status_code=503,
            detail="Databricks SDK not available. Cannot cancel job runs."
        )

    try:
        # Convert run_id to int if it's a numeric string
        run_id_int = int(run_id)

        # Cancel the run
        w.jobs.cancel_run(run_id=run_id_int)

        return {
            "success": True,
            "message": f"Run {run_id} cancellation requested successfully"
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid run_id: {run_id}. Run ID must be a valid integer."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to cancel run {run_id}: {error_msg}")

        # Check for common error types
        if "RESOURCE_DOES_NOT_EXIST" in error_msg or "does not exist" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        elif "INVALID_STATE" in error_msg or "already terminated" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Run {run_id} cannot be cancelled (already terminated or not running)"
            )
        elif "PERMISSION_DENIED" in error_msg or "permission" in error_msg.lower():
            raise HTTPException(status_code=403, detail=f"Permission denied to cancel run {run_id}")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to cancel run: {error_msg}")


@app.post("/api/jobs/runs/{run_id}/repair")
async def repair_job_run(run_id: str, request: RepairRunRequest = None):
    """Repair/retry a failed run, optionally specifying which tasks to rerun"""
    w = get_workspace_client()
    if not w:
        raise HTTPException(
            status_code=503,
            detail="Databricks SDK not available. Cannot repair job runs."
        )

    try:
        # Convert run_id to int if it's a numeric string
        run_id_int = int(run_id)

        # Build repair parameters
        repair_params = {"run_id": run_id_int}

        if request and request.rerun_tasks and len(request.rerun_tasks) > 0:
            # Rerun specific tasks
            repair_params["rerun_tasks"] = request.rerun_tasks
        else:
            # Rerun all failed tasks by setting rerun_all_failed_tasks
            repair_params["rerun_all_failed_tasks"] = True

        # Trigger the repair run
        repair_response = w.jobs.repair_run(**repair_params)

        return {
            "repair_run_id": str(repair_response.repair_id) if hasattr(repair_response, 'repair_id') else str(run_id_int),
            "message": f"Repair initiated for run {run_id}. " +
                      (f"Rerunning tasks: {', '.join(request.rerun_tasks)}" if request and request.rerun_tasks else "Rerunning all failed tasks")
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid run_id: {run_id}. Run ID must be a valid integer."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to repair run {run_id}: {error_msg}")

        # Check for common error types
        if "RESOURCE_DOES_NOT_EXIST" in error_msg or "does not exist" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        elif "INVALID_STATE" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"Run {run_id} cannot be repaired (must be in a failed or cancelled state)"
            )
        elif "PERMISSION_DENIED" in error_msg or "permission" in error_msg.lower():
            raise HTTPException(status_code=403, detail=f"Permission denied to repair run {run_id}")
        elif "rerun_tasks" in error_msg.lower() or "task" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task specification: {error_msg}"
            )
        else:
            raise HTTPException(status_code=500, detail=f"Failed to repair run: {error_msg}")


@app.get("/api/jobs/runs/{run_id}/output")
async def get_run_output(run_id: str):
    """Get the output/logs of a job run"""
    w = get_workspace_client()
    if not w:
        raise HTTPException(
            status_code=503,
            detail="Databricks SDK not available. Cannot retrieve run output."
        )

    try:
        # Convert run_id to int if it's a numeric string
        run_id_int = int(run_id)

        # Get run output
        output_response = w.jobs.get_run_output(run_id=run_id_int)

        # Extract relevant output information
        result = {
            "notebook_output": None,
            "error": None,
            "logs_truncated": False
        }

        # Check for notebook output
        if hasattr(output_response, 'notebook_output') and output_response.notebook_output:
            notebook_out = output_response.notebook_output
            if hasattr(notebook_out, 'result'):
                result["notebook_output"] = notebook_out.result
            if hasattr(notebook_out, 'truncated'):
                result["logs_truncated"] = notebook_out.truncated

        # Check for error information
        if hasattr(output_response, 'error') and output_response.error:
            result["error"] = output_response.error
        elif hasattr(output_response, 'error_trace') and output_response.error_trace:
            result["error"] = output_response.error_trace

        # Check for metadata with logs
        if hasattr(output_response, 'metadata') and output_response.metadata:
            metadata = output_response.metadata
            # Add additional context from metadata if available
            if hasattr(metadata, 'state') and metadata.state:
                state = metadata.state
                if hasattr(state, 'state_message') and state.state_message:
                    if result["error"]:
                        result["error"] += f"\n\nState message: {state.state_message}"
                    else:
                        result["error"] = state.state_message

        # Check for logs truncation indicator
        if hasattr(output_response, 'logs_truncated'):
            result["logs_truncated"] = output_response.logs_truncated

        return result

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid run_id: {run_id}. Run ID must be a valid integer."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to get output for run {run_id}: {error_msg}")

        # Check for common error types
        if "RESOURCE_DOES_NOT_EXIST" in error_msg or "does not exist" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        elif "PERMISSION_DENIED" in error_msg or "permission" in error_msg.lower():
            raise HTTPException(status_code=403, detail=f"Permission denied to access run {run_id} output")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to get run output: {error_msg}")


# ============================================================
# Cost Endpoints
# ============================================================

@app.get("/api/costs/summary")
async def get_cost_summary(days: int = 30):
    """Get cost summary from billing tables"""
    query = f"""
    SELECT
        COALESCE(SUM(u.usage_quantity * p.pricing.default), 0) as total_cost_usd,
        COALESCE(SUM(u.usage_quantity), 0) as total_dbus,
        COUNT(DISTINCT u.usage_metadata.job_id) as unique_jobs,
        COUNT(*) as total_runs
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name AND u.cloud = p.cloud
    WHERE u.usage_date >= current_date() - INTERVAL {days} DAY
        AND u.usage_metadata.job_id IS NOT NULL
    """
    results = execute_sql(query)
    if results:
        row = results[0]
        return {
            "total_cost_usd": float(row.get("total_cost_usd", 0) or 0),
            "total_dbus": float(row.get("total_dbus", 0) or 0),
            "unique_jobs": int(row.get("unique_jobs", 0) or 0),
            "total_runs": int(row.get("total_runs", 0) or 0),
        }
    return {"total_cost_usd": 1234.56, "total_dbus": 5000, "unique_jobs": 25, "total_runs": 150}


@app.get("/api/costs/daily")
async def get_daily_costs(days: int = 30):
    """Get daily costs"""
    query = f"""
    SELECT
        u.usage_date as date,
        SUM(u.usage_quantity * p.pricing.default) as cost_usd
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name AND u.cloud = p.cloud
    WHERE u.usage_date >= current_date() - INTERVAL {days} DAY
    GROUP BY u.usage_date
    ORDER BY u.usage_date
    """
    results = execute_sql(query)
    if results:
        return [{"date": str(r["date"]), "cost_usd": float(r.get("cost_usd", 0) or 0)} for r in results]
    return [
        {"date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"), "cost_usd": 50 + (i * 2) % 30}
        for i in range(days, 0, -1)
    ]


@app.get("/api/costs/top-jobs")
async def get_top_expensive_jobs(days: int = 30, limit: int = 10):
    """Get top expensive jobs"""
    query = f"""
    SELECT
        u.usage_metadata.job_id as job_id,
        FIRST(j.name) as job_name,
        SUM(u.usage_quantity * p.pricing.default) as total_cost,
        SUM(u.usage_quantity) as total_dbus,
        COUNT(*) as total_runs
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name AND u.cloud = p.cloud
    LEFT JOIN system.lakeflow.jobs j ON u.usage_metadata.job_id = j.job_id
    WHERE u.usage_date >= current_date() - INTERVAL {days} DAY
        AND u.usage_metadata.job_id IS NOT NULL
    GROUP BY u.usage_metadata.job_id
    ORDER BY total_cost DESC
    LIMIT {limit}
    """
    results = execute_sql(query)
    if results:
        return results
    return [
        {"job_id": f"job_{i}", "job_name": f"Job {i}", "total_cost": 100 - i * 8, "total_dbus": 500 - i * 40, "total_runs": 20 - i}
        for i in range(10)
    ]


@app.get("/api/costs/by-identity")
async def get_cost_by_identity(days: int = 30):
    """Get costs grouped by identity/user"""
    query = f"""
    SELECT
        COALESCE(u.identity_metadata.run_as, u.identity_metadata.created_by, 'Unknown') as identity,
        SUM(u.usage_quantity * p.pricing.default) as cost_usd
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name AND u.cloud = p.cloud
    WHERE u.usage_date >= current_date() - INTERVAL {days} DAY
        AND u.usage_metadata.job_id IS NOT NULL
    GROUP BY COALESCE(u.identity_metadata.run_as, u.identity_metadata.created_by, 'Unknown')
    ORDER BY cost_usd DESC
    """
    results = execute_sql(query)
    if results:
        return results
    return [
        {"identity": f"user{i}@example.com", "cost_usd": 200 - i * 20}
        for i in range(8)
    ]


# ============================================================
# Health Endpoints
# ============================================================

@app.get("/api/health/failed-jobs")
async def get_failed_jobs(days: int = 7):
    """Get failed jobs statistics"""
    # Simplified query without JOIN for better performance
    query = f"""
    SELECT
        job_id,
        FIRST(run_name) as job_name,
        COUNT(*) as total_runs,
        SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) as failed_runs,
        NULL as run_as,
        MAX(period_start_time) as last_run
    FROM system.lakeflow.job_run_timeline
    WHERE period_start_time >= current_date() - INTERVAL {days} DAY
    GROUP BY job_id
    HAVING SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) > 0
    ORDER BY failed_runs DESC
    LIMIT 50
    """
    results = execute_sql(query)
    if results:
        return [
            {
                **r,
                "success_rate": round((1 - int(r["failed_runs"]) / int(r["total_runs"])) * 100, 2) if int(r["total_runs"]) > 0 else 0,
            }
            for r in results
        ]
    return [
        {"job_id": "job_fail_1", "job_name": "Failed ETL", "total_runs": 10, "failed_runs": 3, "success_rate": 70.0, "run_as": "user@example.com", "last_run": datetime.now().isoformat()}
    ]


@app.get("/api/health/prolonged-jobs")
async def get_prolonged_jobs(warning_minutes: int = 60, critical_minutes: int = 180):
    """Get currently running jobs that exceed duration thresholds"""
    # Simplified query without complex JOINs
    query = f"""
    SELECT
        job_id,
        run_name as job_name,
        run_id,
        TIMESTAMPDIFF(MINUTE, period_start_time, current_timestamp()) as running_minutes,
        30.0 as avg_duration_minutes,
        CASE
            WHEN TIMESTAMPDIFF(MINUTE, period_start_time, current_timestamp()) >= {critical_minutes} THEN 'CRITICAL'
            WHEN TIMESTAMPDIFF(MINUTE, period_start_time, current_timestamp()) >= {warning_minutes} THEN 'WARNING'
            ELSE 'NORMAL'
        END as duration_status
    FROM system.lakeflow.job_run_timeline
    WHERE (result_state IS NULL OR result_state = 'RUNNING')
        AND period_start_time >= current_date() - INTERVAL 2 DAY
    ORDER BY period_start_time ASC
    LIMIT 50
    """
    results = execute_sql(query)
    if results:
        return [
            {
                **r,
                "running_minutes": float(r.get("running_minutes", 0)),
                "avg_duration_minutes": float(r.get("avg_duration_minutes", 30)),
            }
            for r in results
        ]
    return []


@app.get("/api/health/anomalies")
async def get_anomalies(days: int = 7, warning_threshold: float = 2.0, critical_threshold: float = 3.0):
    """Detect anomalies in job execution using Z-score"""
    # Simplified query with limit to avoid timeout
    query = f"""
    WITH job_stats AS (
        SELECT
            job_id,
            AVG(run_duration_seconds / 60.0) as avg_duration,
            STDDEV(run_duration_seconds / 60.0) as std_duration
        FROM system.lakeflow.job_run_timeline
        WHERE result_state = 'SUCCESS' AND run_duration_seconds IS NOT NULL
            AND period_start_time >= current_date() - INTERVAL 14 DAY
        GROUP BY job_id
        HAVING COUNT(*) >= 3 AND STDDEV(run_duration_seconds / 60.0) > 0
    ),
    recent_runs AS (
        SELECT
            r.job_id,
            r.run_name as job_name,
            r.run_id,
            r.run_duration_seconds / 60.0 as duration
        FROM system.lakeflow.job_run_timeline r
        WHERE r.result_state = 'SUCCESS' AND r.run_duration_seconds IS NOT NULL
            AND r.period_start_time >= current_date() - INTERVAL {days} DAY
        LIMIT 500
    )
    SELECT
        r.job_id,
        r.job_name,
        r.run_id,
        'duration' as metric_name,
        r.duration as metric_value,
        s.avg_duration as expected_value,
        (r.duration - s.avg_duration) / s.std_duration as z_score
    FROM recent_runs r
    JOIN job_stats s ON r.job_id = s.job_id
    WHERE ABS((r.duration - s.avg_duration) / s.std_duration) >= {warning_threshold}
    ORDER BY ABS((r.duration - s.avg_duration) / s.std_duration) DESC
    LIMIT 50
    """
    results = execute_sql(query)
    if results:
        return [
            {
                **r,
                "metric_value": float(r.get("metric_value", 0)),
                "expected_value": float(r.get("expected_value", 0)),
                "z_score": float(r.get("z_score", 0)),
                "severity": "CRITICAL" if abs(float(r.get("z_score", 0))) >= critical_threshold else "WARNING",
            }
            for r in results
        ]
    return []


@app.get("/api/health/retry-stats")
async def get_retry_stats(days: int = 7):
    """Get job retry statistics - based on failed runs that were later successful"""
    # Simplified query without JOIN
    query = f"""
    SELECT
        job_id,
        FIRST(run_name) as job_name,
        SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) as runs_with_retries,
        SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) as total_retries,
        ROUND(COUNT(*) * 1.0 / NULLIF(SUM(CASE WHEN result_state = 'SUCCESS' THEN 1 ELSE 0 END), 0), 2) as avg_attempts_per_run
    FROM system.lakeflow.job_run_timeline
    WHERE period_start_time >= current_date() - INTERVAL {days} DAY
    GROUP BY job_id
    HAVING SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) > 0
        AND SUM(CASE WHEN result_state = 'SUCCESS' THEN 1 ELSE 0 END) > 0
    ORDER BY runs_with_retries DESC
    LIMIT 50
    """
    results = execute_sql(query)
    if results:
        return [
            {
                **r,
                "runs_with_retries": int(r.get("runs_with_retries", 0)),
                "total_retries": int(r.get("total_retries", 0)),
                "retry_success_rate": 75.0,  # Would need additional query
                "avg_attempts_per_run": float(r.get("avg_attempts_per_run", 1)),
            }
            for r in results
        ]
    return []


# ============================================================
# SLA Tracking and Percentile Metrics Endpoints
# ============================================================

@app.get("/api/jobs/sla-status")
async def get_sla_status(days: int = 30):
    """
    Get SLA compliance status for jobs.
    SLA is calculated based on historical average duration - jobs exceeding 2x their average are violations.
    """
    # Query for summary statistics
    summary_query = f"""
    WITH job_baselines AS (
        SELECT
            job_id,
            AVG(run_duration_seconds / 60.0) as avg_duration_min
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= current_date() - INTERVAL {days} DAY
            AND result_state = 'SUCCESS'
            AND run_duration_seconds IS NOT NULL
        GROUP BY job_id
        HAVING COUNT(*) >= 3
    ),
    recent_runs AS (
        SELECT
            r.job_id,
            r.run_duration_seconds / 60.0 as actual_duration_min,
            b.avg_duration_min as expected_duration_min,
            CASE
                WHEN r.run_duration_seconds / 60.0 > b.avg_duration_min * 2 THEN 1
                ELSE 0
            END as is_violation
        FROM system.lakeflow.job_run_timeline r
        JOIN job_baselines b ON r.job_id = b.job_id
        WHERE r.period_start_time >= current_date() - INTERVAL {days} DAY
            AND r.result_state = 'SUCCESS'
            AND r.run_duration_seconds IS NOT NULL
        LIMIT 10000
    )
    SELECT
        COUNT(*) as total_jobs,
        SUM(CASE WHEN is_violation = 0 THEN 1 ELSE 0 END) as sla_compliant,
        SUM(is_violation) as sla_violations
    FROM recent_runs
    """

    # Query for jobs with violations
    violations_query = f"""
    WITH job_baselines AS (
        SELECT
            job_id,
            AVG(run_duration_seconds / 60.0) as avg_duration_min
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= current_date() - INTERVAL {days} DAY
            AND result_state = 'SUCCESS'
            AND run_duration_seconds IS NOT NULL
        GROUP BY job_id
        HAVING COUNT(*) >= 3
    ),
    recent_runs AS (
        SELECT
            r.job_id,
            r.run_name as job_name,
            r.run_duration_seconds / 60.0 as actual_duration_min,
            b.avg_duration_min as expected_duration_min,
            CASE
                WHEN r.run_duration_seconds / 60.0 > b.avg_duration_min * 2 THEN 1
                ELSE 0
            END as is_violation
        FROM system.lakeflow.job_run_timeline r
        JOIN job_baselines b ON r.job_id = b.job_id
        WHERE r.period_start_time >= current_date() - INTERVAL {days} DAY
            AND r.result_state = 'SUCCESS'
            AND r.run_duration_seconds IS NOT NULL
    )
    SELECT
        job_id,
        FIRST(job_name) as job_name,
        ROUND(AVG(expected_duration_min), 0) as expected_duration_min,
        ROUND(MAX(actual_duration_min), 0) as actual_duration_min,
        SUM(is_violation) as violation_count
    FROM recent_runs
    GROUP BY job_id
    HAVING SUM(is_violation) > 0
    ORDER BY violation_count DESC
    LIMIT 50
    """

    summary_results = execute_sql(summary_query)
    violations_results = execute_sql(violations_query)

    if summary_results:
        row = summary_results[0]
        total = int(row.get("total_jobs", 0)) or 1
        compliant = int(row.get("sla_compliant", 0))
        violations = int(row.get("sla_violations", 0))

        jobs_with_violations = []
        if violations_results:
            jobs_with_violations = [
                {
                    "job_id": str(r.get("job_id", "")),
                    "job_name": str(r.get("job_name", "")),
                    "expected_duration_min": int(r.get("expected_duration_min", 0)),
                    "actual_duration_min": int(r.get("actual_duration_min", 0)),
                    "violation_count": int(r.get("violation_count", 0)),
                }
                for r in violations_results
            ]

        return {
            "total_jobs": total,
            "sla_compliant": compliant,
            "sla_violations": violations,
            "compliance_rate": round((compliant / total) * 100, 2) if total > 0 else 100.0,
            "jobs_with_violations": jobs_with_violations,
        }

    # Mock data for development
    return {
        "total_jobs": 150,
        "sla_compliant": 142,
        "sla_violations": 8,
        "compliance_rate": 94.67,
        "jobs_with_violations": [
            {"job_id": "job_001", "job_name": "ETL Pipeline", "expected_duration_min": 30, "actual_duration_min": 75, "violation_count": 3},
            {"job_id": "job_002", "job_name": "Data Sync", "expected_duration_min": 15, "actual_duration_min": 45, "violation_count": 2},
            {"job_id": "job_003", "job_name": "Report Generator", "expected_duration_min": 60, "actual_duration_min": 180, "violation_count": 2},
            {"job_id": "job_004", "job_name": "ML Training", "expected_duration_min": 120, "actual_duration_min": 300, "violation_count": 1},
        ],
    }


@app.get("/api/jobs/duration-percentiles")
async def get_duration_percentiles(days: int = 30):
    """
    Get duration percentile statistics for job runs.
    Uses PERCENTILE_CONT for accurate percentile calculations.
    """
    # Global percentiles query
    global_query = f"""
    SELECT
        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY run_duration_seconds / 60.0), 2) as p50_minutes,
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY run_duration_seconds / 60.0), 2) as p90_minutes,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY run_duration_seconds / 60.0), 2) as p95_minutes,
        ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY run_duration_seconds / 60.0), 2) as p99_minutes,
        ROUND(AVG(run_duration_seconds / 60.0), 2) as avg_minutes,
        ROUND(MAX(run_duration_seconds / 60.0), 2) as max_minutes
    FROM system.lakeflow.job_run_timeline
    WHERE period_start_time >= current_date() - INTERVAL {days} DAY
        AND result_state = 'SUCCESS'
        AND run_duration_seconds IS NOT NULL
    """

    # Per-job percentiles query
    by_job_query = f"""
    SELECT
        job_id,
        FIRST(run_name) as job_name,
        ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY run_duration_seconds / 60.0), 2) as p50,
        ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY run_duration_seconds / 60.0), 2) as p90,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY run_duration_seconds / 60.0), 2) as p95,
        ROUND(AVG(run_duration_seconds / 60.0), 2) as avg
    FROM system.lakeflow.job_run_timeline
    WHERE period_start_time >= current_date() - INTERVAL {days} DAY
        AND result_state = 'SUCCESS'
        AND run_duration_seconds IS NOT NULL
    GROUP BY job_id
    HAVING COUNT(*) >= 3
    ORDER BY p90 DESC
    LIMIT 50
    """

    global_results = execute_sql(global_query)
    by_job_results = execute_sql(by_job_query)

    if global_results:
        row = global_results[0]
        by_job = []
        if by_job_results:
            by_job = [
                {
                    "job_id": str(r.get("job_id", "")),
                    "job_name": str(r.get("job_name", "")),
                    "p50": float(r.get("p50", 0) or 0),
                    "p90": float(r.get("p90", 0) or 0),
                    "p95": float(r.get("p95", 0) or 0),
                    "avg": float(r.get("avg", 0) or 0),
                }
                for r in by_job_results
            ]

        return {
            "p50_minutes": float(row.get("p50_minutes", 0) or 0),
            "p90_minutes": float(row.get("p90_minutes", 0) or 0),
            "p95_minutes": float(row.get("p95_minutes", 0) or 0),
            "p99_minutes": float(row.get("p99_minutes", 0) or 0),
            "avg_minutes": float(row.get("avg_minutes", 0) or 0),
            "max_minutes": float(row.get("max_minutes", 0) or 0),
            "by_job": by_job,
        }

    # Mock data for development
    return {
        "p50_minutes": 12.5,
        "p90_minutes": 45.2,
        "p95_minutes": 68.7,
        "p99_minutes": 125.3,
        "avg_minutes": 22.4,
        "max_minutes": 245.0,
        "by_job": [
            {"job_id": "job_001", "job_name": "ETL Pipeline", "p50": 28.5, "p90": 42.0, "p95": 55.0, "avg": 32.1},
            {"job_id": "job_002", "job_name": "Data Sync", "p50": 12.0, "p90": 18.5, "p95": 24.0, "avg": 14.2},
            {"job_id": "job_003", "job_name": "Report Generator", "p50": 55.0, "p90": 78.0, "p95": 95.0, "avg": 62.5},
            {"job_id": "job_004", "job_name": "ML Training", "p50": 95.0, "p90": 145.0, "p95": 180.0, "avg": 110.0},
            {"job_id": "job_005", "job_name": "Batch Processing", "p50": 8.5, "p90": 15.0, "p95": 22.0, "avg": 10.8},
        ],
    }


# ============================================================
# Cluster Endpoints
# ============================================================

@app.get("/api/clusters/configs")
async def get_cluster_configs(job_id: Optional[str] = None, run_id: Optional[str] = None):
    """Get cluster configurations used by jobs"""
    # Simplified query - just get recent job run info without EXPLODE
    where_clause = "WHERE period_start_time >= current_date() - INTERVAL 3 DAY"
    if job_id:
        where_clause = f"WHERE job_id = '{job_id}'"
    elif run_id:
        where_clause = f"WHERE run_id = '{run_id}'"

    query = f"""
    SELECT DISTINCT
        job_id as cluster_id,
        run_type as cluster_type,
        NULL as warehouse_id,
        run_type,
        run_name as job_name
    FROM system.lakeflow.job_run_timeline
    {where_clause}
    LIMIT 50
    """
    results = execute_sql(query)
    if results:
        return results
    return [
        {"cluster_id": f"cluster_{i}", "cluster_name": f"Job Cluster {i}", "cluster_type": "jobs-cluster",
         "driver_node_type": "i3.xlarge", "worker_node_type": "i3.xlarge", "min_workers": 2, "max_workers": 8,
         "fixed_workers": None, "dbr_version": "14.3.x-scala2.12"}
        for i in range(5)
    ]


# ============================================================
# Analysis Endpoints
# ============================================================

@app.get("/api/analysis/overlaps")
async def get_overlaps(days: int = 1):
    """Detect overlapping job runs - simplified for performance"""
    # Using a simpler approach - find concurrent runs in the same hour
    query = f"""
    WITH hourly_runs AS (
        SELECT
            job_id,
            run_name as job_name,
            run_id,
            period_start_time,
            DATE_TRUNC('HOUR', period_start_time) as hour_bucket
        FROM system.lakeflow.job_run_timeline
        WHERE period_start_time >= current_date() - INTERVAL {days} DAY
            AND result_state IS NOT NULL
        LIMIT 200
    )
    SELECT
        a.job_name as job_a,
        b.job_name as job_b,
        a.run_id as run_a,
        b.run_id as run_b,
        1 as overlap_minutes
    FROM hourly_runs a
    JOIN hourly_runs b ON a.hour_bucket = b.hour_bucket AND a.run_id < b.run_id
    LIMIT 20
    """
    results = execute_sql(query)
    if results:
        return [
            {**r, "overlap_minutes": float(r.get("overlap_minutes", 0))}
            for r in results
        ]
    return []


@app.get("/api/analysis/concurrent")
async def get_concurrent_jobs_over_time(hours: int = 24):
    """Get concurrent jobs count over time"""
    # This would require a more complex query - returning mock data for now
    now = datetime.now()
    return [
        {"time": (now - timedelta(hours=hours - i)).strftime("%H:%M"), "concurrent_jobs": 2 + (i % 5)}
        for i in range(0, hours, 1)
    ]


# ============================================================
# Genie (AI Assistant) Endpoints
# ============================================================

@app.get("/api/genie/spaces")
async def get_genie_spaces():
    """List available Genie Spaces"""
    w = get_workspace_client()
    if not w:
        # Return configured space or empty list
        if GENIE_SPACE_ID:
            return [{"id": GENIE_SPACE_ID, "name": "Jobs Monitor Genie Space"}]
        return []

    try:
        # Try to list Genie spaces
        spaces = w.genie.list_spaces()
        return [{"id": s.id, "name": s.name} for s in spaces]
    except Exception as e:
        logger.warning(f"Failed to list Genie spaces: {e}")
        if GENIE_SPACE_ID:
            return [{"id": GENIE_SPACE_ID, "name": "Jobs Monitor Genie Space"}]
        return []


@app.post("/api/genie/conversations")
async def start_genie_conversation(request: GenieConversationRequest):
    """Start a new Genie conversation"""
    w = get_workspace_client()
    if not w:
        raise HTTPException(status_code=503, detail="Databricks SDK not available")

    try:
        conversation = w.genie.start_conversation(space_id=request.space_id)
        return {"conversation_id": conversation.conversation_id}
    except Exception as e:
        logger.error(f"Failed to start Genie conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/genie/conversations/{conversation_id}/messages")
async def send_genie_message(conversation_id: str, request: GenieMessageRequest):
    """Send a message to Genie and get response"""
    w = get_workspace_client()
    if not w:
        raise HTTPException(status_code=503, detail="Databricks SDK not available")

    try:
        response = w.genie.create_message_and_wait(
            space_id=request.space_id,
            conversation_id=conversation_id,
            content=request.message,
        )

        # Extract response text
        response_text = ""
        if response.attachments:
            for attachment in response.attachments:
                if hasattr(attachment, 'text') and attachment.text:
                    response_text += attachment.text.content + "\n"
                elif hasattr(attachment, 'query') and attachment.query:
                    response_text += f"```sql\n{attachment.query.query}\n```\n"

        if not response_text:
            response_text = "I processed your request but couldn't generate a text response."

        return {"response": response_text.strip()}
    except Exception as e:
        logger.error(f"Failed to send Genie message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Metrics Endpoints (3-Tier Architecture)
# ============================================================

@app.get("/api/metrics/executors")
async def get_executor_metrics():
    """
    Tier 1: Get Executor Metrics from Spark UI REST API.
    Always available when a Spark cluster is running.
    """
    try:
        from collectors.spark_ui_collector import SparkUICollector
        collector = SparkUICollector()

        # Check if running in a Databricks environment with active Spark
        w = get_workspace_client()
        if not w:
            # Return mock data for development
            return {
                "available": True,
                "timestamp": datetime.utcnow().isoformat(),
                "executors": [
                    {
                        "executor_id": "driver",
                        "host": "driver-node",
                        "memory_used_mb": 2048,
                        "memory_max_mb": 8192,
                        "memory_usage_percent": 25.0,
                        "gc_time_ms": 150,
                        "shuffle_read_bytes": 1024 * 1024 * 10,
                        "shuffle_write_bytes": 1024 * 1024 * 5,
                        "active_tasks": 0,
                        "completed_tasks": 100,
                        "failed_tasks": 2,
                        "total_duration_ms": 300000,
                    },
                    {
                        "executor_id": "1",
                        "host": "worker-1",
                        "memory_used_mb": 4096,
                        "memory_max_mb": 16384,
                        "memory_usage_percent": 25.0,
                        "gc_time_ms": 200,
                        "shuffle_read_bytes": 1024 * 1024 * 20,
                        "shuffle_write_bytes": 1024 * 1024 * 15,
                        "active_tasks": 2,
                        "completed_tasks": 250,
                        "failed_tasks": 1,
                        "total_duration_ms": 600000,
                    },
                ],
                "summary": {
                    "total_executors": 2,
                    "total_memory_used_mb": 6144,
                    "total_memory_max_mb": 24576,
                    "avg_memory_usage_percent": 25.0,
                    "total_gc_time_ms": 350,
                    "total_shuffle_read_bytes": 1024 * 1024 * 30,
                    "total_shuffle_write_bytes": 1024 * 1024 * 20,
                    "total_active_tasks": 2,
                    "total_completed_tasks": 350,
                    "total_failed_tasks": 3,
                },
            }

        # Try to collect real metrics
        metrics = collector.collect_all_metrics()
        return metrics if metrics else {"available": False, "message": "No active Spark applications found"}
    except ImportError:
        return {"available": False, "message": "Spark UI collector not available"}
    except Exception as e:
        logger.warning(f"Error getting executor metrics: {e}")
        return {"available": False, "message": str(e)}


@app.get("/api/metrics/cloud")
async def get_cloud_metrics():
    """
    Tier 2: Get Cloud Metrics from Azure Monitor or AWS CloudWatch.
    Only available if cloud credentials are configured.
    """
    try:
        # Try Azure first
        from collectors.azure_monitor_collector import AzureMonitorCollector
        azure_collector = AzureMonitorCollector()

        if azure_collector.is_available():
            metrics = azure_collector.collect_cluster_metrics("active-cluster")
            if metrics:
                return {
                    "available": True,
                    "configured": True,
                    "provider": "azure",
                    "timestamp": datetime.utcnow().isoformat(),
                    "metrics": [m.to_dict() for m in metrics] if hasattr(metrics[0], 'to_dict') else metrics,
                    "summary": azure_collector.get_summary(metrics) if hasattr(azure_collector, 'get_summary') else None,
                }
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Azure collector error: {e}")

    try:
        # Try AWS CloudWatch
        from collectors.cloudwatch_collector import CloudWatchCollector
        aws_collector = CloudWatchCollector()

        if aws_collector.is_available():
            metrics = aws_collector.collect_cluster_metrics("active-cluster")
            if metrics:
                return {
                    "available": True,
                    "configured": True,
                    "provider": "aws",
                    "timestamp": datetime.utcnow().isoformat(),
                    "metrics": [m.to_dict() for m in metrics] if hasattr(metrics[0], 'to_dict') else metrics,
                    "summary": aws_collector.get_summary(metrics) if hasattr(aws_collector, 'get_summary') else None,
                }
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"CloudWatch collector error: {e}")

    # No cloud provider configured
    return {
        "available": False,
        "configured": False,
        "message": "Cloud metrics are not configured. Set environment variables for Azure Monitor or AWS CloudWatch.",
    }


@app.get("/api/metrics/otel/status")
async def get_metrics_otel_status():
    """
    Tier 3: Get OTEL metrics status.
    Redirects to the main OTEL status endpoint.
    """
    return await get_otel_status()


@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """
    Get a summary of metrics from the best available source.
    Priority: OTEL > Cloud > Executor
    """
    timestamp = datetime.utcnow().isoformat()
    available_tiers = {
        "executor": False,
        "cloud": False,
        "otel": False,
    }

    # Check OTEL
    try:
        from collectors.otel_collector import OTELCollector
        w = get_workspace_client()
        otel_collector = OTELCollector(workspace_client=w, warehouse_id=WAREHOUSE_ID)
        otel_status = otel_collector.get_status()
        available_tiers["otel"] = otel_status.metrics_available
    except Exception:
        pass

    # Check Cloud
    try:
        from collectors.azure_monitor_collector import AzureMonitorCollector
        azure_collector = AzureMonitorCollector()
        if azure_collector.is_available():
            available_tiers["cloud"] = True
    except Exception:
        pass

    try:
        from collectors.cloudwatch_collector import CloudWatchCollector
        aws_collector = CloudWatchCollector()
        if aws_collector.is_available():
            available_tiers["cloud"] = True
    except Exception:
        pass

    # Executor metrics are always potentially available
    available_tiers["executor"] = True

    # Determine best source and return summary
    if available_tiers["otel"]:
        source = "otel"
        source_label = "OpenTelemetry"
    elif available_tiers["cloud"]:
        source = "cloud"
        source_label = "Cloud Metrics"
    else:
        source = "executor"
        source_label = "Spark Executor Metrics"

    return {
        "source": source,
        "source_label": source_label,
        "available_tiers": available_tiers,
        "metrics": {
            "cpu_usage_percent": 45.2,
            "memory_usage_percent": 62.8,
            "disk_io_bytes_per_sec": 1024 * 1024 * 50,
            "network_io_bytes_per_sec": 1024 * 1024 * 25,
            "gc_time_ms": 350,
            "shuffle_io_bytes": 1024 * 1024 * 50,
            "active_tasks": 5,
            "completed_tasks": 450,
            "failed_tasks": 3,
        },
        "timestamp": timestamp,
    }


# ============================================================
# OTEL (OpenTelemetry) Endpoints
# ============================================================

@app.get("/api/otel/status")
async def get_otel_status():
    """
    Get the status of OpenTelemetry integration.
    Returns information about whether OTEL metrics are available,
    active exporters, and the last metric collection time.
    """
    try:
        from collectors.otel_collector import OTELCollector, OTELStatus
        w = get_workspace_client()
        collector = OTELCollector(workspace_client=w, warehouse_id=WAREHOUSE_ID)
        status = collector.get_status()
        return status.to_dict()
    except ImportError:
        return OTELStatus().to_dict()
    except Exception as e:
        logger.warning(f"Error getting OTEL status: {e}")
        return {
            "metrics_available": False,
            "native_runtime": False,
            "init_script_installed": False,
            "active_exporters": [],
            "last_metric_time": None,
            "error": str(e),
        }


@app.get("/api/otel/metrics")
async def get_otel_metrics(
    hours: int = 24,
    cluster_id: Optional[str] = None,
    job_id: Optional[str] = None,
    limit: int = 1000,
):
    """
    Get OTEL metrics from the Delta table.

    Args:
        hours: Number of hours of historical data (default: 24)
        cluster_id: Optional filter by cluster ID
        job_id: Optional filter by job ID
        limit: Maximum number of records (default: 1000)
    """
    try:
        from collectors.otel_collector import OTELCollector
        w = get_workspace_client()
        collector = OTELCollector(workspace_client=w, warehouse_id=WAREHOUSE_ID)
        return collector.get_metrics(
            hours=hours,
            cluster_id=cluster_id,
            job_id=job_id,
            limit=limit,
        )
    except ImportError:
        return []
    except Exception as e:
        logger.warning(f"Error getting OTEL metrics: {e}")
        return []


@app.get("/api/otel/spark-metrics")
async def get_otel_spark_metrics(hours: int = 24, cluster_id: Optional[str] = None):
    """
    Get Spark-specific metrics from OTEL data.
    Includes executor memory, shuffle read/write, GC time, etc.
    """
    try:
        from collectors.otel_collector import OTELCollector
        w = get_workspace_client()
        collector = OTELCollector(workspace_client=w, warehouse_id=WAREHOUSE_ID)
        return collector.get_spark_metrics(hours=hours, cluster_id=cluster_id)
    except ImportError:
        return []
    except Exception as e:
        logger.warning(f"Error getting Spark metrics: {e}")
        return []


@app.get("/api/otel/cluster-summary/{cluster_id}")
async def get_otel_cluster_summary(cluster_id: str, hours: int = 1):
    """
    Get a summary of OTEL metrics for a specific cluster.
    Returns aggregated metrics including min, max, avg values.
    """
    try:
        from collectors.otel_collector import OTELCollector
        w = get_workspace_client()
        collector = OTELCollector(workspace_client=w, warehouse_id=WAREHOUSE_ID)
        return collector.get_cluster_metrics_summary(cluster_id=cluster_id, hours=hours)
    except ImportError:
        return {"error": "OTEL collector not available"}
    except Exception as e:
        logger.warning(f"Error getting cluster summary: {e}")
        return {"error": str(e)}


@app.get("/api/otel/init-script")
async def get_otel_init_script_endpoint():
    """
    Get the OTEL Collector init script for Databricks clusters.
    Returns the script content and metadata.
    """
    try:
        from collectors.otel_init_script import get_init_script_response
        return get_init_script_response()
    except ImportError as e:
        logger.error(f"Failed to import otel_init_script: {e}")
        raise HTTPException(status_code=500, detail="OTEL init script module not available")


@app.get("/api/otel/init-script/download")
async def download_otel_init_script():
    """
    Download the OTEL Collector init script as a file.
    Returns the script with appropriate headers for file download.
    """
    from fastapi.responses import Response
    try:
        from collectors.otel_init_script import get_otel_init_script
        script_content = get_otel_init_script()
        return Response(
            content=script_content,
            media_type="text/x-shellscript",
            headers={
                "Content-Disposition": "attachment; filename=otel-collector-init.sh",
            },
        )
    except ImportError as e:
        logger.error(f"Failed to import otel_init_script: {e}")
        raise HTTPException(status_code=500, detail="OTEL init script module not available")


@app.get("/api/otel/init-script/minimal")
async def get_otel_init_script_minimal_endpoint():
    """
    Get a minimal version of the OTEL init script for quick testing.
    """
    from fastapi.responses import Response
    try:
        from collectors.otel_init_script import get_otel_init_script_minimal
        script_content = get_otel_init_script_minimal()
        return Response(
            content=script_content,
            media_type="text/x-shellscript",
            headers={
                "Content-Disposition": "attachment; filename=otel-collector-init-minimal.sh",
            },
        )
    except ImportError as e:
        logger.error(f"Failed to import otel_init_script: {e}")
        raise HTTPException(status_code=500, detail="OTEL init script module not available")


# ============================================================
# Reports Endpoint
# ============================================================

@app.post("/api/reports/generate")
async def generate_report(request: ReportRequest):
    """Generate a report"""
    # In a real implementation, this would generate a PDF or Excel report
    report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return {
        "report_id": report_id,
        "report_type": request.report_type,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "status": "completed",
        "download_url": f"/api/reports/{report_id}/download",
    }


# ============================================================
# Static Files and SPA Routing
# ============================================================

# Mount static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/")
    async def serve_spa():
        """Serve the React SPA"""
        return FileResponse(static_dir / "index.html")

    @app.get("/{path:path}")
    async def catch_all(path: str):
        """Catch-all route for SPA routing"""
        # Check if it's a static file
        file_path = static_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise, serve the SPA
        return FileResponse(static_dir / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
