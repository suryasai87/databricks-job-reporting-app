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
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
WAREHOUSE_ID = os.getenv("WAREHOUSE_ID", "")
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "")


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


def execute_sql(query: str, warehouse_id: str = None) -> List[Dict]:
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
            wait_timeout="30s",
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
        workspace_id,
        job_id,
        run_id,
        job_name,
        start_time,
        end_time,
        TIMESTAMPDIFF(SECOND, start_time, COALESCE(end_time, current_timestamp())) as duration_seconds,
        result_state,
        termination_code,
        trigger_type,
        run_type,
        run_as,
        creator_user_name as creator_id
    FROM system.lakeflow.job_run_timeline
    WHERE start_time >= current_date() - INTERVAL {days} DAY
    ORDER BY start_time DESC
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
    WHERE start_time >= current_date() - INTERVAL {days} DAY
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
    WHERE start_time >= current_date() - INTERVAL {days} DAY
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
        DATE(start_time) as date,
        SUM(CASE WHEN result_state = 'SUCCESS' THEN 1 ELSE 0 END) as succeeded,
        SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) as failed
    FROM system.lakeflow.job_run_timeline
    WHERE start_time >= current_date() - INTERVAL {days} DAY
    GROUP BY DATE(start_time)
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


# ============================================================
# Cost Endpoints
# ============================================================

