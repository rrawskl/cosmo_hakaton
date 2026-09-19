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


def window_factor(
    snapshot,
    start,
    end,
    forecast_records=None,
    alerts=None,
    cutoff=None,
    forecast_stale=False,
):
    from .analysis import factor, overlap, union_minutes

    result = factor(
        "protons",
        "insufficient_data",
        "Официальный прогноз S1 описывает будущее окно; измерения GOES показывают текущую обстановку и не экстраполируются. Ненулевая вероятность S1 или действующее протонное предупреждение вызывают attention.",
    )
    result["limitations"] = [
        "GOES не измеряет индивидуальную дозу космонавта.",
        "Измерения GOES не являются прогнозом. Между точками наблюдений допускается интервал не более 10 минут.",
        "Суточная вероятность S1 не задаёт точное время события внутри суток.",
    ]
    forecast_records = [
        row
        for row in (forecast_records or [])
        if row.get("metric") == "S1_probability"
        and not forecast_stale
        and (
            not cutoff
            or (row.get("published_at") and utc(row["published_at"]) <= cutoff)
        )
        and overlap(start, end, utc(row["start"]), utc(row["end"])) > 0
    ]
    forecast_coverage = []
    attention = []
    for row in forecast_records:
        a, b = max(start, utc(row["start"])), min(end, utc(row["end"]))
        forecast_coverage.append((a, b))
        state = "attention" if row["value"] > 0 else "favorable"
        if state == "attention":
            attention.append((a, b))
        result["facts"].append(row)
        result["intervals"].append(
            dict(
                start=a.isoformat(),
                end=b.isoformat(),
                state=state,
                metric="S1_probability",
                value=row["value"],
                unit="%",
            )
        )

    for alert in alerts or []:
        text = str(alert.get("value", "")).lower()
        if "proton" not in text and "radiation" not in text:
            continue
        if alert.get("stale") or not alert.get("start") or not alert.get("end"):
            continue
        if cutoff and (
            not alert.get("published_at") or utc(alert["published_at"]) > cutoff
        ):
            continue
        if overlap(start, end, utc(alert["start"]), utc(alert["end"])) <= 0:
            continue
        a, b = max(start, utc(alert["start"])), min(end, utc(alert["end"]))
        attention.append((a, b))
        result["facts"].append(alert)
        result["intervals"].append(
            dict(
                start=a.isoformat(),
                end=b.isoformat(),
                state="attention",
                metric=alert["event_id"],
                unit="message",
            )
        )
        if alert.get("evidence_id"):
            result["evidence_ids"].append(alert["evidence_id"])

    observation_coverage = {"gte_10_mev": [], "gte_100_mev": []}
    if snapshot:
        if snapshot.get("evidence_id"):
            result["evidence_ids"].append(snapshot["evidence_id"])
        for key in ("gte_10_mev", "gte_100_mev"):
            rows = snapshot["channels"][key]["series"]
            result["facts"].extend(r for r in rows if start <= utc(r["time"]) <= end)
            for left, right in zip(rows, rows[1:]):
                a, b = max(start, utc(left["time"])), min(end, utc(right["time"]))
                if (
                    snapshot["status"] != "OK"
                    or a >= b
                    or (utc(right["time"]) - utc(left["time"])).total_seconds() > 600
                    or left["satellite"] != right["satellite"]
                ):
                    continue
                observation_coverage[key].append((a, b))
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
        rows_50 = snapshot["channels"]["gte_50_mev"]["series"]
        result["facts"].extend(r for r in rows_50 if start <= utc(r["time"]) <= end)
        if snapshot["status"] != "OK":
            result["limitations"].append(
                "Текущие измерения GOES отсутствуют или устарели; прогноз окна остаётся отдельным источником."
            )
    else:
        result["limitations"].append(
            "Текущие измерения GOES недоступны; для окна используется только официальный прогноз S1."
        )

    result["evidence_ids"] = list(dict.fromkeys(result["evidence_ids"]))
    result["attention_minutes"] = union_minutes(attention)
    # Observations cover the mechanism only where BOTH monitored energies exist.
    observed_both = [
        (max(a, c), min(b, d))
        for a, b in observation_coverage["gte_10_mev"]
        for c, d in observation_coverage["gte_100_mev"]
        if max(a, c) < min(b, d)
    ]
    complete = (
        union_minutes(forecast_coverage + observed_both)
        >= (end - start).total_seconds() / 60
    )
    result["coverage_minutes"] = union_minutes(forecast_coverage + observed_both)
    result["forecast_probability_max"] = max(
        (r["value"] for r in forecast_records), default=None
    )
    result["basis"] = (
        "forecast_and_observations"
        if forecast_coverage and observed_both
        else "forecast"
        if forecast_coverage
        else "observations"
        if observed_both
        else "unavailable"
    )
    if forecast_stale:
        result["limitations"].append(
            "Устаревший прогноз S1 исключён из оценки покрытия окна."
        )
    if complete:
        result["status"] = "attention" if attention else "favorable"
        result["confidence_reasons"] = [
            "Окно покрыто пригодным прогнозом S1 и/или парными измерениями GOES на наблюдённом интервале."
        ]
    else:
        result["confidence_reasons"] = [
            "Официальный прогноз S1 не покрывает всё окно; текущие измерения не подставляются вместо прогноза."
        ]
    return result
