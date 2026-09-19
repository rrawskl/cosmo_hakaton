"""Allowlisted source adapters with persisted raw provenance and conservative caching."""

import logging
import hashlib
import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
import httpx
from sqlalchemy import select
from .config import settings
from .schemas import utc
from .storage import (
    Session,
    Source,
    RawRecord,
    IngestionRun,
    NormalizedObservation,
    OrbitElementSet,
    now,
)
from .parsers import (
    PARSER_VERSION,
    parse_forecast,
    parse_protons,
    parse_donki,
    parse_rsga,
    parse_alerts,
)

log = logging.getLogger(__name__)

NCEI = "https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/"
CATALOG = {
    "swpc_alerts": dict(
        provider="NOAA SWPC",
        product="Alerts / warnings",
        url="https://services.swpc.noaa.gov/products/alerts.json",
        ttl=300,
        max_age=900,
    ),
    "swpc_forecast": dict(
        provider="NOAA SWPC",
        product="3-Day Forecast",
        url="https://services.swpc.noaa.gov/text/3-day-forecast.txt",
        ttl=1800,
        max_age=18 * 3600,
    ),
    "swpc_scales": dict(
        provider="NOAA SWPC",
        product="NOAA S/G/R scales",
        url="https://services.swpc.noaa.gov/products/noaa-scales.json",
        ttl=300,
        max_age=900,
    ),
    "celestrak_gp": dict(
        provider="CelesTrak",
        product="GP OMM ISS 25544",
        url="https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=JSON",
        ttl=7200,
        max_age=86400,
    ),
    "ncei": dict(
        provider="NOAA NCEI",
        product="Archived SWPC dated bulletins",
        url=NCEI,
        ttl=86400,
        max_age=None,
    ),
    "donki": dict(
        provider="NASA CCMC",
        product="DONKI SEP context",
        url="https://api.nasa.gov/DONKI/SEP",
        ttl=3600,
        max_age=86400,
    ),
    "spacetrack": dict(
        provider="Space-Track",
        product="GP_HISTORY ISS 25544",
        url="https://www.space-track.org",
        ttl=86400,
        max_age=None,
    ),
}
for _role in ("primary", "secondary"):
    for _range, _suffix in {
        "6h": "6-hour",
        "1d": "1-day",
        "3d": "3-day",
        "7d": "7-day",
    }.items():
        CATALOG[f"protons_{_role}_{_range}"] = dict(
            provider="NOAA SWPC",
            product="GOES Integral Proton Flux",
            url=f"https://services.swpc.noaa.gov/json/goes/{_role}/integral-protons-{_suffix}.json",
            ttl=settings.noaa_cache_ttl_seconds,
            max_age=settings.proton_data_stale_minutes * 60,
        )
LOCKS = {k: threading.RLock() for k in CATALOG}
PARSERS = {
    "swpc_forecast": parse_forecast,
    "donki": parse_donki,
    "swpc_alerts": parse_alerts,
}
PARSERS.update({k: parse_protons for k in CATALOG if k.startswith("protons_")})
controls = {}


def mode(source):
    if source in controls:
        return controls[source]
    if source in settings.disabled_sources.split(","):
        return "disabled"
    if source in settings.frozen_sources.split(","):
        return "frozen"
    return "enabled"


def init_sources():
    with Session.begin() as db:
        for key, definition in CATALOG.items():
            if not db.get(Source, key):
                db.add(
                    Source(
                        id=key,
                        state=dict(
                            definition,
                            status="insufficient_data",
                            last_success=None,
                            last_attempt=None,
                            error=None,
                        ),
                    )
                )


def statuses():
    result = []
    with Session() as db:
        for row in db.scalars(select(Source)):
            if row.id not in CATALOG:
                continue
            state = dict(row.state)
            state.update(id=row.id, mode=mode(row.id))
            if mode(row.id) == "disabled":
                state["status"] = "disabled"
            elif mode(row.id) == "frozen":
                state["status"] = "stale"
            elif (
                state.get("last_success")
                and state.get("max_age")
                and (utc(now()) - utc(state["last_success"])).total_seconds()
                > state["max_age"]
            ):
                state["status"] = "stale"
            result.append(state)
    return result


def pack(raw, stale=False):
    return dict(raw_id=raw.id, body=raw.body, **raw.provenance, stale=stale)


