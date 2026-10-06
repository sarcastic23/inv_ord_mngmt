from fastapi import APIRouter, HTTPException

from order_utils.Business import Inventory, orders as BusinessOrder
from order_utils.models import OrderRow
from order_utils.storage import get_db
from order_utils.schemas import (
    OrderCreate,
    OrderItemsAdd,
    OrderItemReject,
)
from order_utils.schemas import OrderResponse,OrderConfirmationResponse,OrderDeliveryResponse,OrderItemRejectResponse

router = APIRouter(prefix="/orders", tags=["Orders"])


def load_order(order_id: int) -> BusinessOrder:
    with get_db() as db:
        row = db.get(OrderRow, order_id)

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        inventory_id = row.inventory_id
        customer_id = row.customer_id

    try:
        inventory = Inventory(inventory_id)
        return BusinessOrder(
            inventory=inventory,
            customer_id=customer_id,
            order_id=order_id
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.post("", status_code=201,response_model=OrderConfirmationResponse)
def create_order(data: OrderCreate):
    try:
        inventory = Inventory(data.inventory_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    order = BusinessOrder(
        inventory=inventory,
        customer_id=data.customer_id
    )

    items = [
        (item.product_id, item.quantity)
        for item in data.items
    ]

    try:
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


@router.get("/{order_id}",response_model=OrderResponse)
def get_order(order_id: int):
    order = load_order(order_id)
    result = order.view_order()

    if result is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return result


@router.post("/{order_id}/items",response_model=OrderConfirmationResponse)
def add_order_items(order_id: int, data: OrderItemsAdd):
    order = load_order(order_id)

    items = [
        (item.product_id, item.quantity)
        for item in data.items
    ]

    try:
        return order.confirmed_order(items)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.post("/{order_id}/items/{product_id}/reject",response_model=OrderItemRejectResponse)
def reject_order_item(
    order_id: int,
    product_id: str,
    data: OrderItemReject
):
    order = load_order(order_id)

    try:
        removed = order.reject_order(product_id, data.quantity)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if removed is False:
        raise HTTPException(
            status_code=409,
            detail="Order is not confirmed or item is not in the order"
        )

    return {
        "order_id": order_id,
        "product_id": product_id,
        "removed_quantity": removed
    }


@router.post("/{order_id}/deliver",response_model=OrderDeliveryResponse)
def deliver_order(order_id: int):
    order = load_order(order_id)

    if not order.deliver_order():
        raise HTTPException(
            status_code=409,
            detail="Only confirmed orders can be delivered"
        )

    return {
        "order_id": order_id,
        "status": "delivered"
    }