"""Validated GOES service. Measurements are never extrapolated into a forecast."""

import logging
from datetime import timedelta
from statistics import median
from . import adapters
from .config import settings
from .parsers import parse_protons
from .schemas import utc
from .storage import now

log = logging.getLogger(__name__)
ENERGIES = (10, 50, 100)
RANGES = {"6h": 6, "1d": 24, "3d": 72, "7d": 168}


def scale(flux):
    if flux is None:
        return None
    return next((f"S{i}" for i in range(5, 0, -1) if flux >= 10**i), "BELOW_S1")


def trend(rows, at):
    # Compare medians of two 30-minute windows; require >=4 samples each and one satellite.
    selected = [r for r in rows if at - timedelta(hours=1) < utc(r["time"]) <= at]
    if len({r["satellite"] for r in selected}) != 1:
        return "UNAVAILABLE"
    left = [r["flux"] for r in selected if utc(r["time"]) <= at - timedelta(minutes=30)]
    right = [r["flux"] for r in selected if utc(r["time"]) > at - timedelta(minutes=30)]
    if len(left) < 4 or len(right) < 4:
        return "UNAVAILABLE"
    a, b = median(left), median(right)
    tolerance = max(0.01, 0.2 * a)
    return (
        "RISING" if b - a > tolerance else "FALLING" if a - b > tolerance else "STABLE"
    )


def summarize(raw, role, period="6h", at=None):
    at = at or utc(now())
    result = dict(
        status="DATA_UNAVAILABLE",
        range=period,
        observed_at=None,
        fetched_at=raw.get("retrieved_at") if raw else None,
        source=dict(
            provider="NOAA SWPC",
            platform="GOES",
            role=role,
            endpoint=raw.get("url") if raw else None,
        ),
        channels={},
        noaa_scale=dict(level=None),
        trend="UNAVAILABLE",
        freshness=dict(age_seconds=None, stale=True),
        internal_status="UNKNOWN",
        warning_100mev=None,
        reasons=[],
        evidence_id=raw.get("raw_id") if raw else None,
        message="Измерения NOAA временно недоступны.",
    )
    try:
        rows = parse_protons(raw["body"]) if raw else []
    except (ValueError, TypeError):
        log.warning("NOAA proton parsing failed: role=%s", role)
        rows = []
    ages = []
    for energy in ENERGIES:
        series = [
            r
            for r in rows
            if r["energy_threshold_mev"] == energy
            and at - timedelta(hours=RANGES[period]) <= utc(r["time"]) <= at
        ]
        latest = series[-1] if series else None
        age = (at - utc(latest["time"])).total_seconds() if latest else None
        stale = (
            age is None
            or age > settings.proton_data_stale_minutes * 60
            or bool(raw and raw.get("stale"))
        )
        maximum = max(series, key=lambda r: r["flux"]) if series else None
        channel = dict(
            flux=latest["flux"] if latest else None,
            unit="pfu",
            observed_at=latest["time"] if latest else None,
            satellite=latest["satellite"] if latest else None,
            age_seconds=age,
            is_stale=stale,
            trend=trend(series, utc(latest["time"])) if latest else "UNAVAILABLE",
            peak=dict(flux=maximum["flux"], time=maximum["time"]) if maximum else None,
            series=series,
        )
        result["channels"][f"gte_{energy}_mev"] = channel
        if age is not None:
            ages.append(age)
    channels = result["channels"]
    complete = all(c["flux"] is not None for c in channels.values())
    stale = any(c["is_stale"] for c in channels.values())
    result["status"] = (
        "OK"
        if complete and not stale
        else "DATA_STALE"
        if complete
        else "DATA_UNAVAILABLE"
    )
    result["freshness"] = dict(age_seconds=max(ages) if ages else None, stale=stale)
    result["observed_at"] = min(
        (c["observed_at"] for c in channels.values() if c["observed_at"]), default=None
    )
    level = scale(channels["gte_10_mev"]["flux"])
    result["noaa_scale"] = dict(
        level=level,
        basis="Calculated from GOES >=10 MeV; NOAA thresholds, not an issued alert",
    )
    result["trend"] = channels["gte_10_mev"]["trend"]
    v100 = channels["gte_100_mev"]["flux"]
    result["warning_100mev"] = v100 >= 1 if v100 is not None else None
    if result["status"] == "OK":
        result["internal_status"] = {
            "BELOW_S1": "NORMAL",
            "S1": "ATTENTION",
            "S2": "ELEVATED",
            "S3": "HIGH",
            "S4": "CRITICAL",
            "S5": "CRITICAL",
        }[level]
        if result["warning_100mev"] and result["internal_status"] == "NORMAL":
            result["internal_status"] = "ATTENTION"
        result["message"] = (
            "Наблюдаемая солнечно-протонная обстановка NOAA GOES; не прогноз окна ВКД."
        )
    result["reasons"] = [
        f">=10 MeV: {channels['gte_10_mev']['flux']} pfu; NOAA {level or 'нет данных'}",
        f">=100 MeV: {v100} pfu; порог уведомления 1 pfu",
        f"Тренд >=10 MeV: {result['trend']}",
    ]
    return result


