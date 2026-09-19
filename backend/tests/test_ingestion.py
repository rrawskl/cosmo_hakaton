import httpx
import pytest
from uuid import uuid4
from backend.app import adapters
from backend.app.storage import Base, engine, Session, RawRecord
from sqlalchemy import select


@pytest.mark.parametrize("source", list(adapters.CATALOG))
def test_http_failure_is_recorded_without_secrets(source):
    Base.metadata.create_all(engine)
    adapters.init_sources()
    url = adapters.CATALOG[source]["url"] + "?test=" + str(uuid4())
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, text="outage", request=request)
    )
    with httpx.Client(transport=transport) as client:
        assert adapters.fetch(source, url, client=client) is None
    state = next(s for s in adapters.statuses() if s["id"] == source)
    assert state["status"] == "failed"
    assert state["error"] == "HTTPStatusError"


def test_freeze_preserves_raw_and_marks_stale():
    from pathlib import Path

    Base.metadata.create_all(engine)
    adapters.init_sources()
    url = "https://services.swpc.noaa.gov/text/3-day-forecast.txt?test=freeze"
    raw = adapters.store_response(
        "swpc_forecast", url, (Path(__file__).parent / "fixtures/storm.txt").read_text()
    )
    adapters.controls["swpc_forecast"] = "frozen"
    try:
        cached = adapters.fetch("swpc_forecast", url)
        assert cached["sha256"] == raw["sha256"] and cached["stale"]
    finally:
        adapters.controls.pop("swpc_forecast")


def test_ssrf_rejected():
    with pytest.raises(ValueError):
        adapters.fetch("ncei", "http://169.254.169.254/latest/meta-data/")


def test_raw_deduplicated_and_publication_preserved():
    from pathlib import Path

    Base.metadata.create_all(engine)
    adapters.init_sources()
    body = (Path(__file__).parent / "fixtures/storm.txt").read_text()
    url = "https://www.ngdc.noaa.gov/test-dedup"
    a = adapters.store_response("ncei", url, body)
    b = adapters.store_response("ncei", url, body)
    assert a["raw_id"] == b["raw_id"]
    assert a["published_at"] == "2024-05-10T12:30:00+00:00"
    with Session() as db:
        assert len(db.scalars(select(RawRecord).where(RawRecord.url == url)).all()) == 1
