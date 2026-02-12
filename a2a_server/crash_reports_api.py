"""
Crash Report Ingestion API.

Receives crash reports from codetether-agent clients and stores them
in PostgreSQL for later analysis.

Endpoints:
    POST /v1/crash-reports  - Submit a crash report
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from .database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/crash-reports", tags=["Crash Reports"])

_TABLE_CREATED = False


# ============================================================================
# Request Model
# ============================================================================


class CrashReport(BaseModel):
    """Crash report payload sent by codetether-agent."""

    report_id: Optional[str] = Field(None, description="Client-generated report ID")
    version: Optional[str] = Field(None, description="Agent version")
    os: Optional[str] = Field(None, description="Operating system")
    arch: Optional[str] = Field(None, description="CPU architecture")
    timestamp: Optional[str] = Field(None, description="ISO-8601 timestamp")
    error: Optional[str] = Field(None, description="Error message / panic info")
    backtrace: Optional[str] = Field(None, description="Stack backtrace")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Additional context (command, provider, etc.)"
    )


# ============================================================================
# Schema
# ============================================================================


async def _ensure_table() -> bool:
    """Create crash_reports table if it doesn't exist. Returns True on success."""
    global _TABLE_CREATED
    if _TABLE_CREATED:
        return True

    pool = await get_pool()
    if pool is None:
        return False

    try:
        await pool.execute(
            """
            CREATE TABLE IF NOT EXISTS crash_reports (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                report_id   TEXT,
                version     TEXT,
                os          TEXT,
                arch        TEXT,
                error       TEXT,
                backtrace   TEXT,
                context     JSONB,
                client_ts   TIMESTAMPTZ,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_crash_reports_received
                ON crash_reports (received_at DESC);
            """
        )
        _TABLE_CREATED = True
        logger.info("crash_reports table ready")
        return True
    except Exception as e:
        logger.error(f"Failed to create crash_reports table: {e}")
        return False


# ============================================================================
# Endpoint
# ============================================================================


@router.post("", status_code=202)
async def submit_crash_report(report: CrashReport, request: Request):
    """Accept a crash report from the agent."""
    ok = await _ensure_table()
    if not ok:
        # Still accept — don't make the client retry forever.
        logger.warning("DB unavailable, crash report discarded")
        return {"status": "accepted", "persisted": False}

    pool = await get_pool()
    client_ts = None
    if report.timestamp:
        try:
            client_ts = datetime.fromisoformat(report.timestamp)
        except ValueError:
            pass

    try:
        import json as _json

        await pool.execute(
            """
            INSERT INTO crash_reports
                (report_id, version, os, arch, error, backtrace, context, client_ts)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
            """,
            report.report_id,
            report.version,
            report.os,
            report.arch,
            report.error,
            report.backtrace,
            _json.dumps(report.context) if report.context else None,
            client_ts,
        )
        logger.info(f"Crash report stored: {report.report_id}")
        return {"status": "accepted", "persisted": True}
    except Exception as e:
        logger.error(f"Failed to store crash report: {e}")
        return {"status": "accepted", "persisted": False}
