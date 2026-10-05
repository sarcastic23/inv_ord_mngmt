from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import CheckConstraint, ForeignKey, create_engine,event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session,sessionmaker


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


db_path = Path(__file__).resolve().parent / "business.db"
engine = create_engine(f"sqlite:///{db_path.as_posix()}", echo=False)


SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


Base.metadata.create_all(engine)