def store_response(source, url, body, retrieved=None, metadata=None):
    digest = hashlib.sha256(body.encode()).hexdigest()
    rid = hashlib.sha256((source + url + digest).encode()).hexdigest()
    parser = PARSERS.get(source)
    if source == "ncei" and body.startswith(":Product:"):
        parser = parse_forecast if "NOAA Kp index breakdown" in body else parse_rsga
    records = parser(body) if parser else []
    publication = (
        records[0].get("published_at")
        if records and source in ["swpc_forecast", "ncei"]
        else None
    )
    provenance = dict(
        provider=CATALOG[source]["provider"],
        product=CATALOG[source]["product"],
        url=url,
        retrieved_at=retrieved or now(),
        sha256=digest,
        parser_version=PARSER_VERSION,
        raw_url=f"/raw/{rid}",
        quality="source_response",
        published_at=publication,
        **(metadata or {}),
    )
    with Session.begin() as db:
        old = db.get(RawRecord, rid)
        if old:
            if publication and not old.provenance.get("published_at"):
                old.provenance = {**old.provenance, "published_at": publication}
            return pack(old)
        raw = RawRecord(
            id=rid,
            source_id=source,
            url=url,
            sha256=digest,
            body=body,
            provenance=provenance,
        )
        db.add(raw)
        db.flush()
        if records:
            for i, record in enumerate(records):
                db.add(
                    NormalizedObservation(id=f"{rid}:{i}", raw_id=rid, payload=record)
                )
        if source in ["celestrak_gp", "spacetrack"]:
            for i, record in enumerate(json.loads(body)):
                db.add(OrbitElementSet(id=f"{rid}:{i}", raw_id=rid, payload=record))
    return dict(raw_id=rid, body=body, **provenance, stale=False)


def fetch(source, url=None, params=None, client=None):
    url = url or CATALOG[source]["url"]
    allowed = {
        "services.swpc.noaa.gov",
        "celestrak.org",
        "www.ngdc.noaa.gov",
        "api.nasa.gov",
        "www.space-track.org",
    }
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in allowed:
        raise ValueError("Source URL not allowed")
    # Only non-secret query parameters are persisted.
    safe_params = {k: v for k, v in (params or {}).items() if k != "api_key"}
    identity = str(httpx.URL(url, params=safe_params)) if safe_params else url
    with LOCKS[source]:
        with Session() as db:
            raw = db.scalars(
                select(RawRecord).where(
                    RawRecord.source_id == source, RawRecord.url == identity
                )
            ).all()
            cached = (
                max(raw, key=lambda r: r.provenance["retrieved_at"]) if raw else None
            )
            state = dict(db.get(Source, source).state)
        current_mode = mode(source)
        if current_mode == "disabled":
            return None
        if current_mode == "frozen":
            return pack(cached, stale=True) if cached else None
        # last_success also counts a confirmed unchanged response for this exact URL.
        confirmed = (
            state.get("last_success") if state.get("last_url") == identity else None
        )
        age = (
            (
                utc(now()) - utc(confirmed or cached.provenance["retrieved_at"])
            ).total_seconds()
            if cached
            else float("inf")
        )
        if cached and age < CATALOG[source]["ttl"]:
            log.info("Source cache hit: %s", source)
            if not state.get("last_success"):
                state.update(
                    last_success=cached.provenance["retrieved_at"],
                    status="available",
                    error=None,
                )
                with Session.begin() as db:
                    db.get(Source, source).state = state
            return pack(cached)
        # Failed attempts also obey source cadence, preventing retry storms.
        if (
            state.get("last_attempt")
            and state.get("last_url") == identity
            and (utc(now()) - utc(state["last_attempt"])).total_seconds()
            < CATALOG[source]["ttl"]
        ):
            return (
                pack(cached, stale=state.get("status") != "available")
                if cached
                else None
            )
        log.info("Source cache miss: %s", source)
        state.update(last_attempt=now(), last_url=identity)
        result = None
        error = None
        with (
            httpx.Client(
                timeout=httpx.Timeout(
                    settings.noaa_request_timeout_seconds
                    if source.startswith("protons_")
                    else 25,
                    connect=10,
                ),
                follow_redirects=False,
            )
            if client is None
            else _Borrow(client) as http
        ):
            for attempt in range(2):
                try:
                    response = http.get(url, params=params)
                    response.raise_for_status()
                    body = response.text
                    if source == "celestrak_gp" and not any(
                        int(x.get("NORAD_CAT_ID", 0)) == 25544 for x in response.json()
                    ):
                        raise ValueError("ISS missing")
                    if source == "swpc_scales" and "0" not in response.json():
                        raise ValueError("Scales missing")
                    result = store_response(
                        source,
                        identity,
                        body,
                        metadata={
                            "http_last_modified": response.headers.get("last-modified")
                        },
                    )
                    break
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    error = type(
                        exc
                    ).__name__  # Never serialize request URLs or credentials from exception messages.
                    if (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code < 500
                    ):
                        break
                    if attempt == 0:
                        time.sleep(0.5)
        state.update(
            status="available" if result else ("stale" if cached else "failed"),
            error=None if result else error,
        )
        log.info("Source fetch: %s status=%s error=%s", source, state["status"], error)
        if result:
            state["last_success"] = now()
        with Session.begin() as db:
            db.get(Source, source).state = state
            db.add(
                IngestionRun(
                    id=str(uuid4()),
                    source_id=source,
                    details=dict(
                        at=now(),
                        url=identity,
                        status=state["status"],
                        error=state["error"],
                        raw_id=result["raw_id"] if result else None,
                    ),
                )
            )
        return result or (pack(cached, stale=True) if cached else None)


