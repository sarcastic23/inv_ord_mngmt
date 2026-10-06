from sqlalchemy import select,update
from .storage import get_db,get_db_write
from .models import (
    ProductRow,
    InventoryRow,
    InventoryProductRow,
    OrderRow,
    OrderItemRow,
)





class Product:
    def __init__(self,id,name,stock,unit_price):
        self.name=name
        self.id=id
        self.stock=stock
        self.unit_price=unit_price


    def __repr__(self):
        return f"Product({self.id,self.name,self.stock,self.unit_price})"


class Inventory:
    def __init__(self,inventory_id):
             self.inventory_id = inventory_id

             with get_db() as db:
                    if db.get(InventoryRow, inventory_id) is None:
                        raise ValueError(
                            f"Inventory {inventory_id} does not exist"
                        )


    def add_products(self, products: list[Product]):
      with get_db_write() as db:
            for product in products:
                if product.stock < 0 or product.unit_price < 0:
                    raise ValueError("Stock and price cannot be negative")

                product_row = db.get(ProductRow, product.id)

                if product_row is None:
                    db.add(
                        ProductRow(id=product.id, name=product.name)
                    )
                else:
                    product_row.name = product.name

                db.flush()  #whats its use ,,session

                stock_row = db.get(
                    InventoryProductRow,
                    (self.inventory_id, product.id)
                )

                if stock_row is None:
                    db.add(
                        InventoryProductRow(
                            inventory_id=self.inventory_id,
                            product_id=product.id,
                            stock=product.stock,
                            unit_price=product.unit_price
                        )
                    )
                else:
                    stock_row.stock = product.stock
                    stock_row.unit_price = product.unit_price

      return len(products)


    def list_products(self):
        with get_db() as db:
            statement = (
                select(
                    ProductRow.id,
                    ProductRow.name,
                    InventoryProductRow.stock,
                    InventoryProductRow.unit_price
                )
                .join(
                    InventoryProductRow,
                    ProductRow.id == InventoryProductRow.product_id 
                )
                .where(
                    InventoryProductRow.inventory_id == self.inventory_id
                )
                .order_by(ProductRow.name)
            )

            return db.execute(statement).all()


    def add_existing_products(self, prd_id, qty):
        if qty <= 0:
            return False

        with get_db_write() as db:
            product = db.get(
                InventoryProductRow,
                (self.inventory_id, prd_id)
            )

            if product is None:
                return False

            product.stock += qty

        return qty


    def remove_products(self, prd_id, qty):
        if qty <= 0:
            return False

        with get_db_write() as db:
            product = db.get(
                InventoryProductRow,
                (self.inventory_id, prd_id)
            )

            if product is None:
                return False

            if qty > product.stock:
                return False

            product.stock -= qty

        return qty


    def __getitem__(self, prd_id):
        
        with get_db() as db:
            statement = (
                select(
                    ProductRow.id,
                    ProductRow.name,
                    InventoryProductRow.stock,
                    InventoryProductRow.unit_price
                )
                .join(
                    InventoryProductRow,
                    ProductRow.id == InventoryProductRow.product_id
                )
                .where(
                    InventoryProductRow.inventory_id == self.inventory_id,
                    ProductRow.id == prd_id
                )
            )

            row = db.execute(statement).one_or_none()

            if row is None:
                raise KeyError(prd_id)

            return Product(*row)


    def __contains__(self, prd_id):
     with get_db() as db:
        return db.get(
            InventoryProductRow,
            (self.inventory_id, prd_id)
        ) is not None

     
    def __iter__(self):
        return iter(
            Product(*row)
            for row in self.list_products()
        )


    def __repr__(self):
        return (
            f"Inventory(id={self.inventory_id}, "
            f"products={list(self)})"
        )


    def __setitem__(self, prd_id, product: Product):
        if prd_id != product.id:
            raise ValueError("Key must match the product's ID")

        self.add_products([product])


