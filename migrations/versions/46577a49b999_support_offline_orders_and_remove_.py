"""support offline orders and remove unused carts

Revision ID: 46577a49b999
Revises: 1718f08c0454
Create Date: 2026-10-08 08:45:49.118840

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46577a49b999'
down_revision: Union[str, Sequence[str], None] = '1718f08c0454'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.drop_table("cart_items")
    op.drop_table("carts")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column(
                "directory_customer_id",
                sa.Integer(),
                nullable=True
            )
        )

        batch_op.alter_column(
            "customer_id",
            existing_type=sa.Integer(),
            nullable=True
        )

        batch_op.create_index(
            "ix_orders_directory_customer_id",
            ["directory_customer_id"],
            unique=False
        )

        batch_op.create_foreign_key(
            "fk_orders_directory_customer_id_customers",
            "customers",
            ["directory_customer_id"],
            ["id"]
        )

        batch_op.create_check_constraint(
            "ck_orders_status",
            "status IN ('confirmed', 'cancelled', 'delivered')"
        )

        batch_op.create_check_constraint(
            "ck_orders_customer_identity",
            "(customer_id IS NOT NULL AND directory_customer_id IS NULL) "
            "OR "
            "(customer_id IS NULL AND directory_customer_id IS NOT NULL)"
        )

def downgrade() -> None:
    offline_order = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM orders "
            "WHERE customer_id IS NULL LIMIT 1"
        )
    ).first()

    if offline_order is not None:
        raise ValueError(
            "Cannot downgrade while offline orders exist"
        )

    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint(
            "ck_orders_customer_identity",
            type_="check"
        )

        batch_op.drop_constraint(
            "fk_orders_directory_customer_id_customers",
            type_="foreignkey"
        )

        batch_op.drop_index("ix_orders_directory_customer_id")

        batch_op.alter_column(
            "customer_id",
            existing_type=sa.Integer(),
            nullable=False
        )

        batch_op.drop_column("directory_customer_id")

    op.create_table(
        "carts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inventory_id", sa.Integer(), sa.ForeignKey("inventories.id"), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "cart_items",
        sa.Column("cart_id", sa.Integer(), sa.ForeignKey("carts.id"), primary_key=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0"),
    )
