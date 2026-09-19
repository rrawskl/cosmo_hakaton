import os

os.environ["AUTO_REFRESH"] = "false"
from pathlib import Path
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from backend.app.api import app
from backend.app import adapters
from backend.app.parsers import parse_forecast
from backend.app.storage import Base, engine

FIX = Path(__file__).parent / "fixtures"


def test_future_issued_forecast_cannot_cover_window(client, monkeypatch):
    from backend.app import analysis, protons

    monkeypatch.setattr(analysis, "now", lambda: "2024-05-10T12:29:00Z")
    forecast = adapters.store_response(
        "swpc_forecast",
        adapters.CATALOG["swpc_forecast"]["url"],
        (FIX / "storm.txt").read_text(),
    )
    monkeypatch.setattr(
        adapters,
        "current_sources",
        lambda: dict(
            swpc_forecast=forecast,
            celestrak_gp=None,
            swpc_alerts=None,
        ),
    )
    monkeypatch.setattr(adapters, "current_orbit", lambda *args: None)
    monkeypatch.setattr(protons, "load", lambda **kw: (None, None))
    result = client.post(
        "/analysis",
        json=dict(
            mode="current",
            start_utc="2024-05-10T13:00:00Z",
            duration_minutes=60,
            search_horizon_minutes=60,
        ),
    ).json()
    assert result["recommendation"]["status"] == "insufficient_data"
    assert result["recommendation"]["best_indices"] == []


@pytest.fixture
def client(monkeypatch):
    Base.metadata.create_all(engine)
    adapters.init_sources()
    raw = adapters.store_response(
        "ncei",
        "https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/3day_forecast/2024/05/202405101230three_day_forecast.txt",
        (FIX / "storm.txt").read_text(),
    )
    monkeypatch.setattr(
        adapters,
        "historical_forecast",
        lambda cutoff: (raw, parse_forecast(raw["body"])),
    )
    monkeypatch.setattr(adapters, "historical_orbit", lambda *args: None)
    monkeypatch.setattr(adapters, "donki_context", lambda *args: None)
    with TestClient(app) as c:
        yield c


def test_saved_analysis_and_exports_identical(client, monkeypatch):
    request = dict(
        mode="historical_replay",
        start_utc="2024-05-10T13:00:00Z",
        cutoff_utc="2024-05-10T12:30:00Z",
        duration_minutes=360,
        search_horizon_minutes=720,
    )
    response = client.post("/analysis", json=request)
    assert response.status_code == 200
    data = response.json()
    identifier = data["id"]
    assert len(data["windows"]) == 3
    assert all(w["duration_minutes"] == 360 for w in data["windows"])
    assert data["recommendation"]["winner"] is None
    assert data["windows"][0]["factors"][0]["status"] == "attention"
    assert client.get(f"/analysis/{identifier}").json() == data
    assert client.get(f"/analysis/{identifier}/export.json").json() == data
    pdf = client.get(f"/analysis/{identifier}/report.pdf")
    assert pdf.status_code == 200
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert identifier in text
    assert data["recommendation"]["reason"] in text.replace("\n", " ")
    for w in data["windows"]:
        assert w["start"] in text
        for f in w["factors"]:
            assert f["status"] in text

    def no_network(*args, **kwargs):
        raise AssertionError("Offline reproduction must not call adapters")

    for name in [
        "historical_forecast",
        "historical_orbit",
        "donki_context",
        "current_sources",
    ]:
        monkeypatch.setattr(adapters, name, no_network)
    reproduced = client.post(f"/analysis/{identifier}/reproduce").json()
    assert reproduced["matches"] and not reproduced["network_used"]


