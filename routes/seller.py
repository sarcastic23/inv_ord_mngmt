from typing import Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import case, func, select

from order_utils.models import (
    UserRow,
    InventoryRow,
    InventorySellerRow,
    CustomerRow,
    OrderRow,
    OrderItemRow,
    ProductRow,
)

from order_utils.schemas import (
    SellerCreate,
    SellerResponse,
    UserLogin,
    TokenResponse,
    UserResponse,
    OrderDeliveryResponse,
    CustomerResponse,
    CustomerCreate,
    CustomerUpdate,
    OrderSummaryResponse,
    OrderResponse,
    OrderConfirmationResponse,
    OrderItemsAdd,
    OrderItemPriceUpdate,
    CustomerOrderGroupResponse,
    CustomerOrderHistoryResponse
    
)
from order_utils.securities import (
    hash_password,
    verify_password,
    create_access_token,
)
from order_utils.storage import get_db, get_db_write
from .auth import get_current_user

from order_utils.Business import Inventory, orders as BusinessOrder


router = APIRouter(prefix="/seller", tags=["Seller"])

DUMMY_HASH = hash_password("unused-dummy-password")



def get_seller_inventory(
    user: UserResponse = Depends(get_current_user)
) -> int:
    with get_db() as db:
        inventory_id = db.scalar(
            select(InventorySellerRow.inventory_id)
            .where(InventorySellerRow.user_id == user.id)
        )

        if inventory_id is None:
            raise HTTPException(
                status_code=403,
                detail="Seller access required"
            )

        return inventory_id


@router.get("/me", response_model=SellerResponse)
def get_seller_profile(user: UserResponse = Depends(get_current_user)):
    with get_db() as db:
        mapping = db.scalar(
            select(InventorySellerRow)
            .where(InventorySellerRow.user_id == user.id)
        )
        if mapping is None:
            raise HTTPException(status_code=403, detail="Seller access required")
        inventory = db.get(InventoryRow, mapping.inventory_id)
        return SellerResponse(
            id=user.id,
            username=user.username,
            inventory_id=inventory.id,
            inventory_name=inventory.name,
        )


