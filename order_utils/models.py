from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .storage import engine


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

    stock: Mapped[int]
    unit_price: Mapped[int]

    __table_args__ = (
        CheckConstraint("stock >= 0"),
        CheckConstraint("unit_price >= 0"),
    )


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int]
    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id")
    )
    status: Mapped[str] = mapped_column(default="confirmed")

    __table_args__ = (
        CheckConstraint(
            "status IN ('confirmed', 'cancelled', 'delivered')"
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


Base.metadata.create_all(engine)