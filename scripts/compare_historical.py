"""Reproducible comparison with published NOAA forecasts, not an independent model."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path

from backend.app.analysis import overlap, union_minutes, weather
from backend.app.config import ALGORITHM_VERSION
from backend.app.parsers import parse_forecast
from backend.app.protons import window_factor
from backend.app.recommendation import recommend
from backend.app.schemas import utc

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "backend/tests/fixtures"


def compare_case(filename):
    text = (FIX / filename).read_text(encoding="utf8")
    rows = parse_forecast(text)
    cutoff = utc(rows[0]["published_at"])
    start = cutoff + timedelta(minutes=30)
    windows = []
    details = []
    for offset in [0, 360, 720]:
        a = start + timedelta(minutes=offset)
        b = a + timedelta(hours=6)
        selected = [
            r for r in rows if overlap(a, b, utc(r["start"]), utc(r["end"])) > 0
        ]
        kp = [r for r in selected if r["metric"] == "Kp"]
        kp_minutes = union_minutes(
            [
                (max(a, utc(r["start"])), min(b, utc(r["end"])))
                for r in kp
                if r["value"] >= 5
            ]
        )
        sw = weather(rows, a, b, {"raw_id": filename, "stale": False}, cutoff)
        proton = window_factor(None, a, b, forecast_records=rows, cutoff=cutoff)
        windows.append(
            dict(
                start=a.isoformat(),
                end=b.isoformat(),
                duration_minutes=360,
                factors=[sw, proton],
            )
        )
        details.append(
            dict(
                start=a.isoformat(),
                end=b.isoformat(),
                kp_max=max(r["value"] for r in kp),
                kp_ge5_minutes=kp_minutes,
                s1_probability_max=proton["forecast_probability_max"],
                r1_r2_probability_max=max(
                    r["value"] for r in selected if r["metric"] == "R1_R2_probability"
                ),
                r3_probability_max=max(
                    r["value"] for r in selected if r["metric"] == "R3_probability"
                ),
                weather_status=sw["status"],
                proton_status=proton["status"],
            )
        )
    manifest = json.loads((FIX / "manifest.json").read_text(encoding="utf8"))
    return dict(
        source=next(x["url"] for x in manifest if x["file"] == filename),
        cutoff=cutoff.isoformat(),
        forecast_sha256_lf=hashlib.sha256(text.encode()).hexdigest(),
        windows=details,
        recommendation=recommend(windows),
    )


def main():
    cases = {
        name: compare_case(file)
        for name, file in [("storm", "storm.txt"), ("control", "quiet.txt")]
    }
    output = ROOT / "data/experiments/comparison.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            dict(
                algorithm_version=ALGORITHM_VERSION,
                cases=cases,
                limitations=[
                    "NOAA is the upstream forecast, not an independent competing model.",
                    "No EVA dose or GO/NO-GO validation; these are forecast-window calculations.",
                    "No historical GOES observations or orbital geometry are used in this isolated factor comparison.",
                ],
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    print(output)
    for name, case in cases.items():
        print(
            name,
            case["recommendation"]["status"],
            [
                (w["kp_max"], w["kp_ge5_minutes"], w["s1_probability_max"])
                for w in case["windows"]
            ],
        )


if __name__ == "__main__":
    main()
