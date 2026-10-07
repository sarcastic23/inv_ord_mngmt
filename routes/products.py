from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from order_utils.models import ProductRow
from order_utils.storage import get_db_dependency
from order_utils.schemas import InventoryProductInput
from sqlalchemy.exc import IntegrityError
from order_utils.Business import Inventory, Product
from .auth import get_current_user
from order_utils.models import InventoryRow
from order_utils.schemas import InventoryResponse
from .seller import get_seller_inventory


router = APIRouter( dependencies=[Depends(get_current_user)])

public_router = APIRouter()

@public_router.get("/inventories/{inventory_id}/products")
def view_inventory(inventory_id: int):
    try:
        inventory = Inventory(inventory_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    return [
        {
            "id": product.id,
            "name": product.name,
            "stock": product.stock,
            "unit_price": product.unit_price
        }
        for product in inventory
    ]


@public_router.get(
    "/inventories",
    response_model=list[InventoryResponse]
)
def list_inventories(
    db: Session = Depends(get_db_dependency)
):
    return db.scalars(
        select(InventoryRow).order_by(InventoryRow.name)
    ).all()


@public_router.get("/inventories/{inventory_id}/products/{product_id}")
def view_inventory_product(inventory_id: int, product_id: str):
    try:
        inventory = Inventory(inventory_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    try:
        product = inventory[product_id]
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Product not found in this inventory"
        )

    return {
        "id": product.id,
        "name": product.name,
        "stock": product.stock,
        "unit_price": product.unit_price
    }





@router.get("/products")
def get_products(db: Session = Depends(get_db_dependency)):
    products = db.scalars(select(ProductRow)).all()

    return [
        {"id": product.id, "name": product.name}
        for product in products
    ]



@router.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db_dependency)):
    product = db.get(ProductRow, product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return {"id": product.id, "name": product.name}



@router.put("/inventories/{inventory_id}/products")
def set_inventory_products(
    inventory_id: int,
    products: list[InventoryProductInput],
    seller_inventory_id: int = Depends(get_seller_inventory)
):
    if inventory_id != seller_inventory_id:
        raise HTTPException(
            status_code=403,
            detail="Inventory belongs to another seller"
        )

    try:
        inventory = Inventory(inventory_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))

    product_objects = [
        Product(
            id=product.id,
            name=product.name,
            stock=product.stock,
            unit_price=product.unit_price
        )
        for product in products
    ]

    try:
        count = inventory.add_products(product_objects)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Update conflicts with database constraints"
        )

    return {"inventory_id": inventory_id, "processed": count}