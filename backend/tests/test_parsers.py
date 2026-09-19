from pathlib import Path
from backend.app.parsers import (
    parse_forecast,
    parse_rsga,
    parse_donki,
    parse_protons,
)
from backend.app.analysis import overlap, union_minutes, eligible, weather
from backend.app.schemas import utc
import pytest

FIX = Path(__file__).parent / "fixtures"


def test_real_forecast_storm():
    rows = parse_forecast((FIX / "storm.txt").read_text())
    assert len(rows) == 33
    assert max(r["value"] for r in rows if r["metric"] == "Kp") == 8.33
    assert all(r["value"] == 55 for r in rows if r["metric"] == "S1_probability")
    assert all(r["published_at"] == "2024-05-10T12:30:00+00:00" for r in rows)


def test_real_rsga():
    rows = parse_rsga((FIX / "rsga_example.txt").read_text())
    assert len(rows) == 9
    assert rows[0]["value"] == 25


def test_real_protons_and_donki_deduplication():
    assert parse_protons((FIX / "swpc_protons.txt").read_text())
    import json

    rows = json.loads((FIX / "donki.txt").read_text())
    parsed = parse_donki(json.dumps(rows + rows))
    assert len(parsed) == len({r["sepID"] for r in rows})
    assert all(not r["strict_replay_eligible"] for r in parsed)


def test_cutoff_publication_inclusive():
    rows = parse_forecast((FIX / "storm.txt").read_text())
    assert eligible(rows, utc("2024-05-10T12:29:59Z")) == []
    assert len(eligible(rows, utc("2024-05-10T12:30:00Z"))) == 33
    assert eligible([{"published_at": None}], utc("2024-05-10T12:30:00Z")) == []


def test_synthetic_intervals_union_no_double_count():
    from datetime import timedelta

    a = utc("2024-05-10T00:00:00Z")
    b = a + timedelta(hours=1)
    assert overlap(a, b, b, b + timedelta(hours=1)) == 0
    assert union_minutes([(a, b), (a, b)]) == 60


def test_missing_not_favorable():
    assert (
        weather([], utc("2024-05-10T12:00:00Z"), utc("2024-05-10T18:00:00Z"), None)[
            "status"
        ]
        == "insufficient_data"
    )


def test_schema_drift():
    with pytest.raises(ValueError):
        parse_forecast("<html>Error</html>")


def test_real_alert_validity_and_dedup():
    import json
    from backend.app.parsers import parse_alerts

    text = (FIX / "swpc_alerts.txt").read_text()
    rows = parse_alerts(text)
    assert rows
    assert any(r["start"] and r["end"] for r in rows)
    assert len(parse_alerts(json.dumps(json.loads(text) * 2))) == len(rows)
