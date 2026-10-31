from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column



class Base(DeclarativeBase):
    pass


class ProductRow(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]


class InventoryRow(Base):
    __tablename__ = "inventories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class InventoryProductRow(Base):
    __tablename__ = "inventory_products"

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id"),
        primary_key=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
        primary_key=True
    )

    name_override: Mapped[str | None]
    stock: Mapped[int]
    unit_price: Mapped[int]

    __table_args__ = (
        CheckConstraint("stock >= 0"),
        CheckConstraint("unit_price >= 0"),
    )


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    customer_id: Mapped[int | None]

    directory_customer_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "customers.id",
            name="fk_orders_directory_customer_id_customers"
        ),
        index=True
    )

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id")
    )

    status: Mapped[str] = mapped_column(default="confirmed")
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), index=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('confirmed', 'cancelled', 'delivered')",
            name="ck_orders_status"
        ),
        CheckConstraint(
            "(customer_id IS NOT NULL AND directory_customer_id IS NULL) "
            "OR "
            "(customer_id IS NULL AND directory_customer_id IS NOT NULL)",
            name="ck_orders_customer_identity"
        ),
    )
class OrderItemRow(Base):
    __tablename__ = "order_items"

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        primary_key=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
        primary_key=True
    )

    quantity: Mapped[int]
    unit_price: Mapped[int]

    __table_args__ = (
        CheckConstraint("quantity > 0"),
        CheckConstraint("unit_price >= 0"),
    )


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]



class InventorySellerRow(Base):
    __tablename__ = "inventory_sellers"

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id"),
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True
    )




class CustomerRow(Base):  
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id"),
        index=True
    )

    name: Mapped[str]
    phone: Mapped[str | None]
    address: Mapped[str | None]


class InvoiceRow(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(unique=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventories.id"), index=True)
    customer_name: Mapped[str]
    customer_phone: Mapped[str | None]
    customer_address: Mapped[str | None]
    seller_name: Mapped[str]
    payment_terms: Mapped[str] = mapped_column(default="credit")
    is_vat_invoice: Mapped[bool] = mapped_column(default=False)
    vat_rate_bps: Mapped[int] = mapped_column(default=0)
    subtotal: Mapped[int]
    vat_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    issued_at: Mapped[str]


class InvoiceItemRow(Base):
    __tablename__ = "invoice_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str]
    product_name: Mapped[str]
    quantity: Mapped[int]
    unit_price: Mapped[int]
    subtotal: Mapped[int]
    vat_rate_bps: Mapped[int]
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class PaymentRow(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    paid_at: Mapped[str]
    method: Mapped[str | None]
    reference: Mapped[str | None]