def load_seller_order(
    order_id: int,
    inventory_id: int = Depends(get_seller_inventory)
) -> BusinessOrder:
    with get_db() as db:
        row = db.get(OrderRow, order_id)

        if row is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if row.inventory_id != inventory_id:
            raise HTTPException(
                status_code=403,
                detail="Order belongs to another seller"
            )

        customer_id = row.customer_id
        directory_customer_id = row.directory_customer_id

    try:
        return BusinessOrder(
            inventory=Inventory(inventory_id),
            customer_id=customer_id,
            directory_customer_id=directory_customer_id,
            order_id=order_id
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


def serialize_seller_orders(rows: list[OrderRow]) -> list[dict]:
    if not rows:
        return []

    order_ids = [row.id for row in rows]
    with get_db() as db:
        items = db.execute(
            select(
                OrderItemRow.order_id,
                OrderItemRow.product_id,
                ProductRow.name,
                OrderItemRow.quantity,
                OrderItemRow.unit_price,
            )
            .join(ProductRow, ProductRow.id == OrderItemRow.product_id)
            .where(OrderItemRow.order_id.in_(order_ids))
            .order_by(OrderItemRow.order_id, ProductRow.name)
        ).all()

    items_by_order: dict[int, list[dict]] = {}
    for order_id, product_id, name, quantity, unit_price in items:
        subtotal = quantity * unit_price
        items_by_order.setdefault(order_id, []).append({
            "product_id": product_id,
            "name": name,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })

    return [
        {
            "order_id": row.id,
            "customer_id": row.customer_id,
            "directory_customer_id": row.directory_customer_id,
            "inventory_id": row.inventory_id,
            "status": row.status,
            "items": items_by_order.get(row.id, []),
            "total": sum(item["subtotal"] for item in items_by_order.get(row.id, [])),
        }
        for row in rows
    ]




@router.get("/orders", response_model=list[OrderSummaryResponse])
def list_seller_orders(
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        rows = db.scalars(
            select(OrderRow)
            .where(OrderRow.inventory_id == inventory_id)
            .order_by(OrderRow.id.desc())
        ).all()

        return [
            {
                "order_id": row.id,
                "inventory_id": row.inventory_id,
                "status": row.status
            }
            for row in rows
        ]



@router.get("/orders/recent", response_model=list[OrderResponse])
def list_recent_seller_orders(
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        rows = db.scalars(
            select(OrderRow)
            .where(OrderRow.inventory_id == inventory_id)
            .order_by(OrderRow.id.desc())
            .limit(5)
        ).all()

    return serialize_seller_orders(rows)


@router.get("/order-customers", response_model=list[CustomerOrderGroupResponse])
def list_seller_order_customers(
    inventory_id: int = Depends(get_seller_inventory)
):
    confirmed_count = func.sum(
        case((OrderRow.status == "confirmed", 1), else_=0)
    )
    delivered_count = func.sum(
        case((OrderRow.status == "delivered", 1), else_=0)
    )
    cancelled_count = func.sum(
        case((OrderRow.status == "cancelled", 1), else_=0)
    )

    with get_db() as db:
        directory_rows = db.execute(
            select(
                CustomerRow.id,
                CustomerRow.name,
                CustomerRow.phone,
                CustomerRow.address,
                func.count(OrderRow.id),
                confirmed_count,
                delivered_count,
                cancelled_count,
                func.max(OrderRow.id),
            )
            .join(
                OrderRow,
                OrderRow.directory_customer_id == CustomerRow.id,
            )
            .where(
                CustomerRow.inventory_id == inventory_id,
                OrderRow.inventory_id == inventory_id,
            )
            .group_by(
                CustomerRow.id,
                CustomerRow.name,
                CustomerRow.phone,
                CustomerRow.address,
            )
        ).all()

        account_rows = db.execute(
            select(
                UserRow.id,
                UserRow.username,
                func.count(OrderRow.id),
                confirmed_count,
                delivered_count,
                cancelled_count,
                func.max(OrderRow.id),
            )
            .join(OrderRow, OrderRow.customer_id == UserRow.id)
            .where(OrderRow.inventory_id == inventory_id)
            .group_by(UserRow.id, UserRow.username)
        ).all()

    groups = [
        CustomerOrderGroupResponse(
            customer_type="directory",
            customer_id=row[0],
            customer_name=row[1],
            phone=row[2],
            address=row[3],
            total_orders=row[4],
            confirmed_orders=row[5] or 0,
            delivered_orders=row[6] or 0,
            cancelled_orders=row[7] or 0,
            latest_order_id=row[8],
        )
        for row in directory_rows
    ]
    groups.extend(
        CustomerOrderGroupResponse(
            customer_type="account",
            customer_id=row[0],
            customer_name=row[1],
            total_orders=row[2],
            confirmed_orders=row[3] or 0,
            delivered_orders=row[4] or 0,
            cancelled_orders=row[5] or 0,
            latest_order_id=row[6],
        )
        for row in account_rows
    )
    return sorted(groups, key=lambda group: group.latest_order_id, reverse=True)


@router.get(
    "/order-customers/{customer_type}/{customer_id}/orders",
    response_model=CustomerOrderHistoryResponse,
)
def list_customer_order_history(
    customer_type: Literal["directory", "account"],
    customer_id: int,
    status: Literal["confirmed", "delivered", "cancelled"] = "confirmed",
    page: int = Query(default=1, ge=1),
    inventory_id: int = Depends(get_seller_inventory),
):
    groups = list_seller_order_customers(inventory_id)
    customer = next(
        (
            group for group in groups
            if group.customer_type == customer_type
            and group.customer_id == customer_id
        ),
        None,
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_column = (
        OrderRow.directory_customer_id
        if customer_type == "directory"
        else OrderRow.customer_id
    )
    filters = (
        OrderRow.inventory_id == inventory_id,
        customer_column == customer_id,
        OrderRow.status == status,
    )
    with get_db() as db:
        total = db.scalar(
            select(func.count(OrderRow.id)).where(*filters)
        ) or 0
        query = (
            select(OrderRow)
            .where(*filters)
            .order_by(OrderRow.id.desc())
        )
        if status == "confirmed":
            page_size = max(total, 1)
        else:
            page_size = 5
            query = query.offset((page - 1) * page_size).limit(page_size)
        rows = db.scalars(query).all()

    order_details = serialize_seller_orders(rows)

    return CustomerOrderHistoryResponse(
        customer=customer,
        status=status,
        page=page if status != "confirmed" else 1,
        page_size=page_size,
        total=total,
        page_count=max(1, (total + page_size - 1) // page_size),
        orders=order_details,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
def view_seller_order(
    order: BusinessOrder = Depends(load_seller_order)
):   #we should just use route's order_id to pass it to load_seller_order,,but rn im bored ,, idnt hv energy to update these schemas ...
    result = order.view_order()

    if result is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return result


@router.post(
    "/orders/{order_id}/deliver",
    response_model=OrderDeliveryResponse
)
def deliver_seller_order(
    order: BusinessOrder = Depends(load_seller_order)
):
    if not order.deliver_order():
        raise HTTPException(
            status_code=409,
            detail="Only confirmed orders can be delivered"
        )

    return {
        "order_id": order.order_id,
        "status": "delivered"
    }


@router.patch(
    "/orders/{order_id}/items/{product_id}/price",
    response_model=OrderResponse,
)
def update_seller_order_item_price(
    product_id: str,
    data: OrderItemPriceUpdate,
    order: BusinessOrder = Depends(load_seller_order),
):
    try:
        order.update_item_price(product_id, data.unit_price)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return order.view_order()




@router.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=201
)
def create_customer(
    data: CustomerCreate,
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db_write() as db:
        customer = CustomerRow(
            inventory_id=inventory_id,
            name=data.name,
            phone=data.phone,
            address=data.address
        )

        db.add(customer)
        db.flush()

        response = CustomerResponse.model_validate(customer)

    return response


@router.get(
    "/customers",
    response_model=list[CustomerResponse]
)
def list_customers(
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        customers = db.scalars(
            select(CustomerRow)
            .where(CustomerRow.inventory_id == inventory_id)
            .order_by(CustomerRow.name, CustomerRow.id)
        ).all()

        return [
            CustomerResponse.model_validate(customer)
            for customer in customers
        ]


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse
)
def view_customer(
    customer_id: int,
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        customer = db.scalar(
            select(CustomerRow).where(
                CustomerRow.id == customer_id,
                CustomerRow.inventory_id == inventory_id
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        return CustomerResponse.model_validate(customer)


@router.patch(
    "/customers/{customer_id}",
    response_model=CustomerResponse
)
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    inventory_id: int = Depends(get_seller_inventory)
):
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one field to update"
        )

    if "name" in changes and changes["name"] is None:
        raise HTTPException(
            status_code=422,
            detail="Name cannot be null"
        )

    with get_db_write() as db:
        customer = db.scalar(
            select(CustomerRow).where(
                CustomerRow.id == customer_id,
                CustomerRow.inventory_id == inventory_id
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        for field, value in changes.items():
            setattr(customer, field, value)

        db.flush()
        response = CustomerResponse.model_validate(customer)

    return response



# this creates  order for an offline customer for the seller .

@router.post(
    "/customers/{customer_id}/orders",
    response_model=OrderConfirmationResponse,
    status_code=201
)
def create_customer_order(
    customer_id: int,
    data: OrderItemsAdd,
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        customer = db.scalar(
            select(CustomerRow).where(
                CustomerRow.id == customer_id,
                CustomerRow.inventory_id == inventory_id
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

    items = [
        (item.product_id, item.quantity)
        for item in data.items
    ]

    try:
        order = BusinessOrder(
            inventory=Inventory(inventory_id),
            directory_customer_id=customer_id
        )
        result = order.confirmed_order(items)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if result["order_id"] is None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "No items could be accepted",
                "rejected": result["rejected"]
            }
        )

    return result










@router.post("/register", response_model=SellerResponse, status_code=201)
def register_seller(data: SellerCreate):
    inventory_name = data.inventory_name.strip()

    if not inventory_name:
        raise HTTPException(
            status_code=422,
            detail="Inventory name cannot be blank"
        )

    password_hash = hash_password(data.password)

    with get_db_write() as db:
        existing = db.scalar(
            select(UserRow).where(UserRow.username == data.username)
        )

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Username already exists"
            )

        user = UserRow(
            username=data.username,
            password_hash=password_hash
        )
        inventory = InventoryRow(name=inventory_name)

        db.add_all([user, inventory])
        db.flush()

        db.add(
            InventorySellerRow(
                inventory_id=inventory.id,
                user_id=user.id
            )
        )

        response = SellerResponse(
            id=user.id,
            username=user.username,
            inventory_id=inventory.id,
            inventory_name=inventory.name
        )

    return response


@router.post("/login", response_model=TokenResponse)
def login_seller(data: UserLogin):
    with get_db() as db:
        user = db.scalar(
            select(UserRow).where(UserRow.username == data.username)
        )

        user_id = user.id if user is not None else None
        stored_hash = (
            user.password_hash if user is not None else DUMMY_HASH
        )

        inventory_id = None

        if user is not None:
            inventory_id = db.scalar(
                select(InventorySellerRow.inventory_id)
                .where(InventorySellerRow.user_id == user.id)
            )

    valid_password = verify_password(data.password, stored_hash)

    if user_id is None or not valid_password or inventory_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid seller credentials"
        )

    return TokenResponse(
        access_token=create_access_token(user_id)
    )
