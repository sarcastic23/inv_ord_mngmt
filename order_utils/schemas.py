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



class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^\S+$")
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str



class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class OrderSummaryResponse(BaseModel):
    order_id: int
    inventory_id: int
    status: Literal["confirmed", "cancelled", "delivered"]

class OrderCancellationResponse(BaseModel):
    order_id: int
    status: Literal["cancelled"]

class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class SellerCreate(UserCreate):
    inventory_name: str = Field(min_length=1, max_length=100)


class SellerResponse(BaseModel):
    id: int
    username: str
    inventory_id: int
    inventory_name: str


class CustomerCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, min_length=1, max_length=30)
    address: str | None = Field(default=None, min_length=1, max_length=300)


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_id: int
    name: str
    phone: str | None
    address: str | None


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, min_length=1, max_length=30)
    address: str | None = Field(default=None, min_length=1, max_length=300)