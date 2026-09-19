from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

Path(settings.cache_dir).mkdir(parents=True, exist_ok=True)


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "source"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[dict] = mapped_column(JSON)


class IngestionRun(Base):
    __tablename__ = "ingestion_run"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source.id"))
    details: Mapped[dict] = mapped_column(JSON)


class RawRecord(Base):
    __tablename__ = "raw_record"
    __table_args__ = (UniqueConstraint("source_id", "url", "sha256"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source.id"))
    url: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    provenance: Mapped[dict] = mapped_column(JSON)


class NormalizedObservation(Base):
    __tablename__ = "normalized_observation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    raw_id: Mapped[str] = mapped_column(ForeignKey("raw_record.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class OrbitElementSet(Base):
    __tablename__ = "orbit_element_set"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    raw_id: Mapped[str] = mapped_column(ForeignKey("raw_record.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class UserAnalysisRequest(Base):
    __tablename__ = "user_analysis_request"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class FactorAssessment(Base):
    __tablename__ = "factor_assessment"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("user_analysis_request.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class WindowComparison(Base):
    __tablename__ = "window_comparison"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("user_analysis_request.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class Recommendation(Base):
    __tablename__ = "recommendation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("user_analysis_request.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class ExportArtifact(Base):
    __tablename__ = "export_artifact"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("user_analysis_request.id"))
    payload: Mapped[dict] = mapped_column(JSON)


class AlgorithmVersion(Base):
    __tablename__ = "algorithm_version"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


engine = create_engine(
    settings.database_url,
    **(
        {"connect_args": {"check_same_thread": False}}
        if settings.database_url.startswith("sqlite")
        else {}
    ),
)
Session = sessionmaker(engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc).isoformat()
