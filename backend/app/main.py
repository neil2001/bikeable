from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.cities import router as cities_router
from app.api.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.api.health import router as health_router
from app.api.roads import router as roads_router
from app.api.routes import router as routes_router
from app.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(health_router, prefix="/api/v1")
app.include_router(cities_router, prefix="/api/v1")
app.include_router(roads_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")
