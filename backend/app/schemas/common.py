"""Common/shared Pydantic schemas used across the application."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaginatedResponse(BaseModel):
    """Generic pagination wrapper."""

    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=100, description="Items per page")
    total: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")


class HealthResponse(BaseModel):
    """Health check endpoint response."""

    status: str = Field(examples=["ok"])
    version: str
    timestamp: datetime


class JobStatusResponse(BaseModel):
    """Background job / task status response."""

    job_id: str
    status: str = Field(
        description="Current status of the job",
        examples=["pending", "running", "completed", "failed"],
    )
    progress: int | None = Field(
        default=None, ge=0, le=100, description="Progress percentage"
    )
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str = Field(description="Human-readable error description")
    error_code: str | None = Field(
        default=None, description="Machine-readable error code"
    )
