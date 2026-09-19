"""Reproduce limited 24-hour Kp event comparison, never a dose forecast."""

import json
import re
import hashlib
from pathlib import Path
from datetime import timedelta
from backend.app.parsers import parse_forecast
from backend.app.schemas import utc
from backend.app.analysis import weather

FIX = Path("backend/tests/fixtures")
out = Path("data/experiments")
out.mkdir(parents=True, exist_ok=True)
cases = []
for name, forecast, verification in [
    ("storm", "storm.txt", "202405111230.txt"),
    ("control", "quiet.txt", "202405021230.txt"),
]:
    text = (FIX / forecast).read_text()
    later = (FIX / verification).read_text()
    records = parse_forecast(text)
    issued = utc(records[0]["published_at"])
    end = issued + timedelta(hours=24)
    observed = lambda t: float(
        re.search(
            r"greatest observed 3 hr Kp over the past 24 hours was (\d+(?:\.\d+)?)", t
        )[1]
    )
    kp = [
        r
        for r in records
        if r["metric"] == "Kp" and utc(r["start"]) < end and utc(r["end"]) > issued
    ]
    predicted = max(r["value"] for r in kp)
    baseline = observed(text)
    actual = observed(later)
    triggered = sorted(
        [r for r in kp if r["value"] >= 5], key=lambda r: utc(r["start"])
    )
    shifts = []
    for minutes in [-15, 0, 15]:
        a = issued + timedelta(minutes=30 + minutes)
        f = weather(
            records, a, a + timedelta(hours=6), {"raw_id": forecast, "stale": False}
        )
        shifts.append(
            dict(
                shift_minutes=minutes,
                status=f["status"],
                attention_minutes=f["attention_minutes"],
            )
        )
    cases.append(
        dict(
            case=name,
            issued=issued.isoformat(),
            verification_issued=parse_forecast(later)[0]["published_at"],
            forecast_max_kp=predicted,
            baseline_last_observed_max_kp=baseline,
            verified_observed_max_kp=actual,
            prediction=predicted >= 5,
            baseline_prediction=baseline >= 5,
            event=actual >= 5,
            forecast_horizon_hours=24,
            forecast_first_threshold_lead_hours=(
                utc(triggered[0]["start"]) - issued
            ).total_seconds()
            / 3600
            if triggered
            else None,
            onset_timing_error_minutes=None,
            warning_lead_to_observed_onset_minutes=None,
            missing_metrics_reason="Верификация даёт максимум за 24 часа, а не точное время наблюдавшегося начала.",
            shifts=shifts,
            stale_status=weather(
                records,
                issued,
                issued + timedelta(hours=6),
                {"raw_id": forecast, "stale": True},
            )["status"],
            forecast_sha256=hashlib.sha256((FIX / forecast).read_bytes()).hexdigest(),
            verification_sha256=hashlib.sha256(
                (FIX / verification).read_bytes()
            ).hexdigest(),
        )
    )
metrics = {}
for method in ["prediction", "baseline_prediction"]:
    metrics[method] = {
        key: sum(1 for c in cases if predicate(c))
        for key, predicate in {
            "hits": lambda c: c[method] and c["event"],
            "misses": lambda c: not c[method] and c["event"],
            "false_alarms": lambda c: c[method] and not c["event"],
            "correct_negatives": lambda c: not c[method] and not c["event"],
        }.items()
    }
result = dict(
    cases=cases,
    metrics=metrics,
    limitations=[
        "Два примера, статистическая значимость не заявляется.",
        "Проверяется порог Kp ≥ 5, не безопасность ВКД и не вероятность травмы.",
        "Выпуск после cutoff используется только для проверки.",
        "Контроль спокойный по Kp, а не по всем S/G/R.",
        "Бины Kp имеют разрешение 3 часа; 24-часовой период выпуска начинается в 12:30 и пересекает граничные бины.",
        "Глобальная устойчивость выбора окна не измерена: исторические измерения GOES не подключены.",
    ],
)
(out / "results.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
)
print(json.dumps(metrics, ensure_ascii=False))
print(out / "results.json")
