from datetime import date, datetime

from pydantic import BaseModel, Field


class SyncMasterRequest(BaseModel):
    force_full: bool = False


class SyncDailyRequest(BaseModel):
    symbols: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None


class SyncMinuteRequest(BaseModel):
    symbols: list[str] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class SyncRealtimeRequest(BaseModel):
    symbols: list[str] | None = None


class JobResponse(BaseModel):
    job_id: int
    job_type: str
    status: str
    result: dict = Field(default_factory=dict)
    error_message: str | None = None

