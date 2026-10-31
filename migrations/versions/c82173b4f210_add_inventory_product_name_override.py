"""allow inventory-specific product display names

Revision ID: c82173b4f210
Revises: f53d92b31a08
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c82173b4f210"
down_revision: Union[str, Sequence[str], None] = "f53d92b31a08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_products", sa.Column("name_override", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_products", "name_override")
