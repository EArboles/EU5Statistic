"""add_index_on_location_stats_view

Revision ID: 50b97241a536
Revises: 9e6e22bb32c4
Create Date: 2026-11-03 20:59:03.152302

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50b97241a536"
down_revision: str | Sequence[str] | None = "9e6e22bb32c4"
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
