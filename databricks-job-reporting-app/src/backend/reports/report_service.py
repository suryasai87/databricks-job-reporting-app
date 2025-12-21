"""
Scheduled Reports Service for Databricks Jobs Monitor.

Provides PDF/HTML report generation, email delivery, and scheduling
for job monitoring reports.
"""

import os
import uuid
import logging
import smtplib
import tempfile
from io import BytesIO
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Any, Dict, List, Optional, Literal
from enum import Enum
from threading import Thread
import time
import schedule

from jinja2 import Environment, BaseLoader

# ReportLab imports for PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from data.data_layer import get_data_layer

logger = logging.getLogger(__name__)


class ReportSectionType(str, Enum):
    """Available report section types."""
    EXECUTIVE_SUMMARY = "executive_summary"
    FAILED_JOBS = "failed_jobs"
    COST_BREAKDOWN = "cost_breakdown"
    SLA_COMPLIANCE = "sla_compliance"
    TRENDING_ISSUES = "trending_issues"


class ReportFormat(str, Enum):
    """Supported report output formats."""
    PDF = "pdf"
    HTML = "html"


class ReportFrequency(str, Enum):
    """Report scheduling frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class ReportSection:
    """Configuration for a report section."""
    section_type: ReportSectionType
    enabled: bool = True
    title: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.title is None:
            self.title = self.section_type.value.replace("_", " ").title()


@dataclass
class ReportConfig:
    """Configuration for a scheduled report."""
    config_id: str
    name: str
    owner: str
    recipients: List[str]
    sections: List[ReportSection]
    format: ReportFormat = ReportFormat.PDF
    frequency: ReportFrequency = ReportFrequency.DAILY
    schedule_time: str = "08:00"  # HH:MM format
    timezone: str = "UTC"
    enabled: bool = True
    workspace_ids: List[str] = field(default_factory=list)
    job_filters: Dict[str, Any] = field(default_factory=dict)
    lookback_days: int = 7
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_run_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["sections"] = [
            {
                "section_type": s.section_type.value if isinstance(s.section_type, ReportSectionType) else s.section_type,
                "enabled": s.enabled,
                "title": s.title,
                "filters": s.filters,
            }
            for s in self.sections
        ]
        data["format"] = self.format.value if isinstance(self.format, ReportFormat) else self.format
        data["frequency"] = self.frequency.value if isinstance(self.frequency, ReportFrequency) else self.frequency
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        data["last_run_at"] = self.last_run_at.isoformat() if self.last_run_at else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReportConfig":
        """Create from dictionary."""
        sections = [
            ReportSection(
                section_type=ReportSectionType(s["section_type"]),
                enabled=s.get("enabled", True),
                title=s.get("title"),
                filters=s.get("filters", {}),
            )
            for s in data.get("sections", [])
        ]

        return cls(
            config_id=data["config_id"],
            name=data["name"],
            owner=data["owner"],
            recipients=data.get("recipients", []),
            sections=sections,
            format=ReportFormat(data.get("format", "pdf")),
            frequency=ReportFrequency(data.get("frequency", "daily")),
            schedule_time=data.get("schedule_time", "08:00"),
            timezone=data.get("timezone", "UTC"),
            enabled=data.get("enabled", True),
            workspace_ids=data.get("workspace_ids", []),
            job_filters=data.get("job_filters", {}),
            lookback_days=data.get("lookback_days", 7),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            last_run_at=datetime.fromisoformat(data["last_run_at"]) if data.get("last_run_at") else None,
        )


@dataclass
class GeneratedReport:
    """Represents a generated report instance."""
    report_id: str
    config_id: str
    format: ReportFormat
    file_path: str
    file_size_bytes: int
    generated_at: datetime
    generation_duration_seconds: float
    sections_included: List[str]
    status: Literal["success", "failed", "partial"] = "success"
    error_message: Optional[str] = None
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "report_id": self.report_id,
            "config_id": self.config_id,
            "format": self.format.value if isinstance(self.format, ReportFormat) else self.format,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "generated_at": self.generated_at.isoformat(),
            "generation_duration_seconds": self.generation_duration_seconds,
            "sections_included": self.sections_included,
            "status": self.status,
            "error_message": self.error_message,
            "email_sent": self.email_sent,
            "email_sent_at": self.email_sent_at.isoformat() if self.email_sent_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedReport":
        """Create from dictionary."""
        return cls(
            report_id=data["report_id"],
            config_id=data["config_id"],
            format=ReportFormat(data.get("format", "pdf")),
            file_path=data["file_path"],
            file_size_bytes=data.get("file_size_bytes", 0),
            generated_at=datetime.fromisoformat(data["generated_at"]),
            generation_duration_seconds=data.get("generation_duration_seconds", 0),
            sections_included=data.get("sections_included", []),
            status=data.get("status", "success"),
            error_message=data.get("error_message"),
            email_sent=data.get("email_sent", False),
            email_sent_at=datetime.fromisoformat(data["email_sent_at"]) if data.get("email_sent_at") else None,
        )


class ReportGenerator:
    """Generates PDF and HTML reports from job monitoring data."""

    # HTML template for reports
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{{ report_title }}</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .header {
                border-bottom: 3px solid #FF3621;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            .header h1 {
                color: #1B3139;
                margin: 0;
            }
            .header .subtitle {
                color: #666;
                margin-top: 5px;
            }
            .section {
                margin-bottom: 40px;
            }
            .section h2 {
                color: #1B3139;
                border-bottom: 2px solid #eee;
                padding-bottom: 10px;
            }
            .metric-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .metric-card {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
            }
            .metric-value {
                font-size: 32px;
                font-weight: bold;
                color: #1B3139;
            }
            .metric-label {
                color: #666;
                margin-top: 5px;
            }
            .metric-card.success .metric-value { color: #00A972; }
            .metric-card.warning .metric-value { color: #F2A900; }
            .metric-card.danger .metric-value { color: #FF3621; }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }
            th {
                background: #1B3139;
                color: white;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .status-badge {
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            .status-success { background: #d4edda; color: #155724; }
            .status-failed { background: #f8d7da; color: #721c24; }
            .status-warning { background: #fff3cd; color: #856404; }
            .footer {
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                text-align: center;
                color: #666;
                font-size: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{{ report_title }}</h1>
                <div class="subtitle">Generated on {{ generated_at }} | Period: {{ period_start }} to {{ period_end }}</div>
            </div>

            {% for section in sections %}
            <div class="section">
                {{ section.content | safe }}
            </div>
            {% endfor %}

            <div class="footer">
                <p>Databricks Jobs Monitor - Automated Report</p>
                <p>This report was automatically generated. Do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

    def __init__(self):
        """Initialize the report generator."""
        self.data_layer = get_data_layer()
        self.jinja_env = Environment(loader=BaseLoader())
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom PDF styles."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#1B3139'),
        ))
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#1B3139'),
        ))
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1B3139'),
        ))
        self.styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#666666'),
        ))

    def get_report_data(self, config: ReportConfig) -> Dict[str, Any]:
        """
        Fetch all data needed for report sections.

        Args:
            config: Report configuration

        Returns:
            Dictionary with data for each section type
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=config.lookback_days)

        data = {
            "period_start": start_date,
            "period_end": end_date,
            "config": config,
            "sections": {},
        }

        for section in config.sections:
            if not section.enabled:
                continue

            try:
                section_data = self._fetch_section_data(
                    section.section_type,
                    start_date,
                    end_date,
                    config.workspace_ids,
                    config.job_filters,
                    section.filters,
                )
                data["sections"][section.section_type.value] = section_data
            except Exception as e:
                logger.error(f"Error fetching data for section {section.section_type}: {e}")
                data["sections"][section.section_type.value] = {"error": str(e)}

        return data

    def _fetch_section_data(
        self,
        section_type: ReportSectionType,
        start_date: datetime,
        end_date: datetime,
        workspace_ids: List[str],
        job_filters: Dict[str, Any],
        section_filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch data for a specific section type."""

        if section_type == ReportSectionType.EXECUTIVE_SUMMARY:
            return self._fetch_executive_summary(start_date, end_date, workspace_ids)
        elif section_type == ReportSectionType.FAILED_JOBS:
            return self._fetch_failed_jobs(start_date, end_date, workspace_ids, job_filters)
        elif section_type == ReportSectionType.COST_BREAKDOWN:
            return self._fetch_cost_breakdown(start_date, end_date, workspace_ids)
        elif section_type == ReportSectionType.SLA_COMPLIANCE:
            return self._fetch_sla_compliance(start_date, end_date, workspace_ids)
        elif section_type == ReportSectionType.TRENDING_ISSUES:
            return self._fetch_trending_issues(start_date, end_date, workspace_ids)
        else:
            return {}

    def _fetch_executive_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        workspace_ids: List[str],
    ) -> Dict[str, Any]:
        """Fetch executive summary metrics."""
        query = """
        SELECT
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_runs,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_runs,
            SUM(CASE WHEN status = 'RUNNING' THEN 1 ELSE 0 END) as running_runs,
            AVG(duration_seconds) as avg_duration_seconds,
            SUM(estimated_dbu_cost) as total_dbu_cost,
            COUNT(DISTINCT job_id) as unique_jobs
        FROM jobs_monitor.core.job_runs
        WHERE start_time >= :start_date AND start_time <= :end_date
        """

        if workspace_ids:
            query += " AND workspace_id IN :workspace_ids"

        try:
            result = self.data_layer.execute_query(
                query,
                {"start_date": start_date, "end_date": end_date, "workspace_ids": tuple(workspace_ids) if workspace_ids else None}
            )

            if result and len(result) > 0:
                row = result[0]
                total = row.get("total_runs", 0) or 0
                successful = row.get("successful_runs", 0) or 0
                return {
                    "total_runs": total,
                    "successful_runs": successful,
                    "failed_runs": row.get("failed_runs", 0) or 0,
                    "running_runs": row.get("running_runs", 0) or 0,
                    "success_rate": (successful / total * 100) if total > 0 else 0,
                    "avg_duration_minutes": (row.get("avg_duration_seconds", 0) or 0) / 60,
                    "total_dbu_cost": row.get("total_dbu_cost", 0) or 0,
                    "unique_jobs": row.get("unique_jobs", 0) or 0,
                }
        except Exception as e:
            logger.error(f"Error fetching executive summary: {e}")

        return {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "running_runs": 0,
            "success_rate": 0,
            "avg_duration_minutes": 0,
            "total_dbu_cost": 0,
            "unique_jobs": 0,
        }

    def _fetch_failed_jobs(
        self,
        start_date: datetime,
        end_date: datetime,
        workspace_ids: List[str],
        job_filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch failed jobs details."""
        query = """
        SELECT
            job_id,
            job_name,
            run_id,
            start_time,
            end_time,
            error_message,
            workspace_id,
            cluster_type
        FROM jobs_monitor.core.job_runs
        WHERE status = 'FAILED'
            AND start_time >= :start_date
            AND start_time <= :end_date
        """

        if workspace_ids:
            query += " AND workspace_id IN :workspace_ids"

        query += " ORDER BY start_time DESC LIMIT 50"

        try:
            result = self.data_layer.execute_query(
                query,
                {"start_date": start_date, "end_date": end_date, "workspace_ids": tuple(workspace_ids) if workspace_ids else None}
            )

            # Group by job for failure counts
            job_failures = {}
            for row in result or []:
                job_id = row.get("job_id")
                if job_id not in job_failures:
                    job_failures[job_id] = {
                        "job_id": job_id,
                        "job_name": row.get("job_name", "Unknown"),
                        "failure_count": 0,
                        "recent_failures": [],
                    }
                job_failures[job_id]["failure_count"] += 1
                if len(job_failures[job_id]["recent_failures"]) < 5:
                    job_failures[job_id]["recent_failures"].append({
                        "run_id": row.get("run_id"),
                        "start_time": row.get("start_time"),
                        "error_message": row.get("error_message", "")[:200],
                    })

            return {
                "total_failures": len(result or []),
                "unique_failed_jobs": len(job_failures),
                "failed_jobs": sorted(
                    job_failures.values(),
                    key=lambda x: x["failure_count"],
                    reverse=True
                )[:20],
                "raw_failures": result or [],
            }
        except Exception as e:
            logger.error(f"Error fetching failed jobs: {e}")

        return {"total_failures": 0, "unique_failed_jobs": 0, "failed_jobs": [], "raw_failures": []}

    def _fetch_cost_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
        workspace_ids: List[str],
    ) -> Dict[str, Any]:
        """Fetch cost breakdown by various dimensions."""
        # Cost by workspace
        workspace_query = """
        SELECT
            workspace_id,
            SUM(estimated_dbu_cost) as total_cost,
            COUNT(*) as run_count
        FROM jobs_monitor.core.job_runs
        WHERE start_time >= :start_date AND start_time <= :end_date
        GROUP BY workspace_id
        ORDER BY total_cost DESC
        """

        # Cost by cluster type
        cluster_query = """
        SELECT
            cluster_type,
            SUM(estimated_dbu_cost) as total_cost,
            COUNT(*) as run_count
        FROM jobs_monitor.core.job_runs
        WHERE start_time >= :start_date AND start_time <= :end_date
        GROUP BY cluster_type
        ORDER BY total_cost DESC
        """

        # Top costly jobs
        top_jobs_query = """
        SELECT
            job_id,
            job_name,
            SUM(estimated_dbu_cost) as total_cost,
            COUNT(*) as run_count,
            AVG(duration_seconds) as avg_duration
        FROM jobs_monitor.core.job_runs
        WHERE start_time >= :start_date AND start_time <= :end_date
        GROUP BY job_id, job_name
        ORDER BY total_cost DESC
        LIMIT 10
        """

        try:
            params = {"start_date": start_date, "end_date": end_date}

            workspace_result = self.data_layer.execute_query(workspace_query, params) or []
            cluster_result = self.data_layer.execute_query(cluster_query, params) or []
            top_jobs_result = self.data_layer.execute_query(top_jobs_query, params) or []

            total_cost = sum(row.get("total_cost", 0) or 0 for row in workspace_result)

            return {
                "total_cost": total_cost,
                "by_workspace": workspace_result,
                "by_cluster_type": cluster_result,
                "top_costly_jobs": top_jobs_result,
            }
        except Exception as e:
            logger.error(f"Error fetching cost breakdown: {e}")

        return {"total_cost": 0, "by_workspace": [], "by_cluster_type": [], "top_costly_jobs": []}

    def _fetch_sla_compliance(
        self,
        start_date: datetime,
        end_date: datetime,
        workspace_ids: List[str],
    ) -> Dict[str, Any]:
        """Fetch SLA compliance metrics."""
        query = """
        SELECT
            jr.job_id,
            jr.job_name,
            COUNT(*) as total_runs,
            SUM(CASE WHEN jr.status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_runs,
            SUM(CASE WHEN jr.duration_seconds <= sc.max_duration_seconds THEN 1 ELSE 0 END) as within_sla,
            AVG(jr.duration_seconds) as avg_duration,
            sc.max_duration_seconds as sla_threshold
        FROM jobs_monitor.core.job_runs jr
        LEFT JOIN jobs_monitor.config.sla_configs sc ON jr.job_id = sc.job_id
        WHERE jr.start_time >= :start_date AND jr.start_time <= :end_date
        GROUP BY jr.job_id, jr.job_name, sc.max_duration_seconds
        HAVING sc.max_duration_seconds IS NOT NULL
        ORDER BY (SUM(CASE WHEN jr.duration_seconds <= sc.max_duration_seconds THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) ASC
        LIMIT 20
        """

        try:
            result = self.data_layer.execute_query(
                query,
                {"start_date": start_date, "end_date": end_date}
            )

            jobs_with_sla = []
            total_compliant = 0
            total_runs = 0

            for row in result or []:
                runs = row.get("total_runs", 0) or 0
                within_sla = row.get("within_sla", 0) or 0
                compliance_rate = (within_sla / runs * 100) if runs > 0 else 0

                total_runs += runs
                total_compliant += within_sla

                jobs_with_sla.append({
                    "job_id": row.get("job_id"),
                    "job_name": row.get("job_name"),
                    "total_runs": runs,
                    "within_sla": within_sla,
                    "compliance_rate": compliance_rate,
                    "avg_duration": row.get("avg_duration", 0) or 0,
                    "sla_threshold": row.get("sla_threshold", 0) or 0,
                })

            overall_compliance = (total_compliant / total_runs * 100) if total_runs > 0 else 100

            return {
                "overall_compliance_rate": overall_compliance,
                "total_sla_jobs": len(jobs_with_sla),
                "jobs_below_threshold": [j for j in jobs_with_sla if j["compliance_rate"] < 95],
                "all_jobs": jobs_with_sla,
            }
        except Exception as e:
            logger.error(f"Error fetching SLA compliance: {e}")

        return {
            "overall_compliance_rate": 100,
            "total_sla_jobs": 0,
            "jobs_below_threshold": [],
            "all_jobs": [],
        }

    def _fetch_trending_issues(
        self,
        start_date: datetime,
        end_date: datetime,
        workspace_ids: List[str],
    ) -> Dict[str, Any]:
        """Fetch trending issues and patterns."""
        # Error pattern analysis
        error_query = """
        SELECT
            SUBSTRING(error_message, 1, 100) as error_pattern,
            COUNT(*) as occurrence_count,
            COUNT(DISTINCT job_id) as affected_jobs
        FROM jobs_monitor.core.job_runs
        WHERE status = 'FAILED'
            AND start_time >= :start_date
            AND start_time <= :end_date
            AND error_message IS NOT NULL
        GROUP BY SUBSTRING(error_message, 1, 100)
        ORDER BY occurrence_count DESC
        LIMIT 10
        """

        # Jobs with increasing failure rate
        trend_query = """
        WITH daily_stats AS (
            SELECT
                job_id,
                job_name,
                DATE(start_time) as run_date,
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_runs
            FROM jobs_monitor.core.job_runs
            WHERE start_time >= :start_date AND start_time <= :end_date
            GROUP BY job_id, job_name, DATE(start_time)
        )
        SELECT
            job_id,
            job_name,
            AVG(failed_runs * 1.0 / NULLIF(total_runs, 0)) as avg_failure_rate,
            SUM(failed_runs) as total_failures,
            SUM(total_runs) as total_runs
        FROM daily_stats
        GROUP BY job_id, job_name
        HAVING SUM(failed_runs) >= 3
        ORDER BY avg_failure_rate DESC
        LIMIT 10
        """

        try:
            params = {"start_date": start_date, "end_date": end_date}

            error_result = self.data_layer.execute_query(error_query, params) or []
            trend_result = self.data_layer.execute_query(trend_query, params) or []

            return {
                "common_errors": [
                    {
                        "pattern": row.get("error_pattern", ""),
                        "count": row.get("occurrence_count", 0),
                        "affected_jobs": row.get("affected_jobs", 0),
                    }
                    for row in error_result
                ],
                "problematic_jobs": [
                    {
                        "job_id": row.get("job_id"),
                        "job_name": row.get("job_name"),
                        "failure_rate": (row.get("avg_failure_rate", 0) or 0) * 100,
                        "total_failures": row.get("total_failures", 0),
                        "total_runs": row.get("total_runs", 0),
                    }
                    for row in trend_result
                ],
            }
        except Exception as e:
            logger.error(f"Error fetching trending issues: {e}")

        return {"common_errors": [], "problematic_jobs": []}

    def generate_pdf(self, config: ReportConfig, data: Dict[str, Any]) -> str:
        """
        Generate a PDF report.

        Args:
            config: Report configuration
            data: Report data from get_report_data()

        Returns:
            Path to the generated PDF file
        """
        # Create temp file for PDF
        fd, file_path = tempfile.mkstemp(suffix=".pdf", prefix=f"report_{config.config_id}_")
        os.close(fd)

        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
        )

        story = []

        # Title
        story.append(Paragraph(config.name, self.styles['ReportTitle']))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | "
            f"Period: {data['period_start'].strftime('%Y-%m-%d')} to {data['period_end'].strftime('%Y-%m-%d')}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 20))

        # Generate each section
        for section in config.sections:
            if not section.enabled:
                continue

            section_data = data["sections"].get(section.section_type.value, {})
            section_content = self._generate_pdf_section(section, section_data)
            story.extend(section_content)
            story.append(Spacer(1, 20))

        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph(
            "Databricks Jobs Monitor - Automated Report",
            ParagraphStyle(name='Footer', parent=self.styles['Normal'], alignment=TA_CENTER, textColor=colors.gray)
        ))

        doc.build(story)

        return file_path

    def _generate_pdf_section(
        self,
        section: ReportSection,
        data: Dict[str, Any],
    ) -> List:
        """Generate PDF content for a section."""
        content = []

        content.append(Paragraph(section.title, self.styles['SectionTitle']))

        if "error" in data:
            content.append(Paragraph(f"Error loading section: {data['error']}", self.styles['Normal']))
            return content

        if section.section_type == ReportSectionType.EXECUTIVE_SUMMARY:
            content.extend(self._pdf_executive_summary(data))
        elif section.section_type == ReportSectionType.FAILED_JOBS:
            content.extend(self._pdf_failed_jobs(data))
        elif section.section_type == ReportSectionType.COST_BREAKDOWN:
            content.extend(self._pdf_cost_breakdown(data))
        elif section.section_type == ReportSectionType.SLA_COMPLIANCE:
            content.extend(self._pdf_sla_compliance(data))
        elif section.section_type == ReportSectionType.TRENDING_ISSUES:
            content.extend(self._pdf_trending_issues(data))

        return content

    def _pdf_executive_summary(self, data: Dict[str, Any]) -> List:
        """Generate executive summary PDF content."""
        content = []

        # Metrics table
        metrics_data = [
            ["Total Runs", "Success Rate", "Failed Runs", "Avg Duration", "Total Cost"],
            [
                str(data.get("total_runs", 0)),
                f"{data.get('success_rate', 0):.1f}%",
                str(data.get("failed_runs", 0)),
                f"{data.get('avg_duration_minutes', 0):.1f} min",
                f"${data.get('total_dbu_cost', 0):.2f}",
            ]
        ]

        table = Table(metrics_data, colWidths=[1.4*inch]*5)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3139')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 1), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 15),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ]))
        content.append(table)

        return content

    def _pdf_failed_jobs(self, data: Dict[str, Any]) -> List:
        """Generate failed jobs PDF content."""
        content = []

        content.append(Paragraph(
            f"Total Failures: {data.get('total_failures', 0)} | Unique Failed Jobs: {data.get('unique_failed_jobs', 0)}",
            self.styles['Normal']
        ))
        content.append(Spacer(1, 10))

        failed_jobs = data.get("failed_jobs", [])[:10]
        if failed_jobs:
            table_data = [["Job Name", "Failure Count", "Last Error"]]
            for job in failed_jobs:
                recent = job.get("recent_failures", [{}])
                last_error = recent[0].get("error_message", "N/A")[:50] if recent else "N/A"
                table_data.append([
                    job.get("job_name", "Unknown")[:30],
                    str(job.get("failure_count", 0)),
                    last_error + "..." if len(last_error) == 50 else last_error,
                ])

            table = Table(table_data, colWidths=[2.5*inch, 1*inch, 3.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3139')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            content.append(table)
        else:
            content.append(Paragraph("No failed jobs in this period.", self.styles['Normal']))

        return content

    def _pdf_cost_breakdown(self, data: Dict[str, Any]) -> List:
        """Generate cost breakdown PDF content."""
        content = []

        content.append(Paragraph(
            f"Total Cost: ${data.get('total_cost', 0):.2f}",
            self.styles['Normal']
        ))
        content.append(Spacer(1, 10))

        # Top costly jobs
        top_jobs = data.get("top_costly_jobs", [])[:10]
        if top_jobs:
            content.append(Paragraph("Top 10 Costly Jobs", self.styles['Normal']))
            table_data = [["Job Name", "Total Cost", "Run Count", "Avg Duration"]]
            for job in top_jobs:
                table_data.append([
                    str(job.get("job_name", "Unknown"))[:30],
                    f"${job.get('total_cost', 0):.2f}",
                    str(job.get("run_count", 0)),
                    f"{(job.get('avg_duration', 0) or 0) / 60:.1f} min",
                ])

            table = Table(table_data, colWidths=[3*inch, 1.2*inch, 1*inch, 1.3*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3139')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            content.append(table)

        return content

    def _pdf_sla_compliance(self, data: Dict[str, Any]) -> List:
        """Generate SLA compliance PDF content."""
        content = []

        compliance_rate = data.get("overall_compliance_rate", 100)
        content.append(Paragraph(
            f"Overall SLA Compliance: {compliance_rate:.1f}%",
            self.styles['Normal']
        ))
        content.append(Spacer(1, 10))

        # Jobs below threshold
        below_threshold = data.get("jobs_below_threshold", [])[:10]
        if below_threshold:
            content.append(Paragraph("Jobs Below 95% SLA Compliance", self.styles['Normal']))
            table_data = [["Job Name", "Compliance", "Runs", "Avg Duration", "SLA Threshold"]]
            for job in below_threshold:
                table_data.append([
                    str(job.get("job_name", "Unknown"))[:25],
                    f"{job.get('compliance_rate', 0):.1f}%",
                    str(job.get("total_runs", 0)),
                    f"{job.get('avg_duration', 0) / 60:.1f} min",
                    f"{job.get('sla_threshold', 0) / 60:.1f} min",
                ])

            table = Table(table_data, colWidths=[2.2*inch, 1*inch, 0.8*inch, 1.2*inch, 1.3*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3139')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            content.append(table)
        else:
            content.append(Paragraph("All jobs are meeting SLA targets.", self.styles['Normal']))

        return content

    def _pdf_trending_issues(self, data: Dict[str, Any]) -> List:
        """Generate trending issues PDF content."""
        content = []

        # Common errors
        common_errors = data.get("common_errors", [])[:5]
        if common_errors:
            content.append(Paragraph("Common Error Patterns", self.styles['Normal']))
            table_data = [["Error Pattern", "Count", "Affected Jobs"]]
            for error in common_errors:
                table_data.append([
                    str(error.get("pattern", ""))[:60] + "...",
                    str(error.get("count", 0)),
                    str(error.get("affected_jobs", 0)),
                ])

            table = Table(table_data, colWidths=[4.5*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3139')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ]))
            content.append(table)
            content.append(Spacer(1, 15))

        # Problematic jobs
        problematic = data.get("problematic_jobs", [])[:5]
        if problematic:
            content.append(Paragraph("Jobs with High Failure Rates", self.styles['Normal']))
            table_data = [["Job Name", "Failure Rate", "Total Failures", "Total Runs"]]
            for job in problematic:
                table_data.append([
                    str(job.get("job_name", "Unknown"))[:30],
                    f"{job.get('failure_rate', 0):.1f}%",
                    str(job.get("total_failures", 0)),
                    str(job.get("total_runs", 0)),
                ])

            table = Table(table_data, colWidths=[3*inch, 1.2*inch, 1.2*inch, 1.1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3139')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ]))
            content.append(table)

        if not common_errors and not problematic:
            content.append(Paragraph("No significant trending issues detected.", self.styles['Normal']))

        return content

    def generate_html(self, config: ReportConfig, data: Dict[str, Any]) -> str:
        """
        Generate an HTML report.

        Args:
            config: Report configuration
            data: Report data from get_report_data()

        Returns:
            Path to the generated HTML file
        """
        # Create temp file for HTML
        fd, file_path = tempfile.mkstemp(suffix=".html", prefix=f"report_{config.config_id}_")
        os.close(fd)

        sections = []
        for section in config.sections:
            if not section.enabled:
                continue

            section_data = data["sections"].get(section.section_type.value, {})
            section_html = self._generate_html_section(section, section_data)
            sections.append({"title": section.title, "content": section_html})

        template = self.jinja_env.from_string(self.HTML_TEMPLATE)
        html_content = template.render(
            report_title=config.name,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            period_start=data["period_start"].strftime("%Y-%m-%d"),
            period_end=data["period_end"].strftime("%Y-%m-%d"),
            sections=sections,
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return file_path

    def _generate_html_section(
        self,
        section: ReportSection,
        data: Dict[str, Any],
    ) -> str:
        """Generate HTML content for a section."""
        if "error" in data:
            return f"<p class='error'>Error loading section: {data['error']}</p>"

        if section.section_type == ReportSectionType.EXECUTIVE_SUMMARY:
            return self._html_executive_summary(data)
        elif section.section_type == ReportSectionType.FAILED_JOBS:
            return self._html_failed_jobs(data)
        elif section.section_type == ReportSectionType.COST_BREAKDOWN:
            return self._html_cost_breakdown(data)
        elif section.section_type == ReportSectionType.SLA_COMPLIANCE:
            return self._html_sla_compliance(data)
        elif section.section_type == ReportSectionType.TRENDING_ISSUES:
            return self._html_trending_issues(data)

        return ""

    def _html_executive_summary(self, data: Dict[str, Any]) -> str:
        """Generate executive summary HTML."""
        success_rate = data.get("success_rate", 0)
        rate_class = "success" if success_rate >= 95 else "warning" if success_rate >= 80 else "danger"

        return f"""
        <h2>Executive Summary</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{data.get('total_runs', 0):,}</div>
                <div class="metric-label">Total Runs</div>
            </div>
            <div class="metric-card {rate_class}">
                <div class="metric-value">{success_rate:.1f}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card danger">
                <div class="metric-value">{data.get('failed_runs', 0):,}</div>
                <div class="metric-label">Failed Runs</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{data.get('avg_duration_minutes', 0):.1f}</div>
                <div class="metric-label">Avg Duration (min)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${data.get('total_dbu_cost', 0):,.2f}</div>
                <div class="metric-label">Total Cost</div>
            </div>
        </div>
        """

    def _html_failed_jobs(self, data: Dict[str, Any]) -> str:
        """Generate failed jobs HTML."""
        html = f"""
        <h2>Failed Jobs</h2>
        <p>Total Failures: {data.get('total_failures', 0)} | Unique Failed Jobs: {data.get('unique_failed_jobs', 0)}</p>
        """

        failed_jobs = data.get("failed_jobs", [])[:10]
        if failed_jobs:
            html += """
            <table>
                <thead>
                    <tr><th>Job Name</th><th>Failure Count</th><th>Last Error</th></tr>
                </thead>
                <tbody>
            """
            for job in failed_jobs:
                recent = job.get("recent_failures", [{}])
                last_error = recent[0].get("error_message", "N/A")[:100] if recent else "N/A"
                html += f"""
                <tr>
                    <td>{job.get('job_name', 'Unknown')}</td>
                    <td><span class="status-badge status-failed">{job.get('failure_count', 0)}</span></td>
                    <td>{last_error}</td>
                </tr>
                """
            html += "</tbody></table>"
        else:
            html += "<p>No failed jobs in this period.</p>"

        return html

    def _html_cost_breakdown(self, data: Dict[str, Any]) -> str:
        """Generate cost breakdown HTML."""
        html = f"""
        <h2>Cost Breakdown</h2>
        <p><strong>Total Cost:</strong> ${data.get('total_cost', 0):,.2f}</p>
        """

        top_jobs = data.get("top_costly_jobs", [])[:10]
        if top_jobs:
            html += """
            <h3>Top 10 Costly Jobs</h3>
            <table>
                <thead>
                    <tr><th>Job Name</th><th>Total Cost</th><th>Run Count</th><th>Avg Duration</th></tr>
                </thead>
                <tbody>
            """
            for job in top_jobs:
                html += f"""
                <tr>
                    <td>{job.get('job_name', 'Unknown')}</td>
                    <td>${job.get('total_cost', 0):.2f}</td>
                    <td>{job.get('run_count', 0)}</td>
                    <td>{(job.get('avg_duration', 0) or 0) / 60:.1f} min</td>
                </tr>
                """
            html += "</tbody></table>"

        return html

    def _html_sla_compliance(self, data: Dict[str, Any]) -> str:
        """Generate SLA compliance HTML."""
        compliance = data.get("overall_compliance_rate", 100)
        compliance_class = "success" if compliance >= 95 else "warning" if compliance >= 80 else "danger"

        html = f"""
        <h2>SLA Compliance</h2>
        <div class="metric-card {compliance_class}" style="max-width: 200px;">
            <div class="metric-value">{compliance:.1f}%</div>
            <div class="metric-label">Overall Compliance</div>
        </div>
        """

        below_threshold = data.get("jobs_below_threshold", [])[:10]
        if below_threshold:
            html += """
            <h3>Jobs Below 95% SLA Compliance</h3>
            <table>
                <thead>
                    <tr><th>Job Name</th><th>Compliance</th><th>Runs</th><th>Avg Duration</th><th>SLA Threshold</th></tr>
                </thead>
                <tbody>
            """
            for job in below_threshold:
                rate = job.get("compliance_rate", 0)
                rate_class = "success" if rate >= 95 else "warning" if rate >= 80 else "failed"
                html += f"""
                <tr>
                    <td>{job.get('job_name', 'Unknown')}</td>
                    <td><span class="status-badge status-{rate_class}">{rate:.1f}%</span></td>
                    <td>{job.get('total_runs', 0)}</td>
                    <td>{job.get('avg_duration', 0) / 60:.1f} min</td>
                    <td>{job.get('sla_threshold', 0) / 60:.1f} min</td>
                </tr>
                """
            html += "</tbody></table>"
        else:
            html += "<p>All jobs are meeting SLA targets.</p>"

        return html

    def _html_trending_issues(self, data: Dict[str, Any]) -> str:
        """Generate trending issues HTML."""
        html = "<h2>Trending Issues</h2>"

        common_errors = data.get("common_errors", [])[:5]
        if common_errors:
            html += """
            <h3>Common Error Patterns</h3>
            <table>
                <thead>
                    <tr><th>Error Pattern</th><th>Count</th><th>Affected Jobs</th></tr>
                </thead>
                <tbody>
            """
            for error in common_errors:
                html += f"""
                <tr>
                    <td>{error.get('pattern', '')[:80]}...</td>
                    <td>{error.get('count', 0)}</td>
                    <td>{error.get('affected_jobs', 0)}</td>
                </tr>
                """
            html += "</tbody></table>"

        problematic = data.get("problematic_jobs", [])[:5]
        if problematic:
            html += """
            <h3>Jobs with High Failure Rates</h3>
            <table>
                <thead>
                    <tr><th>Job Name</th><th>Failure Rate</th><th>Total Failures</th><th>Total Runs</th></tr>
                </thead>
                <tbody>
            """
            for job in problematic:
                html += f"""
                <tr>
                    <td>{job.get('job_name', 'Unknown')}</td>
                    <td><span class="status-badge status-failed">{job.get('failure_rate', 0):.1f}%</span></td>
                    <td>{job.get('total_failures', 0)}</td>
                    <td>{job.get('total_runs', 0)}</td>
                </tr>
                """
            html += "</tbody></table>"

        if not common_errors and not problematic:
            html += "<p>No significant trending issues detected.</p>"

        return html


class EmailService:
    """Handles email delivery of reports."""

    def __init__(self):
        """Initialize email service with SMTP configuration."""
        self.smtp_host = os.environ.get("SMTP_HOST", "localhost")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
        self.from_email = os.environ.get("SMTP_FROM_EMAIL", "noreply@databricks-jobs-monitor.local")
        self.from_name = os.environ.get("SMTP_FROM_NAME", "Databricks Jobs Monitor")

    def send_report(
        self,
        recipients: List[str],
        report_path: str,
        config: ReportConfig,
    ) -> bool:
        """
        Send a report via email.

        Args:
            recipients: List of email addresses
            report_path: Path to the report file
            config: Report configuration

        Returns:
            True if email sent successfully, False otherwise
        """
        if not recipients:
            logger.warning("No recipients specified for report email")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"[Jobs Monitor] {config.name} - {datetime.utcnow().strftime('%Y-%m-%d')}"

            # Email body
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Databricks Jobs Monitor Report</h2>
                <p>Please find attached the scheduled report: <strong>{config.name}</strong></p>
                <p>
                    <strong>Report Period:</strong> Last {config.lookback_days} days<br>
                    <strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
                </p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    This is an automated email from Databricks Jobs Monitor.
                    Please do not reply to this message.
                </p>
            </body>
            </html>
            """
            msg.attach(MIMEText(body, "html"))

            # Attach report file
            with open(report_path, "rb") as f:
                file_data = f.read()

            file_ext = os.path.splitext(report_path)[1]
            filename = f"{config.name.replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}{file_ext}"

            attachment = MIMEApplication(file_data)
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename,
            )
            msg.attach(attachment)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Report email sent successfully to {len(recipients)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send report email: {e}")
            return False


class ReportService:
    """Main service for managing scheduled reports."""

    CONFIGS_TABLE = "jobs_monitor.reports.report_configs"
    HISTORY_TABLE = "jobs_monitor.reports.report_history"

    def __init__(self):
        """Initialize the report service."""
        self.data_layer = get_data_layer()
        self.generator = ReportGenerator()
        self.email_service = EmailService()

    def create_report_config(self, config: ReportConfig) -> ReportConfig:
        """
        Create a new scheduled report configuration.

        Args:
            config: Report configuration to create

        Returns:
            Created report configuration
        """
        if not config.config_id:
            config.config_id = str(uuid.uuid4())

        config.created_at = datetime.utcnow()
        config.updated_at = datetime.utcnow()

        self.data_layer.insert_record(
            self.CONFIGS_TABLE,
            config.to_dict(),
        )

        logger.info(f"Created report config: {config.config_id}")
        return config

    def update_report_config(self, config: ReportConfig) -> ReportConfig:
        """
        Update an existing report configuration.

        Args:
            config: Report configuration to update

        Returns:
            Updated report configuration
        """
        config.updated_at = datetime.utcnow()

        self.data_layer.update_record(
            self.CONFIGS_TABLE,
            {"config_id": config.config_id},
            config.to_dict(),
        )

        logger.info(f"Updated report config: {config.config_id}")
        return config

    def delete_report_config(self, config_id: str) -> bool:
        """
        Delete a report configuration.

        Args:
            config_id: ID of the configuration to delete

        Returns:
            True if deleted successfully
        """
        self.data_layer.delete_record(
            self.CONFIGS_TABLE,
            {"config_id": config_id},
        )

        logger.info(f"Deleted report config: {config_id}")
        return True

    def get_report_config(self, config_id: str) -> Optional[ReportConfig]:
        """
        Get a report configuration by ID.

        Args:
            config_id: Configuration ID

        Returns:
            Report configuration or None if not found
        """
        result = self.data_layer.execute_query(
            f"SELECT * FROM {self.CONFIGS_TABLE} WHERE config_id = :config_id",
            {"config_id": config_id},
        )

        if result and len(result) > 0:
            return ReportConfig.from_dict(result[0])
        return None

    def get_report_configs(self, owner: Optional[str] = None) -> List[ReportConfig]:
        """
        Get all report configurations, optionally filtered by owner.

        Args:
            owner: Optional owner to filter by

        Returns:
            List of report configurations
        """
        query = f"SELECT * FROM {self.CONFIGS_TABLE}"
        params = {}

        if owner:
            query += " WHERE owner = :owner"
            params["owner"] = owner

        query += " ORDER BY created_at DESC"

        result = self.data_layer.execute_query(query, params)

        return [ReportConfig.from_dict(row) for row in (result or [])]

    def generate_report(self, config_id: str) -> GeneratedReport:
        """
        Manually trigger report generation.

        Args:
            config_id: ID of the report configuration

        Returns:
            Generated report metadata
        """
        config = self.get_report_config(config_id)
        if not config:
            raise ValueError(f"Report config not found: {config_id}")

        start_time = datetime.utcnow()
        report_id = str(uuid.uuid4())

        try:
            # Get report data
            data = self.generator.get_report_data(config)

            # Generate report file
            if config.format == ReportFormat.PDF:
                file_path = self.generator.generate_pdf(config, data)
            else:
                file_path = self.generator.generate_html(config, data)

            # Get file size
            file_size = os.path.getsize(file_path)

            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Create report record
            generated_report = GeneratedReport(
                report_id=report_id,
                config_id=config_id,
                format=config.format,
                file_path=file_path,
                file_size_bytes=file_size,
                generated_at=datetime.utcnow(),
                generation_duration_seconds=duration,
                sections_included=[s.section_type.value for s in config.sections if s.enabled],
                status="success",
            )

            # Send email if recipients configured
            if config.recipients:
                email_sent = self.email_service.send_report(
                    config.recipients,
                    file_path,
                    config,
                )
                generated_report.email_sent = email_sent
                if email_sent:
                    generated_report.email_sent_at = datetime.utcnow()

            # Save to history
            self._save_report_history(generated_report)

            # Update last run time
            config.last_run_at = datetime.utcnow()
            self.update_report_config(config)

            logger.info(f"Generated report {report_id} for config {config_id}")
            return generated_report

        except Exception as e:
            logger.error(f"Error generating report for config {config_id}: {e}")

            # Create failed report record
            generated_report = GeneratedReport(
                report_id=report_id,
                config_id=config_id,
                format=config.format,
                file_path="",
                file_size_bytes=0,
                generated_at=datetime.utcnow(),
                generation_duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                sections_included=[],
                status="failed",
                error_message=str(e),
            )

            self._save_report_history(generated_report)
            return generated_report

    def _save_report_history(self, report: GeneratedReport) -> None:
        """Save generated report to history table."""
        self.data_layer.insert_record(
            self.HISTORY_TABLE,
            report.to_dict(),
        )

    def get_report_history(
        self,
        config_id: str,
        limit: int = 10,
    ) -> List[GeneratedReport]:
        """
        Get report generation history for a configuration.

        Args:
            config_id: Configuration ID
            limit: Maximum number of records to return

        Returns:
            List of generated report records
        """
        result = self.data_layer.execute_query(
            f"""
            SELECT * FROM {self.HISTORY_TABLE}
            WHERE config_id = :config_id
            ORDER BY generated_at DESC
            LIMIT :limit
            """,
            {"config_id": config_id, "limit": limit},
        )

        return [GeneratedReport.from_dict(row) for row in (result or [])]

    def get_report_file(self, report_id: str) -> Optional[str]:
        """
        Get the file path for a generated report.

        Args:
            report_id: Report ID

        Returns:
            File path or None if not found
        """
        result = self.data_layer.execute_query(
            f"SELECT file_path FROM {self.HISTORY_TABLE} WHERE report_id = :report_id",
            {"report_id": report_id},
        )

        if result and len(result) > 0:
            file_path = result[0].get("file_path")
            if file_path and os.path.exists(file_path):
                return file_path
        return None


class ReportScheduler:
    """Handles scheduling of report generation."""

    def __init__(self, report_service: Optional[ReportService] = None):
        """Initialize the scheduler."""
        self.report_service = report_service or ReportService()
        self._running = False
        self._thread: Optional[Thread] = None

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._thread = Thread(target=self._run_scheduler, daemon=True)
        self._thread.start()
        logger.info("Report scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        schedule.clear()
        logger.info("Report scheduler stopped")

    def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        self._schedule_all_reports()

        while self._running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def _schedule_all_reports(self) -> None:
        """Load and schedule all enabled report configurations."""
        schedule.clear()

        configs = self.report_service.get_report_configs()
        for config in configs:
            if config.enabled:
                self._schedule_report(config)

    def _schedule_report(self, config: ReportConfig) -> None:
        """Schedule a single report configuration."""
        job_tag = f"report_{config.config_id}"

        # Clear existing schedule for this config
        schedule.clear(job_tag)

        # Schedule based on frequency
        if config.frequency == ReportFrequency.DAILY:
            schedule.every().day.at(config.schedule_time).do(
                self._run_report, config.config_id
            ).tag(job_tag)
        elif config.frequency == ReportFrequency.WEEKLY:
            schedule.every().monday.at(config.schedule_time).do(
                self._run_report, config.config_id
            ).tag(job_tag)
        elif config.frequency == ReportFrequency.MONTHLY:
            # Run on the 1st of each month
            schedule.every().day.at(config.schedule_time).do(
                self._run_monthly_report, config.config_id
            ).tag(job_tag)

        logger.info(f"Scheduled report {config.config_id}: {config.frequency.value} at {config.schedule_time}")

    def _run_report(self, config_id: str) -> None:
        """Execute a scheduled report generation."""
        try:
            logger.info(f"Running scheduled report: {config_id}")
            self.report_service.generate_report(config_id)
        except Exception as e:
            logger.error(f"Error running scheduled report {config_id}: {e}")

    def _run_monthly_report(self, config_id: str) -> None:
        """Execute monthly report (only on the 1st)."""
        if datetime.utcnow().day == 1:
            self._run_report(config_id)

    def refresh_schedules(self) -> None:
        """Reload all report schedules from the database."""
        self._schedule_all_reports()
        logger.info("Report schedules refreshed")
