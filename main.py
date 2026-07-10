```python
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import (
    SkillSwapException,
    ResourceNotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ConflictException,
    ValidationException,
)
from app.db.session import engine, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Manage application lifespan events.
    Initialize database and other resources on startup, cleanup on shutdown.
    """
    logger.info("Starting SkillSwap API...")
    
    # Initialize database tables
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down SkillSwap API...")
    await engine.dispose()
    logger.info("Database connections closed")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A RESTful API platform for professionals to exchange skills without monetary transactions",
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)


# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers
@app.exception_handler(SkillSwapException)
async def skillswap_exception_handler(request: Request, exc: SkillSwapException) -> JSONResponse:
    """Handle custom application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.error_code,
        },
    )


@app.exception_handler(ResourceNotFoundException)
async def not_found_exception_handler(request: Request, exc: ResourceNotFoundException) -> JSONResponse:
    """Handle resource not found exceptions."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": exc.detail,
            "error_code": "RESOURCE_NOT_FOUND",
        },
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_exception_handler(request: Request, exc: UnauthorizedException) -> JSONResponse:
    """Handle unauthorized access exceptions."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": exc.detail,
            "error_code": "UNAUTHORIZED",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
    """Handle forbidden access exceptions."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": exc.detail,
            "error_code": "FORBIDDEN",
        },
    )


@app.exception_handler(ConflictException)
async def conflict_exception_handler(request: Request, exc: ConflictException) -> JSONResponse:
    """Handle resource conflict exceptions."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": exc.detail,
            "error_code": "CONFLICT",
        },
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException) -> JSONResponse:
    """Handle custom validation exceptions."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.detail,
            "error_code": "VALIDATION_ERROR",
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"],
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "error_code": "VALIDATION_ERROR",
            "errors": errors,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database-related errors."""
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected database error occurred",
            "error_code": "DATABASE_ERROR",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint to verify API is running.
    Used by load balancers and monitoring systems.
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> dict:
    """
    Root endpoint with basic API information.
    """
    return {
        "message": "Welcome to SkillSwap API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
    }


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    )
```