class orders:
    def __init__(self, inventory: Inventory, customer_id, order_id=None):
        self.inventory = inventory
        self.customer_id = customer_id
        self.order_id = order_id

        if order_id is not None:
            with get_db() as db:
                order = db.get(OrderRow, order_id)

                if order is None:
                    raise ValueError("Order does not exist")

                if (
                    order.inventory_id != inventory.inventory_id
                    or order.customer_id != customer_id
                ):
                    raise ValueError("Order belongs to another inventory or customer")


    def verify_order(self, prd_id, qty):
        if qty <= 0:
            return "Quantity must be positive"

        with get_db() as db:
            product = db.get(
                InventoryProductRow,
                (self.inventory.inventory_id, prd_id)
            )

            if product is None:
                return f"{prd_id} not in this inventory"

            if qty > product.stock:
                return f"{prd_id}: available {product.stock}, requested {qty}"

            return 1


    def process_orders(self, orders: list[tuple]):
        totals = []
        remaining_stock = {}

        with get_db() as db:
            for prd_id, qty in orders:
                if qty <= 0:
                    continue

                product = db.get(
                    InventoryProductRow,
                    (self.inventory.inventory_id, prd_id)
                )

                if product is None:
                    continue

                if prd_id not in remaining_stock:
                    remaining_stock[prd_id] = product.stock

                if qty > remaining_stock[prd_id]:
                    continue

                remaining_stock[prd_id] -= qty
                totals.append(product.unit_price * qty)

        return totals
    
        
    def confirmed_order(self, orders: list[tuple]):
        rejected = []
        order_id = self.order_id

        with get_db_write() as db:
            order = None

            if order_id is not None:
                order = db.get(OrderRow, order_id)

                if order is None or order.status != "confirmed":
                    raise ValueError("Order is no longer open")

            for prd_id, qty in orders:
                if qty <= 0:
                    rejected.append({
                        "product_id": prd_id,
                        "qty": qty,
                        "message": "Quantity must be positive"
                    })
                    continue

                result = db.execute(
                    update(InventoryProductRow)
                    .where(
                        InventoryProductRow.inventory_id
                        == self.inventory.inventory_id,
                        InventoryProductRow.product_id == prd_id,
                        InventoryProductRow.stock >= qty
                    )
                    .values(stock=InventoryProductRow.stock - qty)
                    .execution_options(synchronize_session=False)
                )

                stock_row = db.get(
                    InventoryProductRow,
                    (self.inventory.inventory_id, prd_id)
                )

                if result.rowcount == 0:
                    rejected.append({
                        "product_id": prd_id,
                        "qty": qty,
                        "message": (
                            "Product not in this inventory"
                            if stock_row is None
                            else "Insufficient stock"
                        )
                    })
                    continue

                if order is None:
                    order = OrderRow(
                        customer_id=self.customer_id,
                        inventory_id=self.inventory.inventory_id,
                        status="confirmed"
                    )
                    db.add(order)
                    db.flush()
                    order_id = order.id

                item = db.get(OrderItemRow, (order_id, prd_id))

                if item is None:
                    db.add(
                        OrderItemRow(
                            order_id=order_id,
                            product_id=prd_id,
                            quantity=qty,
                            unit_price=stock_row.unit_price
                        )
                    )
                else:
                    item.quantity += qty

        self.order_id = order_id

        return {"order_id": order_id, "rejected": rejected}


    def reject_order(self, prd_id, qty):
        if qty <= 0 or self.order_id is None:
            return False

        with get_db_write() as db:
            order = db.get(OrderRow, self.order_id)

            if order is None or order.status != "confirmed":
                return False

            item = db.get(
                OrderItemRow,
                (self.order_id, prd_id)
            )

            if item is None:
                return False

            stock_row = db.get(
                InventoryProductRow,
                (self.inventory.inventory_id, prd_id)
            )

            if stock_row is None:
                raise ValueError("Ordered product is missing from inventory")

            actual_removed = min(qty, item.quantity)
            stock_row.stock += actual_removed

            if actual_removed == item.quantity:
                db.delete(item)
            else:
                item.quantity -= actual_removed

            db.flush()

            remaining_item = db.scalar(
                select(OrderItemRow.product_id)
                .where(OrderItemRow.order_id == self.order_id)
                .limit(1)
            )

            if remaining_item is None:
                order.status = "cancelled"

        return actual_removed
          

    def deliver_order(self):
        if self.order_id is None:
            return False

        with get_db_write() as db:
            result = db.execute(
                update(OrderRow)
                .where(
                    OrderRow.id == self.order_id,
                    OrderRow.status == "confirmed"
                )
                .values(status="delivered")
                .execution_options(synchronize_session=False)
            )

            changed = result.rowcount == 1

        return changed


    def view_order(self):
        if self.order_id is None:
            return None

        with get_db() as db:
            order = db.get(OrderRow, self.order_id)

            if order is None:
                return None

            items = db.execute(
                select(
                    OrderItemRow.product_id,
                    ProductRow.name,
                    OrderItemRow.quantity,
                    OrderItemRow.unit_price
                )
                .join(
                    ProductRow,
                    ProductRow.id == OrderItemRow.product_id
                )
                .where(OrderItemRow.order_id == self.order_id)
                .order_by(ProductRow.name)
            ).all()

            return {
                "order_id": order.id,
                "customer_id": order.customer_id,
                "inventory_id": order.inventory_id,
                "status": order.status,
                "items": [
                    {
                        "product_id": prd_id,
                        "name": name,
                        "quantity": qty,
                        "unit_price": price,
                        "subtotal": qty * price
                    }
                    for prd_id, name, qty, price in items
                ],
                "total": sum(qty * price for _, _, qty, price in items)
            }































