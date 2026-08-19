from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions import add_exception_handlers
from app.api.v1 import api_router
from app.core.logging import logger
from app.core.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import fastapi.encoders
import decimal

# Fix FastAPI Decimal serialization to avoid float conversion
fastapi.encoders.ENCODERS_BY_TYPE[decimal.Decimal] = str


from app.db.session import SessionLocal
from app.crud.crud_admin_auth import clean_expired_challenges

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME}")
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    default_origins = [
        "https://www.fareedcoffee.com",
        "https://fareedcoffee.com",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://elfareedcoffee.lovable.app",
        "https://elfreedcoffee.vercel.app",
    ]

    # Combine environment-configured origins with default production and development origins
    configured_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else []
    allowed_origins = list(dict.fromkeys(configured_origins + default_origins))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.ENABLE_HSTS:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    add_exception_handlers(app)

    @app.get("/healthz", tags=["health"])
    def healthz():
        return {"status": "ok"}

    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app

app = create_app()
