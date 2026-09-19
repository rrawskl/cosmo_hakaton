from contextlib import asynccontextmanager
import asyncio
import hashlib
import secrets
import threading
import time
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Header, Response
from pydantic import BaseModel
from typing import Literal
from sqlalchemy import text
from . import adapters, protons
from .analysis import run
from .config import settings, ALGORITHM_VERSION
from .schemas import AnalysisRequest
from .storage import (
    Session,
    UserAnalysisRequest,
    FactorAssessment,
    WindowComparison,
    Recommendation,
    AlgorithmVersion,
    RawRecord,
    ExportArtifact,
)
from .exports import report
from .parsers import parse_forecast, parse_rsga

refresh_lock = threading.Lock()
last_refresh = 0.0


async def update_loop():
    while True:
        try:
            await asyncio.to_thread(adapters.current_sources)
            await asyncio.to_thread(protons.load)
        except Exception:
            pass  # Each adapter records its failure; scheduler survives schema/source failures.
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app):
    adapters.init_sources()
    with Session.begin() as db:
        if not db.get(AlgorithmVersion, ALGORITHM_VERSION):
            db.add(
                AlgorithmVersion(
                    id=ALGORITHM_VERSION, payload={"rules": "docs/ALGORITHMS.md"}
                )
            )
    task = asyncio.create_task(update_loop()) if settings.auto_refresh else None
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Orbital Risk API", version=ALGORITHM_VERSION, lifespan=lifespan)


@app.get("/health")
def health():
    with Session() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "algorithm_version": ALGORITHM_VERSION}


@app.get("/sources/status")
def sources():
    return adapters.statuses()


@app.post("/sources/refresh")
def refresh():
    global last_refresh
    with refresh_lock:
        if time.monotonic() - last_refresh < 60:
            raise HTTPException(
                429, "Обновление доступно раз в минуту; TTL поставщиков сохраняется"
            )
        last_refresh = time.monotonic()
    adapters.current_sources()
    protons.load()
    return adapters.statuses()


@app.post("/analysis")
def analyze(request: AnalysisRequest):
    result = run(request)
    with Session.begin() as db:
        db.add(
            UserAnalysisRequest(
                id=result["id"], payload=request.model_dump(mode="json"), result=result
            )
        )
        db.flush()
        db.add(
            Recommendation(
                id=str(uuid4()),
                analysis_id=result["id"],
                payload=result["recommendation"],
            )
        )
        db.add(
            WindowComparison(
                id=str(uuid4()),
                analysis_id=result["id"],
                payload={"windows": result["windows"]},
            )
        )
        for w in result["windows"]:
            for f in w["factors"]:
                db.add(
                    FactorAssessment(
                        id=str(uuid4()),
                        analysis_id=result["id"],
                        payload={"window_start": w["start"], **f},
                    )
                )
    return result


def saved(identifier):
    with Session() as db:
        row = db.get(UserAnalysisRequest, identifier)
        if not row:
            raise HTTPException(404, "Расчёт не найден")
        return row.result


@app.get("/analysis/{identifier}")
def get_analysis(identifier: str):
    return saved(identifier)


@app.post("/analysis/{identifier}/reproduce")
def reproduce(identifier: str):
    original = saved(identifier)
    if original["algorithm_version"] != ALGORITHM_VERSION:
        raise HTTPException(
            409, "Для повторного расчёта нужна исходная версия алгоритма"
        )
    by_source = {}
    with Session() as db:
        for evidence in original["evidence"]:
            raw = db.get(RawRecord, evidence["raw_id"])
            if not raw:
                raise HTTPException(409, "Исходная запись отсутствует в хранилище")
            by_source[raw.source_id] = {"body": raw.body, **evidence}
    forecast = by_source.get("ncei")
    records = []
    if forecast:
        parser = (
            parse_forecast
            if "NOAA Kp index breakdown" in forecast["body"]
            else parse_rsga
        )
        records = parser(forecast["body"])
    bundle = dict(
        created_at=original["created_at"],
        source_states=original["sources"],
        current_sources={
            key: by_source.get(key)
            for key in [
                "swpc_forecast",
                "swpc_scales",
                "celestrak_gp",
                "swpc_alerts",
            ]
        },
        historical_forecast=(forecast, records),
        proton_raw=next(
            (v for k, v in by_source.items() if k.startswith("protons_")), None
        ),
        proton_role=(original.get("protons") or {})
        .get("source", {})
        .get("role", "primary"),
        orbit_raw=by_source.get("spacetrack"),
        context=by_source.get("donki"),
    )
    rebuilt = run(AnalysisRequest(**original["request"]), bundle=bundle)
    keys = ["windows", "recommendation", "orbit", "observations", "context", "protons"]
    return {
        "analysis_id": identifier,
        "algorithm_version": ALGORITHM_VERSION,
        "matches": all(rebuilt.get(key) == original.get(key) for key in keys),
        "compared_fields": keys,
        "network_used": False,
        "recomputed": {key: rebuilt.get(key) for key in keys},
    }


@app.get("/analysis/{identifier}/export.json")
def export_json(identifier: str):
    import json

    result = saved(identifier)
    return Response(
        json.dumps(result, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="orbital-{result["id"]}.json"'
        },
    )


@app.get("/analysis/{identifier}/report.pdf")
def export_pdf(identifier: str):
    result = saved(identifier)
    body = report(result)
    with Session.begin() as db:
        db.add(
            ExportArtifact(
                id=str(uuid4()),
                analysis_id=identifier,
                payload={"format": "pdf", "sha256": hashlib.sha256(body).hexdigest()},
            )
        )
    return Response(
        body,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="orbital-{result["id"]}.pdf"'
        },
    )


@app.get("/raw/{identifier}")
def raw(identifier: str):
    with Session() as db:
        row = db.get(RawRecord, identifier)
        if not row:
            raise HTTPException(404, "Исходный ответ не найден")
        if row.source_id == "spacetrack":
            raise HTTPException(
                403,
                "Space-Track: локальная копия доступна оператору; публичная выдача отключена",
            )
        return Response(
            row.body,
            media_type="text/plain",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'",
            },
        )


class Control(BaseModel):
    mode: Literal["enabled", "frozen", "disabled"]


@app.post("/admin/sources/{source}")
def control(
    source: str, payload: Control, authorization: str | None = Header(default=None)
):
    if (
        not settings.admin_token
        or not authorization
        or not secrets.compare_digest(authorization, "Bearer " + settings.admin_token)
    ):
        raise HTTPException(403, "Диагностика отключена или нет доступа")
    if source not in adapters.CATALOG:
        raise HTTPException(404, "Источник не найден")
    adapters.controls[source] = payload.mode
    return {"id": source, "mode": payload.mode}


@app.get("/protons/current")
def proton_current():
    result, _ = protons.load()
    return result


@app.get("/protons/history")
def proton_history(range: Literal["6h", "1d", "3d", "7d"] = "6h"):
    result, _ = protons.load(range)
    return result
