from datetime import timedelta
import json
from uuid import uuid4
from . import adapters, protons
from .config import ALGORITHM_VERSION
from .schemas import utc
from .parsers import (
    parse_forecast,
    parse_donki,
    parse_alerts,
)
from .orbit import select_elements, propagate
from .recommendation import recommend
from .storage import now


def overlap(a, b, c, d):
    return max(0.0, (min(b, d) - max(a, c)).total_seconds() / 60)


def union_minutes(intervals):
    merged = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return sum((b - a).total_seconds() / 60 for a, b in merged)


def eligible(records, cutoff):
    return [
        r for r in records if r.get("published_at") and utc(r["published_at"]) <= cutoff
    ]


def factor(mechanism, status, rule, **kwargs):
    return dict(
        mechanism=mechanism,
        status=status,
        rule=rule,
        intervals=[],
        facts=[],
        confidence="limited",
        confidence_reasons=[],
        limitations=[],
        evidence_ids=[],
        adverse_minutes=0,
        attention_minutes=0,
        **kwargs,
    )


def weather(records, start, end, raw, cutoff=None):
    result = factor(
        "space_weather",
        "insufficient_data",
        "Kp ≥ 5: attention как прокси геомагнитной обстановки. Любая ненулевая вероятность R: attention, не индивидуальный риск. Длительность объединяется без двойного счёта.",
    )
    result["limitations"] = [
        "GOES и Kp не измеряют дозу на МКС. S/G/R — различные явления.",
        "Суточная вероятность не локализует событие внутри суток; интервалы означают применимость прогноза.",
        "Порог допустимости ВКД не задан. favorable означает лишь отсутствие триггеров выбранного правила.",
    ]
    if raw:
        result["evidence_ids"] = [raw["raw_id"]]
    if cutoff:
        records = eligible(records, cutoff)
    records = [
        r
        for r in records
        if r["metric"] in {"Kp", "R1_R2_probability", "R3_probability"}
    ]
    relevant = [
        r for r in records if overlap(start, end, utc(r["start"]), utc(r["end"])) > 0
    ]
    result["facts"] = relevant
    coverage = {}
    intervals = []
    for r in relevant:
        a = max(start, utc(r["start"]))
        b = min(end, utc(r["end"]))
        coverage.setdefault(r["metric"], []).append((a, b))
        attention = (r["metric"] == "Kp" and r["value"] >= 5) or (
            r["unit"] == "%" and r["value"] > 0
        )
        if attention:
            intervals.append((a, b))
            result["intervals"].append(
                dict(
                    start=a.isoformat(),
                    end=b.isoformat(),
                    state="attention",
                    metric=r["metric"],
                    value=r["value"],
                    unit=r["unit"],
                )
            )
    result["attention_minutes"] = union_minutes(intervals)
    complete = all(
        union_minutes(coverage.get(metric, [])) >= (end - start).total_seconds() / 60
        for metric in ["Kp", "R1_R2_probability", "R3_probability"]
    )
    if raw and raw.get("stale"):
        result["limitations"].append("Получение источника неактуально или заморожено.")
        complete = False
    if not complete:
        result["confidence_reasons"] = [
            "Не все временные интервалы Kp/R покрыты пригодным выпуском."
        ]
    else:
        result["status"] = "attention" if intervals else "favorable"
        result["confidence_reasons"] = [
            "Полное покрытие окна внешним прогнозом; точность самого прогноза отдельно не гарантируется."
        ]
    return result


