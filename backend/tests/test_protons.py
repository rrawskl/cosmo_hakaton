"""Synthetic boundary cases are test-only; real NOAA fixtures validate the contract."""

import json
from datetime import timedelta
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app import protons, adapters
from backend.app.api import app
from backend.app.parsers import parse_protons, parse_forecast
from backend.app.schemas import utc
from backend.app.analysis import weather
from backend.app.storage import Base, engine

AT = utc("2026-09-19T05:15:00Z")
FIX = Path(__file__).parent / "fixtures"


def raw(rows=None):
    return dict(
        body=json.dumps(rows)
        if rows is not None
        else (FIX / "protons-primary.json").read_text(),
        retrieved_at=AT.isoformat(),
        url="https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json",
        raw_id="test",
        stale=False,
    )


def samples(flux=1, trend=1):
    return [
        dict(
            time_tag=(AT - timedelta(minutes=5 * i)).isoformat(),
            satellite=18,
            energy=f">={energy} MeV",
            flux=flux * (trend if i < 6 else 1),
        )
        for i in range(13)
        for energy in [10, 50, 100]
    ]


@pytest.mark.parametrize(
    "value,level",
    [
        (9.999, "BELOW_S1"),
        (10, "S1"),
        (99.999, "S1"),
        (100, "S2"),
        (999.999, "S2"),
        (1000, "S3"),
        (9999.999, "S3"),
        (10000, "S4"),
        (99999.999, "S4"),
        (100000, "S5"),
    ],
)
def test_noaa_boundaries(value, level):
    assert protons.scale(value) == level


def test_real_channels_and_order():
    rows = parse_protons(raw()["body"])
    assert {r["energy_threshold_mev"] for r in rows} == {10, 50, 100}
    assert rows == parse_protons(json.dumps(list(reversed(json.loads(raw()["body"])))))
    assert all(r["unit"] == "pfu" for r in rows)


@pytest.mark.parametrize("bad", [None, -1, float("nan"), float("inf"), True, "oops"])
def test_invalid_flux_skipped(bad):
    row = samples()[0]
    row["flux"] = bad
    assert parse_protons(json.dumps([row])) == []


def test_units_naive_time_and_duplicate_conflict():
    row = samples()[0]
    assert parse_protons(json.dumps([dict(row, units="Sv")])) == []
    assert parse_protons(json.dumps([dict(row, time_tag="2026-09-19T05:15:00")])) == []
    assert len(parse_protons(json.dumps([row, row]))) == 1
    assert parse_protons(json.dumps([row, dict(row, flux=99)])) == []


@pytest.mark.parametrize("body", ["<html>", "{}", "null"])
def test_malformed_normalized(body):
    assert (
        protons.summarize(dict(raw(), body=body), "primary", at=AT)["status"]
        == "DATA_UNAVAILABLE"
    )


@pytest.mark.parametrize(
    "ratio,expected", [(2, "RISING"), (0.5, "FALLING"), (1.05, "STABLE")]
)
def test_smoothed_trend(ratio, expected):
    assert (
        protons.summarize(raw(samples(trend=ratio)), "primary", at=AT)["trend"]
        == expected
    )


def test_stale_and_future_not_current():
    assert (
        protons.summarize(raw(samples()), "primary", at=AT + timedelta(hours=1))[
            "status"
        ]
        == "DATA_STALE"
    )
    assert (
        protons.summarize(raw(samples()), "primary", at=AT - timedelta(days=1))[
            "status"
        ]
        == "DATA_UNAVAILABLE"
    )


def test_100mev_warning_separate_scale():
    r = protons.summarize(raw(samples(flux=1)), "primary", at=AT)
    assert r["noaa_scale"]["level"] == "BELOW_S1" and r["warning_100mev"]
    assert r["internal_status"] == "ATTENTION"
    assert (
        protons.summarize(raw(samples(flux=0.999)), "primary", at=AT)["internal_status"]
        == "NORMAL"
    )


@pytest.mark.parametrize("primary", [None, "malformed", "stale"])
def test_fallback(primary, monkeypatch):
    bad = (
        None
        if primary is None
        else dict(raw(samples()), body="{}")
        if primary == "malformed"
        else dict(raw(samples()), stale=True)
    )
    calls = []

    def fetch(key):
        calls.append(key)
        return bad if "primary" in key else raw(samples())

    monkeypatch.setattr(adapters, "fetch", fetch)
    result, _ = protons.load(at=AT)
    assert result["status"] == "OK" and result["source"]["role"] == "secondary"
    assert len(calls) == 2


def test_both_unavailable(monkeypatch):
    monkeypatch.setattr(adapters, "fetch", lambda *a: None)
    assert protons.load(at=AT)[0]["internal_status"] == "UNKNOWN"


def test_risk_no_future_extrapolation():
    r = protons.summarize(raw(samples(flux=14)), "primary", at=AT)
    covered = protons.window_factor(r, AT - timedelta(hours=1), AT)
    assert covered["status"] == "attention" and covered["attention_minutes"] == 60
    future = protons.window_factor(r, AT, AT + timedelta(hours=1))
    assert future["status"] == "insufficient_data"
    assert (
        protons.window_factor(r, AT - timedelta(hours=1), AT, historical=True)["facts"]
        == []
    )


def test_no_double_count_s1():
    rows = parse_forecast((FIX / "storm.txt").read_text())
    result = weather(rows, utc("2024-05-10T13:00Z"), utc("2024-05-10T19:00Z"), None)
    assert all(f["metric"] != "S1_probability" for f in result["facts"])


def test_timeout_then_secondary_and_cache(monkeypatch):
    Base.metadata.create_all(engine)
    adapters.init_sources()
    # Isolate this test from persisted per-source cadence in other cases.
    from backend.app.storage import Session, Source

    with Session.begin() as db:
        for key in ["protons_primary_6h", "protons_secondary_6h"]:
            db.get(Source, key).state = dict(adapters.CATALOG[key])
    calls = []
    original_client = httpx.Client

    def handler(request):
        calls.append(str(request.url))
        if "/primary/" in str(request.url):
            raise httpx.ReadTimeout("test timeout", request=request)
        return httpx.Response(200, text=raw(samples())["body"])

    monkeypatch.setattr(
        adapters.httpx,
        "Client",
        lambda **kw: original_client(transport=httpx.MockTransport(handler)),
    )
    result, _ = protons.load(at=AT)
    assert result["source"]["role"] == "secondary" and len(calls) == 3
    protons.load(at=AT)
    assert len(calls) == 3


def test_endpoints(monkeypatch):
    Base.metadata.create_all(engine)
    adapters.init_sources()
    monkeypatch.setattr(
        protons,
        "load",
        lambda period="6h": (
            protons.summarize(raw(samples()), "primary", period, AT),
            raw(samples()),
        ),
    )
    with TestClient(app) as client:
        assert client.get("/protons/current").json()["status"] == "OK"
        for period in protons.RANGES:
            assert (
                client.get("/protons/history", params={"range": period}).json()["range"]
                == period
            )
        assert client.get("/protons/history?range=100d").status_code == 422
