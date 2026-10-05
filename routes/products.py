from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from order_utils.models import ProductRow
from order_utils.storage import get_db_dependency
from order_utils.schemas import ProductCreate, ProductResponse,InventoryProductInput
from sqlalchemy.exc import IntegrityError
from order_utils.Business import Inventory, Product


router = APIRouter()






router = APIRouter()


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



@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=201
)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db_dependency)
):
    row = ProductRow(id=product.id, name=product.name)

    try:
        with db.begin():
            db.add(row)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Product ID already exists"
        )

    db.refresh(row)
    return row







@router.put("/inventories/{inventory_id}/products")
def set_inventory_products(
    inventory_id: int,
    products: list[InventoryProductInput]
):
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