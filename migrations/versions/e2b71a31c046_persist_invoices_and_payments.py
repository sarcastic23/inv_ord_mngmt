"""persist invoices, invoice lines, and customer payments

Revision ID: e2b71a31c046
Revises: 46577a49b999
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e2b71a31c046"
down_revision: Union[str, Sequence[str], None] = "46577a49b999"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_number", sa.String(), nullable=False, unique=True),
        sa.Column("inventory_id", sa.Integer(), sa.ForeignKey("inventories.id"), nullable=False),
        sa.Column("customer_name", sa.String(), nullable=False),
        sa.Column("customer_phone", sa.String(), nullable=True),
        sa.Column("customer_address", sa.String(), nullable=True),
        sa.Column("seller_name", sa.String(), nullable=False),
        sa.Column("payment_terms", sa.String(), nullable=False, server_default="credit"),
        sa.Column("is_vat_invoice", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vat_rate_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("vat_total", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.String(), nullable=False),
    )
    op.create_index("ix_invoices_inventory_id", "invoices", ["inventory_id"])
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("vat_rate_bps", sa.Integer(), nullable=False),
        sa.Column("vat_amount", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
    )
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(sa.Column("invoice_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_orders_invoice_id_invoices", "invoices", ["invoice_id"], ["id"])
        batch_op.create_index("ix_orders_invoice_id", ["invoice_id"])


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_index("ix_orders_invoice_id")
        batch_op.drop_constraint("fk_orders_invoice_id_invoices", type_="foreignkey")
        batch_op.drop_column("invoice_id")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_index("ix_invoices_inventory_id", table_name="invoices")
    op.drop_table("invoices")