class _Borrow:
    def __init__(self, client):
        self.client = client

    def __enter__(self):
        return self.client

    def __exit__(self, *args):
        pass


def current_sources():
    # Sequential per vendor, bounded request count; cadences apply even on manual refresh.
    return {
        key: fetch(key)
        for key in [
            "swpc_forecast",
            "swpc_scales",
            "celestrak_gp",
            "swpc_alerts",
        ]
    }


def historical_forecast(cutoff):
    candidates = []
    # Read directory entries; missing files are never manufactured from a filename guess.
    for product, pattern, parser in [
        ("3day_forecast", r"(\d{12}three_day_forecast\.txt)", parse_forecast),
        ("reports_solar_geophysical_activity", r"(\d{8}RSGA\.txt)", parse_rsga),
    ]:
        months = sorted(
            {
                (cutoff.year, cutoff.month),
                ((cutoff - timedelta(days=3)).year, (cutoff - timedelta(days=3)).month),
            }
        )
        entries = []
        for year, month in months:
            root = f"{NCEI}{product}/{year}/{month:02d}/"
            listing = fetch("ncei", root)
            if not listing:
                continue
            for name in set(re.findall(r'href="' + pattern + r'"', listing["body"])):
                stamp = datetime.strptime(
                    name[:12] if product == "3day_forecast" else name[:8],
                    "%Y%m%d%H%M" if product == "3day_forecast" else "%Y%m%d",
                ).replace(tzinfo=timezone.utc)
                if cutoff - timedelta(days=3) <= stamp <= cutoff:
                    entries.append((stamp, root + name))
        for _, url in sorted(entries, reverse=True)[:3]:
            raw = fetch("ncei", url)
            if not raw:
                continue
            try:
                records = parser(raw["body"])
            except ValueError:
                continue
            issued = utc(records[0]["published_at"])
            if issued <= cutoff and cutoff - issued <= timedelta(hours=36):
                candidates.append((issued, raw, records))
                break
        if candidates and product == "3day_forecast":
            break
    return max(candidates, key=lambda x: x[0])[1:] if candidates else (None, [])


def historical_orbit(start, cutoff):
    path = Path(settings.spacetrack_archive)
    if mode("spacetrack") == "disabled":
        return None
    if path.is_file():
        body = path.read_text(encoding="utf-8-sig")
        json.loads(body)
        return store_response(
            "spacetrack",
            "https://www.space-track.org/basicspacedata/query/class/gp_history (local authorized export)",
            body,
        )
    if not settings.spacetrack_username or not settings.spacetrack_password:
        return None
    lo = (start - timedelta(days=3)).strftime("%Y-%m-%d")
    hi = (start + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://www.space-track.org/basicspacedata/query/class/gp_history/NORAD_CAT_ID/25544/EPOCH/{lo}--{hi}/orderby/EPOCH/format/json"
    with Session() as db:
        existing = db.scalars(
            select(RawRecord).where(
                RawRecord.source_id == "spacetrack", RawRecord.url == url
            )
        ).all()
        cached = (
            max(existing, key=lambda r: r.provenance["retrieved_at"])
            if existing
            else None
        )
        if (
            cached
            and (utc(now()) - utc(cached.provenance["retrieved_at"])).total_seconds()
            < CATALOG["spacetrack"]["ttl"]
        ):
            return pack(cached, stale=mode("spacetrack") == "frozen")
        if mode("spacetrack") == "frozen":
            return pack(cached, stale=True) if cached else None
    # Credentials only sent to the fixed official login endpoint, never persisted.
    with httpx.Client(timeout=25, follow_redirects=False) as client:
        try:
            auth = client.post(
                "https://www.space-track.org/ajaxauth/login",
                data={
                    "identity": settings.spacetrack_username,
                    "password": settings.spacetrack_password,
                },
            )
            auth.raise_for_status()
        except httpx.HTTPError:
            return None
        return fetch("spacetrack", url, client=client)


def donki_context(start, end):
    return fetch(
        "donki",
        params=dict(
            startDate=start.strftime("%Y-%m-%d"),
            endDate=end.strftime("%Y-%m-%d"),
            api_key=settings.nasa_api_key,
        ),
    )
