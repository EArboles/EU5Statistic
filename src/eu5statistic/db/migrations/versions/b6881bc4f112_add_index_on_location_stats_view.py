"""add_index_on_location_stats_view

Revision ID: b6881bc4f112
Revises: 152e94a6ba4e
Create Date: 2026-11-01 20:12:27.006067

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6881bc4f112"
down_revision: str | Sequence[str] | None = "152e94a6ba4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_location_stats_view_location_year",
        "location_stats_view",
        ["location_id", "year"],
        unique=True,
    )
    op.create_index(
        "ix_location_stats_view_year",
        "location_stats_view",
        ["year"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_location_stats_view_year", table_name="location_stats_view")
    op.drop_index("ix_location_stats_view_location_year", table_name="location_stats_view")