def run(request, bundle=None):
    reference_time = utc(bundle["created_at"]) if bundle is not None else utc(now())
    start = request.start_utc
    cutoff = request.cutoff_utc
    duration = timedelta(minutes=request.duration_minutes)
    offsets = sorted(
        set([0, request.search_horizon_minutes // 2, request.search_horizon_minutes])
    )
    max_end = start + timedelta(minutes=request.search_horizon_minutes) + duration
    errors = []
    records = []
    weather_raw = None
    orbit_raw = None
    proton_snapshot = None
    context = None
    evidence = []
    observations = []
    warnings = []
    warnings_status = "insufficient_data"
    if request.mode == "current":
        sources = (
            bundle["current_sources"]
            if bundle is not None
            else adapters.current_sources()
        )
        weather_raw = sources["swpc_forecast"]
        orbit_raw = (
            bundle.get("orbit_raw")
            if bundle is not None
            else adapters.current_orbit(sources["celestrak_gp"], start, max_end)
        )

        if weather_raw:
            records = parse_forecast(weather_raw["body"])
            issued = utc(records[0]["published_at"])
            if not 0 <= (reference_time - issued).total_seconds() <= 18 * 3600:
                weather_raw = {**weather_raw, "stale": True}
                sources["swpc_forecast"] = weather_raw
        evidence = [x for x in sources.values() if x]
        if orbit_raw and all(
            x.get("raw_id") != orbit_raw.get("raw_id") for x in evidence
        ):
            evidence.append(orbit_raw)
        if sources.get("swpc_alerts"):
            warnings_status = (
                "stale" if sources["swpc_alerts"]["stale"] else "available"
            )
            warnings = parse_alerts(sources["swpc_alerts"]["body"])
            warnings = [
                {
                    **r,
                    "evidence_id": sources["swpc_alerts"]["raw_id"],
                    "stale": sources["swpc_alerts"]["stale"],
                }
                for r in warnings
                if utc(r["published_at"]) <= reference_time
                if (
                    r["start"]
                    and r["end"]
                    and overlap(start, max_end, utc(r["start"]), utc(r["end"])) > 0
                )
                or (
                    not r["end"]
                    and utc(r["published_at"]) >= start - timedelta(hours=24)
                )
            ]
        if bundle is not None:
            proton_raw = bundle.get("proton_raw")
            proton_snapshot = protons.summarize(
                proton_raw, bundle.get("proton_role", "primary"), at=reference_time
            )
        else:
            proton_snapshot, proton_raw = protons.load(at=reference_time)
        if proton_raw:
            evidence.append(proton_raw)
    else:
        weather_raw, records = (
            bundle["historical_forecast"]
            if bundle is not None
            else adapters.historical_forecast(cutoff or start)
        )
        orbit_raw = (
            bundle["orbit_raw"]
            if bundle is not None
            else adapters.historical_orbit(start, cutoff)
        )
        evidence = [x for x in [weather_raw, orbit_raw] if x]
    try:
        context = (
            bundle["context"]
            if bundle is not None
            else adapters.donki_context(start - timedelta(days=1), max_end)
        )
        if context:
            evidence.append(context)
    except (ValueError, KeyError, TypeError):
        errors.append("DONKI: непригодная схема дополнительного контекста")
    orbit = None
    element = None
    if orbit_raw:
        element = select_elements(json.loads(orbit_raw["body"]), start, cutoff)
        if element:
            try:
                orbit = propagate(element, start, max_end)
                orbit.update(
                    raw_id=orbit_raw["raw_id"],
                    retrieved_at=orbit_raw["retrieved_at"],
                    source=orbit_raw["url"],
                    age_hours=(start - utc(element["EPOCH"])).total_seconds() / 3600,
                    geometry_mode="strict_replay"
                    if cutoff
                    else ("reconstruction" if request.mode != "current" else "current"),
                    source_stale=bool(orbit_raw.get("stale")),
                )
                if orbit_raw.get("stale"):
                    orbit["limitations"].append(
                        "Источник не обновился; использован последний пригодный кеш с явно указанной эпохой."
                    )
            except (ValueError, RuntimeError) as exc:
                errors.append(str(exc))
    if orbit is None:
        errors.append(
            "Нет пригодных орбитальных элементов соответствующего периода; траектория и освещённость не рассчитаны."
        )
    windows = []
    for offset in offsets:
        a = start + timedelta(minutes=offset)
        b = a + duration
        sw = weather(records, a, b, weather_raw, cutoff)
        active = [
            r
            for r in warnings
            if r["start"]
            and r["end"]
            and overlap(a, b, utc(r["start"]), utc(r["end"])) > 0
            and not r["stale"]
            and not r.get("cancelled")
            and "proton" not in r["value"].lower()
            and "radiation" not in r["value"].lower()
        ]
        for alert in active:
            sw["facts"].append(alert)
            sw["evidence_ids"] = list(
                dict.fromkeys(sw["evidence_ids"] + [alert["evidence_id"]])
            )
            sw["intervals"].append(
                dict(
                    start=max(a, utc(alert["start"])).isoformat(),
                    end=min(b, utc(alert["end"])).isoformat(),
                    state="attention",
                    metric=alert["event_id"],
                )
            )
            if sw["status"] == "favorable":
                sw["status"] = "attention"
        if active:
            sw["attention_minutes"] = union_minutes(
                [(utc(x["start"]), utc(x["end"])) for x in sw["intervals"]]
            )
            sw["rule"] += (
                " Действующее предупреждение NOAA вызывает attention; интервалы объединены с прогнозом."
            )
        proton = protons.window_factor(
            proton_snapshot,
            a,
            b,
            forecast_records=records,
            alerts=warnings,
            cutoff=cutoff,
            forecast_stale=bool(weather_raw and weather_raw.get("stale")),
        )
        if weather_raw:
            proton["evidence_ids"] = list(
                dict.fromkeys(proton["evidence_ids"] + [weather_raw["raw_id"]])
            )
        light = factor(
            "illumination",
            "not_applicable" if orbit else "insufficient_data",
            "Свет/тень: геометрическое условие работ. Ограничение на допустимую освещённость не задано.",
        )
        if orbit:
            light["intervals"] = [
                dict(
                    start=max(a, utc(x["start"])).isoformat(),
                    end=min(b, utc(x["end"])).isoformat(),
                    state=x["state"],
                )
                for x in orbit["intervals"]
                if overlap(a, b, utc(x["start"]), utc(x["end"])) > 0
            ]
            light["shadow_minutes"] = sum(
                overlap(a, b, utc(x["start"]), utc(x["end"]))
                for x in orbit["intervals"]
                if x["state"] == "shadow"
            )
            light["evidence_ids"] = [orbit_raw["raw_id"]]
            light["limitations"] = orbit["limitations"]
            light["confidence_reasons"] = [
                "Расчёт SGP4 и геометрии Солнца, шаг 60 секунд."
            ]
        windows.append(
            dict(
                start=a.isoformat(),
                end=b.isoformat(),
                duration_minutes=request.duration_minutes,
                factors=[sw, proton, light],
            )
        )
    context_records = parse_donki(context["body"]) if context else []
    return dict(
        id=str(uuid4()),
        created_at=reference_time.isoformat(),
        algorithm_version=ALGORITHM_VERSION,
        request=request.model_dump(mode="json"),
        windows=windows,
        recommendation=recommend(windows, proton_snapshot),
        orbit=orbit,
        protons=proton_snapshot,
        evidence=[{k: v for k, v in r.items() if k != "body"} for r in evidence],
        observations=observations,
        warnings=warnings,
        warnings_status=warnings_status,
        context=context_records,
        limitations=errors
        + [
            "Аналитический инструмент на публичных данных. Не заменяет официальные процедуры планирования и безопасности EVA.",
            "DONKI — дополнительный исторический контекст, исключён из strict replay и не суммируется с NOAA.",
        ],
        sources=bundle["source_states"] if bundle is not None else adapters.statuses(),
        status="partial"
        if any(
            f["mechanism"] in {"space_weather", "protons"}
            and f["status"] == "insufficient_data"
            for w in windows
            for f in w["factors"]
        )
        else "complete",
    )
