import pytest
from pydantic import ValidationError
from backend.app.schemas import AnalysisRequest
from backend.app.storage import Base


def test_schema_has_required_entities():
    assert len(Base.metadata.tables) == 11


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration_minutes", 59),
        ("duration_minutes", 481),
        ("search_horizon_minutes", 1441),
        ("start_utc", "2024-05-10T12:00:00"),
    ],
)
def test_boundaries(field, value):
    data = dict(
        mode="historical_review",
        start_utc="2024-05-10T12:00:00Z",
        duration_minutes=60,
        search_horizon_minutes=60,
    )
    data[field] = value
    with pytest.raises(ValidationError):
        AnalysisRequest(**data)
