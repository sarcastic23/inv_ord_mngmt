from fastapi import FastAPI
from routes.products import router as products_router
from routes.products import public_router as get_prd_router
from routes.orders import router as orders_router
from routes.auth import router as auth_router


app = FastAPI()
app.include_router(get_prd_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(auth_router)