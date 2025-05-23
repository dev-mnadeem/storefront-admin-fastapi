"""Application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routers import health, insights, inventory, products, sales
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.security import log_auth_mode
from app.db.base import Base
from app.db.session import engine
from app.models import Inventory, InventoryLog, Product, Sale  # noqa: F401

logging.basicConfig(level=logging.INFO)

DESCRIPTION = "Products, stock and sales analytics for a storefront admin dashboard."


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_auth_mode()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Storefront Admin API",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    for module in (health, products, inventory, sales, insights):
        app.include_router(module.router)
    return app


app = create_app()