@app.get("/api/costs/summary")
async def get_cost_summary(days: int = 30):
    """Get cost summary from billing tables"""
    query = f"""
    SELECT
        COALESCE(SUM(usage_quantity * list_price), 0) as total_cost_usd,
        COALESCE(SUM(usage_quantity), 0) as total_dbus,
        COUNT(DISTINCT job_id) as unique_jobs,
        COUNT(*) as total_runs
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name
    WHERE usage_date >= current_date() - INTERVAL {days} DAY
        AND usage_metadata.job_id IS NOT NULL
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
        usage_date as date,
        SUM(usage_quantity * list_price) as cost_usd
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name
    WHERE usage_date >= current_date() - INTERVAL {days} DAY
    GROUP BY usage_date
    ORDER BY usage_date
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
        usage_metadata.job_id as job_id,
        FIRST(job_name) as job_name,
        SUM(usage_quantity * list_price) as total_cost,
        SUM(usage_quantity) as total_dbus,
        COUNT(*) as total_runs
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name
    LEFT JOIN system.lakeflow.jobs j ON u.usage_metadata.job_id = j.job_id
    WHERE usage_date >= current_date() - INTERVAL {days} DAY
        AND usage_metadata.job_id IS NOT NULL
    GROUP BY usage_metadata.job_id
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
        COALESCE(run_as, 'Unknown') as identity,
        SUM(usage_quantity * list_price) as cost_usd
    FROM system.billing.usage u
    LEFT JOIN system.billing.list_prices p ON u.sku_name = p.sku_name
    LEFT JOIN system.lakeflow.job_run_timeline j ON u.usage_metadata.run_id = j.run_id
    WHERE usage_date >= current_date() - INTERVAL {days} DAY
    GROUP BY COALESCE(run_as, 'Unknown')
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
    query = f"""
    SELECT
        job_id,
        job_name,
        COUNT(*) as total_runs,
        SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) as failed_runs,
        run_as,
        MAX(start_time) as last_run
    FROM system.lakeflow.job_run_timeline
    WHERE start_time >= current_date() - INTERVAL {days} DAY
    GROUP BY job_id, job_name, run_as
    HAVING SUM(CASE WHEN result_state IN ('FAILED', 'INTERNAL_ERROR') THEN 1 ELSE 0 END) > 0
    ORDER BY failed_runs DESC
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
    query = f"""
    WITH running_jobs AS (
        SELECT
            j.job_id,
            j.job_name,
            j.run_id,
            TIMESTAMPDIFF(MINUTE, j.start_time, current_timestamp()) as running_minutes
        FROM system.lakeflow.job_run_timeline j
        WHERE j.result_state IS NULL OR j.result_state = 'RUNNING'
    ),
    job_stats AS (
        SELECT
            job_id,
            AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) as avg_duration_minutes
        FROM system.lakeflow.job_run_timeline
        WHERE result_state = 'SUCCESS' AND end_time IS NOT NULL
        GROUP BY job_id
    )
    SELECT
        r.job_id,
        r.job_name,
        r.run_id,
        r.running_minutes,
        COALESCE(s.avg_duration_minutes, 30) as avg_duration_minutes,
        CASE
            WHEN r.running_minutes >= {critical_minutes} THEN 'CRITICAL'
            WHEN r.running_minutes >= {warning_minutes} THEN 'WARNING'
            WHEN r.running_minutes > COALESCE(s.avg_duration_minutes, 30) * 2 THEN 'ANOMALY'
            ELSE 'NORMAL'
        END as duration_status
    FROM running_jobs r
    LEFT JOIN job_stats s ON r.job_id = s.job_id
    WHERE r.running_minutes >= {warning_minutes}
       OR r.running_minutes > COALESCE(s.avg_duration_minutes, 30) * 2
    ORDER BY r.running_minutes DESC
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
    query = f"""
    WITH job_stats AS (
        SELECT
            job_id,
            job_name,
            AVG(TIMESTAMPDIFF(MINUTE, start_time, end_time)) as avg_duration,
            STDDEV(TIMESTAMPDIFF(MINUTE, start_time, end_time)) as std_duration
        FROM system.lakeflow.job_run_timeline
        WHERE result_state = 'SUCCESS' AND end_time IS NOT NULL
            AND start_time >= current_date() - INTERVAL 30 DAY
        GROUP BY job_id, job_name
        HAVING COUNT(*) >= 5
    ),
    recent_runs AS (
        SELECT
            j.job_id,
            j.job_name,
            j.run_id,
            TIMESTAMPDIFF(MINUTE, j.start_time, j.end_time) as duration
        FROM system.lakeflow.job_run_timeline j
        WHERE j.result_state = 'SUCCESS' AND j.end_time IS NOT NULL
            AND j.start_time >= current_date() - INTERVAL {days} DAY
    )
    SELECT
        r.job_id,
        r.job_name,
        r.run_id,
        'duration' as metric_name,
        r.duration as metric_value,
        s.avg_duration as expected_value,
        (r.duration - s.avg_duration) / NULLIF(s.std_duration, 0) as z_score
    FROM recent_runs r
    JOIN job_stats s ON r.job_id = s.job_id
    WHERE ABS((r.duration - s.avg_duration) / NULLIF(s.std_duration, 0)) >= {warning_threshold}
    ORDER BY ABS((r.duration - s.avg_duration) / NULLIF(s.std_duration, 0)) DESC
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
    """Get job retry statistics"""
    query = f"""
    SELECT
        job_id,
        job_name,
        SUM(CASE WHEN attempt_number > 1 THEN 1 ELSE 0 END) as runs_with_retries,
        SUM(attempt_number - 1) as total_retries,
        AVG(attempt_number) as avg_attempts_per_run
    FROM system.lakeflow.job_run_timeline
    WHERE start_time >= current_date() - INTERVAL {days} DAY
    GROUP BY job_id, job_name
    HAVING SUM(attempt_number - 1) > 0
    ORDER BY total_retries DESC
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
# Cluster Endpoints
# ============================================================

@app.get("/api/clusters/configs")
async def get_cluster_configs(job_id: Optional[str] = None, run_id: Optional[str] = None):
    """Get cluster configurations used by jobs"""
    where_clause = ""
    if job_id:
        where_clause = f"WHERE job_id = '{job_id}'"
    elif run_id:
        where_clause = f"WHERE run_id = '{run_id}'"

    query = f"""
    SELECT DISTINCT
        cluster_id,
        cluster_name,
        cluster_type,
        driver_node_type,
        worker_node_type,
        min_workers,
        max_workers,
        num_workers as fixed_workers,
        dbr_version
    FROM system.lakeflow.job_run_timeline
    {where_clause}
    LIMIT 100
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
async def get_overlaps(days: int = 7):
    """Detect overlapping job runs"""
    query = f"""
    WITH job_intervals AS (
        SELECT
            job_id,
            job_name,
            run_id,
            start_time,
            COALESCE(end_time, current_timestamp()) as end_time
        FROM system.lakeflow.job_run_timeline
        WHERE start_time >= current_date() - INTERVAL {days} DAY
    )
    SELECT
        a.job_name as job_a,
        b.job_name as job_b,
        a.run_id as run_a,
        b.run_id as run_b,
        TIMESTAMPDIFF(MINUTE,
            GREATEST(a.start_time, b.start_time),
            LEAST(a.end_time, b.end_time)
        ) as overlap_minutes
    FROM job_intervals a
    JOIN job_intervals b ON a.run_id < b.run_id
    WHERE a.start_time < b.end_time AND a.end_time > b.start_time
    ORDER BY overlap_minutes DESC
    LIMIT 50
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
