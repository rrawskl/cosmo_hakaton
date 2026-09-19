import json
import re
from datetime import datetime, timedelta, timezone
from .schemas import utc

PARSER_VERSION = "2.0.0"


def parse_forecast(text):
    match = re.search(r":Issued:\s*(\d{4} \w{3} \d{1,2} \d{4}) UTC", text)
    if not match:
        raise ValueError("Нет Issued — выпуск непригоден для replay")
    issued = datetime.strptime(match[1], "%Y %b %d %H%M").replace(tzinfo=timezone.utc)
    header = re.search(r"NOAA Kp index breakdown[^\n]*\n\s*\n([^\n]+)", text)
    if not header:
        raise ValueError("Изменилась схема NOAA Kp")
    md = re.findall(r"([A-Z][a-z]{2})\s+(\d{1,2})", header[1])
    days = []
    for month, day in md:
        date = datetime.strptime(f"{issued.year} {month} {day}", "%Y %b %d").replace(
            tzinfo=timezone.utc
        )
        if date < issued - timedelta(days=180):
            date = date.replace(year=date.year + 1)
        if date > issued + timedelta(days=180):
            date = date.replace(year=date.year - 1)
        days.append(date)
    records = []
    for line in text.splitlines():
        row = re.match(r"^(\d{2})-(\d{2})UT\s+(.+)", line)
        if row:
            values = re.findall(r"\d+(?:\.\d+)?", re.sub(r"\(G\d\)", "", row[3]))
            if len(values) != 3 or len(days) != 3:
                raise ValueError("Неполная таблица Kp")
            for date, value in zip(days, values):
                begin = date + timedelta(hours=int(row[1]))
                records.append(
                    dict(
                        metric="Kp",
                        value=float(value),
                        unit="index",
                        start=begin.isoformat(),
                        end=(begin + timedelta(hours=3)).isoformat(),
                        kind="forecast",
                        published_at=issued.isoformat(),
                    )
                )
    for label, metric in [
        ("S1 or greater", "S1_probability"),
        ("R1-R2", "R1_R2_probability"),
        ("R3 or greater", "R3_probability"),
    ]:
        row = re.search(r"^" + re.escape(label) + r"\s+([^\n]+)", text, re.M)
        values = re.findall(r"(\d+)%", row[1]) if row else []
        if len(values) != 3:
            raise ValueError(f"Неполная таблица {metric}")
        for date, value in zip(days, values):
            records.append(
                dict(
                    metric=metric,
                    value=float(value),
                    unit="%",
                    start=date.isoformat(),
                    end=(date + timedelta(days=1)).isoformat(),
                    kind="forecast",
                    published_at=issued.isoformat(),
                )
            )
    if len(records) != 33:
        raise ValueError("Неполный выпуск")
    return records


def parse_protons(text):
    """NOAA integral product documents pfu; absent units use that dataset contract."""
    import math

    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("Expected NOAA array")
    result = {}
    conflicts = set()
    for r in rows:
        try:
            energy = {">=10 MeV": 10, ">=50 MeV": 50, ">=100 MeV": 100}[r["energy"]]
            if r.get("units", r.get("unit", "pfu")) != "pfu" or isinstance(
                r["flux"], bool
            ):
                continue
            value = float(r["flux"])
            stamp = datetime.fromisoformat(r["time_tag"].replace("Z", "+00:00"))
            if stamp.tzinfo is None or not math.isfinite(value) or value < 0:
                continue
            stamp = utc(stamp).isoformat()
            satellite = int(r["satellite"])
            key = (stamp, energy, satellite)
            record = dict(
                metric=f"proton_flux_ge{energy}MeV",
                value=value,
                flux=value,
                unit="pfu",
                start=stamp,
                end=stamp,
                time=stamp,
                published_at=None,
                kind="observation",
                satellite=satellite,
                energy_threshold_mev=energy,
            )
            if key in result and result[key]["flux"] != value:
                conflicts.add(key)
            result[key] = record
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return [r for k, r in sorted(result.items()) if k not in conflicts]


def parse_donki(text):
    # Context only: present API records cannot prove the historical version existed at cutoff.
    rows = json.loads(text)
    seen = set()
    result = []
    for row in rows:
        key = row.get("sepID") or row.get("activityID") or row.get("flrID")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(
            dict(
                event_id=key,
                kind="observation",
                published_at=row.get("submissionTime"),
                strict_replay_eligible=False,
                original=row,
            )
        )
    return result


def parse_rsga(text):
    match = re.search(r":Issued:\s*(\d{4} \w{3} \d{1,2} \d{4}) UTC", text)
    if not match:
        raise ValueError("RSGA без Issued")
    issued = datetime.strptime(match[1], "%Y %b %d %H%M").replace(tzinfo=timezone.utc)
    header = re.search(r"III\.\s+Event probabilities\s+(\d{2}) (\w{3})-", text)
    if not header:
        raise ValueError("Неизвестная схема RSGA")
    day = datetime.strptime(
        f"{issued.year} {header[2]} {header[1]}", "%Y %b %d"
    ).replace(tzinfo=timezone.utc)
    if day < issued - timedelta(days=180):
        day = day.replace(year=day.year + 1)
    result = []
    for label, metric in [
        ("Proton", "S1_probability"),
        ("Class M", "M_flare_probability"),
        ("Class X", "X_flare_probability"),
    ]:
        match = re.search(r"^" + label + r"\s+(\d+)/(\d+)/(\d+)", text, re.M)
        if not match:
            raise ValueError("Неполный RSGA")
        for i, value in enumerate(match.groups()):
            result.append(
                dict(
                    metric=metric,
                    value=float(value),
                    unit="%",
                    start=(day + timedelta(days=i)).isoformat(),
                    end=(day + timedelta(days=i + 1)).isoformat(),
                    kind="forecast",
                    published_at=issued.isoformat(),
                    resolution="1 day",
                )
            )
    return result


def parse_alerts(text):
    latest = {}

    def date_field(message, label):
        found = re.search(label + r":\s*(\d{4} \w{3} \d{1,2} \d{4}) UTC", message)
        return (
            datetime.strptime(found[1], "%Y %b %d %H%M")
            .replace(tzinfo=timezone.utc)
            .isoformat()
            if found
            else None
        )

    for row in json.loads(text):
        message = row["message"]
        issued = utc(row["issue_datetime"]).isoformat()
        code = re.search(r"Message Code:\s*(\w+)", message)
        key = code[1] if code else row["product_id"]
        record = dict(
            metric="NOAA_warning",
            event_id=key,
            published_at=issued,
            kind="forecast" if "WARNING:" in message else "observation",
            start=date_field(message, "Valid From"),
            end=date_field(message, "(?:Now )?Valid Until"),
            value=message,
            unit="message",
            original=row,
        )
        if key not in latest or issued > latest[key]["published_at"]:
            latest[key] = record
    return list(latest.values())
