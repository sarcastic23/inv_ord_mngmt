from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class ProductCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class InventoryProductInput(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    stock: int = Field(ge=0)
    unit_price: int = Field(ge=0)




class OrderItemInput(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    inventory_id: int
    customer_id: int
    items: list[OrderItemInput] = Field(min_length=1)


class OrderItemsAdd(BaseModel):
    items: list[OrderItemInput] = Field(min_length=1)


class OrderItemReject(BaseModel):
    quantity: int = Field(gt=0)




class OrderItemResponse(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: int
    subtotal: int


class OrderResponse(BaseModel):
    order_id: int
    customer_id: int
    inventory_id: int
    status: Literal["confirmed", "cancelled", "delivered"]
    items: list[OrderItemResponse]
    total: int


class RejectedOrderItem(BaseModel):
    product_id: str
    qty: int
    message: str


class OrderConfirmationResponse(BaseModel):
    order_id: int
    rejected: list[RejectedOrderItem]


class OrderItemRejectResponse(BaseModel):
    order_id: int
    product_id: str
    removed_quantity: int


class OrderDeliveryResponse(BaseModel):
    order_id: int
    status: Literal["delivered"]