"""Initial provenance and analysis schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("state", sa.JSON, nullable=False),
    )
    op.create_table(
        "ingestion_run",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("source_id", sa.String, sa.ForeignKey("source.id"), nullable=False),
        sa.Column("details", sa.JSON, nullable=False),
    )
    op.create_table(
        "raw_record",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("source_id", sa.String, sa.ForeignKey("source.id"), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("sha256", sa.String, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("provenance", sa.JSON, nullable=False),
        sa.UniqueConstraint("source_id", "url", "sha256"),
    )
    for name in ["normalized_observation", "orbit_element_set"]:
        op.create_table(
            name,
            sa.Column("id", sa.String, primary_key=True),
            sa.Column(
                "raw_id", sa.String, sa.ForeignKey("raw_record.id"), nullable=False
            ),
            sa.Column("payload", sa.JSON, nullable=False),
        )
    op.create_table(
        "user_analysis_request",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON, nullable=False),
    )
    for name in [
        "factor_assessment",
        "window_comparison",
        "recommendation",
        "export_artifact",
    ]:
        op.create_table(
            name,
            sa.Column("id", sa.String, primary_key=True),
            sa.Column(
                "analysis_id",
                sa.String,
                sa.ForeignKey("user_analysis_request.id"),
                nullable=False,
            ),
            sa.Column("payload", sa.JSON, nullable=False),
        )
    op.create_table(
        "algorithm_version",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("payload", sa.JSON, nullable=False),
    )


def downgrade():
    for name in [
        "algorithm_version",
        "export_artifact",
        "recommendation",
        "window_comparison",
        "factor_assessment",
        "user_analysis_request",
        "orbit_element_set",
        "normalized_observation",
        "raw_record",
        "ingestion_run",
        "source",
    ]:
        op.drop_table(name)