def load(period="6h", at=None):
    if period not in RANGES:
        raise ValueError("Unsupported range")
    candidates = []
    for role in ("primary", "secondary"):
        raw = adapters.fetch(f"protons_{role}_{period}")
        result = summarize(raw, role, period, at)
        candidates.append((result, raw))
        if result["status"] == "OK":
            log.info("NOAA proton source selected: role=%s range=%s", role, period)
            return result, raw
        log.warning(
            "NOAA proton source unavailable or stale: role=%s status=%s",
            role,
            result["status"],
        )
    # Keep stale observations visible; never convert an outage into NORMAL.
    return next(
        (c for c in candidates if c[0]["status"] == "DATA_STALE"), candidates[0]
    )


def window_factor(snapshot, start, end, historical=False):
    from .analysis import factor, union_minutes

    result = factor(
        "protons",
        "insufficient_data",
        "Наблюдения GOES: >=10 MeV >=10 pfu или >=100 MeV >=1 pfu вызывают attention. Нет экстраполяции в будущее.",
    )
    result["limitations"] = [
        "GOES не измеряет индивидуальную дозу космонавта.",
        "Измерения не являются прогнозом. Между точками допускается интервал не более 10 минут.",
    ]
    if historical:
        result["limitations"].append(
            "Архив GOES за эту дату не подключён: DATA_UNAVAILABLE."
        )
        return result
    if not snapshot:
        return result
    result["evidence_ids"] = (
        [snapshot["evidence_id"]] if snapshot.get("evidence_id") else []
    )
    coverage = []
    attention = []
    for key in ("gte_10_mev", "gte_100_mev"):
        rows = snapshot["channels"][key]["series"]
        segments = []
        for left, right in zip(rows, rows[1:]):
            a, b = max(start, utc(left["time"])), min(end, utc(right["time"]))
            if (
                a >= b
                or (utc(right["time"]) - utc(left["time"])).total_seconds() > 600
                or left["satellite"] != right["satellite"]
            ):
                continue
            segments.append((a, b))
            high = left["flux"] >= (10 if key == "gte_10_mev" else 1)
            if high:
                attention.append((a, b))
            result["intervals"].append(
                dict(
                    start=a.isoformat(),
                    end=b.isoformat(),
                    state="attention" if high else "favorable",
                    metric=left["metric"],
                    value=left["flux"],
                    unit="pfu",
                )
            )
        coverage.append(union_minutes(segments))
        result["facts"].extend(r for r in rows if start <= utc(r["time"]) <= end)
    result["attention_minutes"] = union_minutes(attention)
    if (
        min(coverage, default=0) >= (end - start).total_seconds() / 60
        and snapshot["status"] == "OK"
    ):
        result["status"] = "attention" if attention else "favorable"
    result["confidence_reasons"] = [
        "Оценка только покрытой наблюдениями части окна; будущее и пробелы остаются неизвестными."
    ]
    return result
