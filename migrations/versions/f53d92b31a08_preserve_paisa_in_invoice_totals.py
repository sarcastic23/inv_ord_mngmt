"""preserve paisa precision in invoice totals and payments

Revision ID: f53d92b31a08
Revises: e2b71a31c046
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f53d92b31a08"
down_revision: Union[str, Sequence[str], None] = "e2b71a31c046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, columns in {
        "invoices": ["vat_total", "total"],
        "invoice_items": ["vat_amount", "total"],
        "payments": ["amount"],
    }.items():
        with op.batch_alter_table(table) as batch_op:
            for column in columns:
                batch_op.alter_column(
                    column,
                    existing_type=sa.Integer(),
                    type_=sa.Numeric(14, 2),
                    existing_nullable=False,
                )


def downgrade() -> None:
    for table, columns in {
        "invoices": ["vat_total", "total"],
        "invoice_items": ["vat_amount", "total"],
        "payments": ["amount"],
    }.items():
        with op.batch_alter_table(table) as batch_op:
            for column in columns:
                batch_op.alter_column(
                    column,
                    existing_type=sa.Numeric(14, 2),
                    type_=sa.Integer(),
                    existing_nullable=False,
                )