@pytest.mark.parametrize("with_orbit", [False, True])
def test_current_reproduction_never_uses_network(client, monkeypatch, with_orbit):
    from backend.app import analysis, protons

    monkeypatch.setattr(analysis, "now", lambda: "2026-09-18T20:00:00+00:00")
    forecast = adapters.store_response(
        "swpc_forecast",
        adapters.CATALOG["swpc_forecast"]["url"],
        (FIX / "swpc_forecast.txt").read_text(),
    )
    orbit = (
        adapters.store_response(
            "celestrak_gp",
            adapters.CATALOG["celestrak_gp"]["url"],
            (FIX / "celestrak_gp.txt").read_text(),
        )
        if with_orbit
        else None
    )
    if orbit:
        orbit["stale"] = True
    monkeypatch.setattr(
        adapters,
        "current_sources",
        lambda: dict(
            swpc_forecast=forecast,
            celestrak_gp=orbit,
            swpc_alerts=None,
        ),
    )
    monkeypatch.setattr(adapters, "current_orbit", lambda *args: orbit)
    monkeypatch.setattr(
        protons,
        "load",
        lambda **kw: (protons.summarize(None, "primary", at=kw["at"]), None),
    )
    response = client.post(
        "/analysis",
        json=dict(
            mode="current",
            start_utc="2026-09-18T20:00:00Z",
            duration_minutes=60,
            search_horizon_minutes=60,
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recommendation"]["status"] != "insufficient_data"
    if with_orbit:
        assert data["orbit"]["source_stale"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden during reproduce")

    for method in [
        "current_sources",
        "current_orbit",
        "historical_orbit",
        "historical_forecast",
        "fetch",
        "donki_context",
    ]:
        monkeypatch.setattr(adapters, method, forbidden)
    monkeypatch.setattr(protons, "load", forbidden)
    reproduced = client.post(f"/analysis/{data['id']}/reproduce")
    assert reproduced.status_code == 200 and reproduced.json()["matches"]


def test_cutoff_prevents_future_leak(client):
    data = client.post(
        "/analysis",
        json=dict(
            mode="historical_replay",
            start_utc="2024-05-10T13:00:00Z",
            cutoff_utc="2024-05-10T12:29:00Z",
            duration_minutes=60,
            search_horizon_minutes=60,
        ),
    ).json()
    assert data["windows"][0]["factors"][0]["facts"] == []
    assert data["windows"][0]["factors"][0]["status"] == "insufficient_data"


def test_api_validation_and_admin_closed(client):
    assert client.get("/health").status_code == 200
    assert client.post("/analysis", json={}).status_code == 422
    assert (
        client.post("/admin/sources/ncei", json={"mode": "disabled"}).status_code == 403
    )
    assert client.get("/analysis/missing").status_code == 404


@pytest.mark.parametrize("source", list(adapters.CATALOG))
def test_each_source_disabled_returns_missing(source):
    adapters.init_sources()
    adapters.controls[source] = "disabled"
    try:
        assert adapters.fetch(source) is None
    finally:
        adapters.controls.pop(source, None)


def test_all_sources_failed_analysis_is_partial(client, monkeypatch):
    monkeypatch.setattr(
        adapters,
        "current_sources",
        lambda: {
            k: None
            for k in [
                "swpc_forecast",
                "celestrak_gp",
            ]
        },
    )
    monkeypatch.setattr(adapters, "current_orbit", lambda *args: None)
    monkeypatch.setattr(adapters, "fetch", lambda *args, **kwargs: None)
    data = client.post(
        "/analysis",
        json=dict(
            mode="current",
            start_utc="2026-09-18T20:00:00Z",
            duration_minutes=60,
            search_horizon_minutes=60,
        ),
    ).json()
    assert data["status"] == "partial"
    assert all(
        f["status"] == "insufficient_data"
        for w in data["windows"]
        for f in w["factors"]
    )


def test_zero_horizon_not_duplicate_window(client):
    data = client.post(
        "/analysis",
        json=dict(
            mode="historical_review",
            start_utc="2024-05-10T13:00:00Z",
            duration_minutes=60,
            search_horizon_minutes=0,
        ),
    ).json()
    assert len(data["windows"]) == 1
    assert data["recommendation"]["winner"] is None
