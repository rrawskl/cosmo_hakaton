from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


def utc(value: str | datetime) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class AnalysisRequest(BaseModel):
    mode: Literal["current", "historical_replay", "historical_review"]
    start_utc: datetime
    duration_minutes: int = Field(ge=60, le=480, strict=True)
    search_horizon_minutes: int = Field(ge=0, le=1440, strict=True)
    cutoff_utc: datetime | None = None

    @field_validator("start_utc", "cutoff_utc")
    @classmethod
    def explicit_zone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Укажите часовой пояс; основной формат UTC")
        return value.astimezone(timezone.utc) if value else None

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode == "historical_replay":
            if self.cutoff_utc is None or self.cutoff_utc > self.start_utc:
                raise ValueError("Replay требует cutoff не позже начала окна")
        elif self.cutoff_utc is not None:
            raise ValueError("cutoff применяется только в strict replay")
        if self.mode != "current" and not (
            datetime(2024, 5, 1, tzinfo=timezone.utc)
            <= self.start_utc
            < datetime(2024, 7, 1, tzinfo=timezone.utc)
        ):
            raise ValueError("Проверенный исторический диапазон: май–июнь 2024 UTC")
        return self
