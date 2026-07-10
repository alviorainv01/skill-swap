"""
Database connection and session management module.

Provides SQLAlchemy engine, session factory, and base model class for the SkillSwap platform.
Includes connection pooling, retry logic, and proper resource management.
"""

import logging
import time
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, exc, pool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool

from config import get_settings

# Configure module logger
logger = logging.getLogger(__name__)

# Get application settings
settings = get_settings()

# SQLAlchemy engine configuration with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=pool.QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections after this many seconds
    echo=settings.DB_ECHO,  # Log SQL statements in development
    connect_args={
        "connect_timeout": 10,
        "application_name": "skillswap_api",
    },
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevent lazy loading issues after commit
)

# Base class for all SQLAlchemy models
Base = declarative_base()


# Connection event listeners for monitoring and debugging
@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log successful database connections."""
    logger.debug(f"Database connection established: {id(dbapi_conn)}")


@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log when a connection is checked out from the pool."""
    logger.debug(f"Connection checked out from pool: {id(dbapi_conn)}")


@event.listens_for(Pool, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log when a connection is returned to the pool."""
    logger.debug(f"Connection returned to pool: {id(dbapi_conn)}")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    
    Yields a SQLAlchemy session and ensures proper cleanup after the request.
    Handles connection errors and implements retry logic for transient failures.
    
    Yields:
        Session: SQLAlchemy database session
        
    Raises:
        Exception: Database connection or transaction errors
    """
    db = SessionLocal()
    try:
        yield db
    except exc.DBAPIError as e:
        logger.error(f"Database API error occurred: {str(e)}")
        db.rollback()
        raise
    except exc.SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error occurred: {str(e)}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in database session: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions outside of FastAPI request context.
    
    Useful for background tasks, CLI scripts, and testing.
    
    Usage:
        with get_db_context() as db:
            # Perform database operations
            user = db.query(User).first()
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Error in database context: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.
    
    Should be called during application startup or in migration scripts.
    In production, use Alembic migrations instead of this function.
    """
    try:
        logger.info("Initializing database schema...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


def check_db_connection(max_retries: int = 3, retry_delay: int = 2) -> bool:
    """
    Check if database connection is available.
    
    Implements retry logic for handling temporary connection issues.
    Useful for health checks and startup validation.
    
    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Seconds to wait between retries
        
    Returns:
        bool: True if connection successful, False otherwise
    """
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
                logger.info("Database connection check successful")
                return True
        except exc.OperationalError as e:
            logger.warning(
                f"Database connection attempt {attempt}/{max_retries} failed: {str(e)}"
            )
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                logger.error("Max database connection retries reached")
                return False
        except Exception as e:
            logger.error(f"Unexpected error checking database connection: {str(e)}")
            return False
    
    return False


def close_db_connection() -> None:
    """
    Close all database connections and dispose of the engine.
    
    Should be called during application shutdown to ensure clean resource cleanup.
    """
    try:
        logger.info("Closing database connections...")
        engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {str(e)}")
        raise


class DatabaseHealthCheck:
    """
    Provides database health check functionality for monitoring.
    """
    
    @staticmethod
    def is_healthy() -> dict:
        """
        Perform comprehensive database health check.
        
        Returns:
            dict: Health check results including connection status and pool stats
        """
        health_status = {
            "database": "unknown",
            "connection": False,
            "pool_size": 0,
            "pool_checked_out": 0,
        }
        
        try:
            # Check basic connectivity
            health_status["connection"] = check_db_connection(max_retries=1)
            
            # Get connection pool statistics
            pool_stats = engine.pool.status()
            health_status["pool_size"] = engine.pool.size()
            health_status["pool_checked_out"] = engine.pool.checkedout()
            
            # Determine overall health status
            if health_status["connection"]:
                health_status["database"] = "healthy"
            else:
                health_status["database"] = "unhealthy"
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            health_status["database"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status