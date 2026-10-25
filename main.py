import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.products import router as products_router
from routes.products import public_router as get_prd_router
from routes.orders import router as orders_router
from routes.auth import router as auth_router
from routes.seller import router as seller_router


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "FRONTEND_ORIGINS", "http://localhost:3000"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(get_prd_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(auth_router)
app.include_router(seller_router)
