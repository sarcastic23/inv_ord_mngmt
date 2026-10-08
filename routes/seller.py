from fastapi import APIRouter, HTTPException,Depends
from sqlalchemy import select

from order_utils.models import  UserRow,InventoryRow,InventorySellerRow,CustomerRow,OrderRow

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
    OrderItemsAdd
    
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