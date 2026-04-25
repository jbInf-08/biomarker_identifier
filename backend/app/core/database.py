"""
Database connection and session management for the Cancer Biomarker Identifier.

This module handles database connections, session management, and provides
utilities for database operations.
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, List, Tuple

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite configuration for development
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DEBUG,
    )
else:
    # PostgreSQL configuration for production
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        echo=settings.DEBUG,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models (primary metadata for Alembic + init_db).
# Note: ``app.models.clinical`` and ``app.models.monitoring`` define separate
# legacy ``Base`` instances; those tables are not created by init_db() unless
# their models are migrated to import ``Base`` from this module. See
# ``docs/backend/DATABASE_AND_MIGRATIONS.md``.
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: yields one session per request and closes it afterward.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Non-request code (tasks, services): caller must db.commit() / db.rollback();
    session is always closed on exit.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


async def init_db():
    """Initialize database tables."""
    try:
        # Import all models to ensure they are registered
        from ..models.biomarker_model import BiomarkerResult
        from ..models.data_model import ClinicalData, ExpressionData
        from ..models.federated import (  # noqa: F401
            FederatedEvaluation,
            FederatedGlobalModel,
            FederatedModel,
            FederatedParticipant,
            FederatedRound,
        )
        from ..models.platform_models import (  # noqa: F401
            AuditLog,
            ComplianceChecklistItem,
            FederatedIdempotency,
            InterpretationSnapshot,
            ProjectMember,
            ResearchProject,
            ServiceApiKey,
            SparkJob,
            WebhookDeliveryLog,
            WebhookSubscription,
        )
        from ..models.run_model import AnalysisRun
        from ..models.tenant_model import Tenant
        from ..models.user_model import User  # noqa: F401 — register users table for FKs

        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        _ensure_schema_patches()

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def _ensure_schema_patches() -> None:
    """Add columns introduced after first deploy (SQLite dev / simple ALTER)."""
    try:
        insp = inspect(engine)
        patches: List[Tuple[str, str, str]] = [
            ("users", "tenant_id", "VARCHAR"),
            ("analysis_runs", "tenant_id", "VARCHAR"),
        ]
        for table, col, coltype in patches:
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            if col in existing:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
            logger.info("Schema patch: added %s.%s", table, col)
    except Exception as e:
        logger.warning("Schema patch skipped or failed: %s", e)


def close_db():
    """Close database connections."""
    engine.dispose()
    logger.info("Database connections closed")


# Database utilities
def check_db_connection() -> bool:
    """Check if database connection is working."""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def get_db_info() -> dict:
    """Get database information."""
    try:
        with get_db_context() as db:
            # Get table information
            tables = []
            for table_name in Base.metadata.tables.keys():
                table = Base.metadata.tables[table_name]
                tables.append({"name": table_name, "columns": len(table.columns)})

            return {
                "database_url": settings.DATABASE_URL,
                "tables": tables,
                "connection_status": "connected",
            }
    except Exception as e:
        return {
            "database_url": settings.DATABASE_URL,
            "tables": [],
            "connection_status": f"error: {str(e)}",
        }


# Database migration utilities
def create_migration_script():
    """Create a new migration script."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    migration_file = f"migrations/migration_{timestamp}.py"

    os.makedirs("migrations", exist_ok=True)

    with open(migration_file, "w") as f:
        f.write(
            f'''"""
Migration script created on {datetime.now().isoformat()}

This migration script should be updated with the necessary database changes.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '{timestamp}'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Upgrade database schema."""
    # Add your migration code here
    pass

def downgrade():
    """Downgrade database schema."""
    # Add your downgrade code here
    pass
'''
        )

    logger.info(f"Migration script created: {migration_file}")
    return migration_file


def run_migrations():
    """Run database migrations."""
    try:
        # This would use Alembic for proper migration management
        # For now, just recreate tables
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        raise


# Database backup utilities
def backup_database(backup_path: str = None):
    """Create database backup."""
    if backup_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/biomarker_db_backup_{timestamp}.db"

    os.makedirs("backups", exist_ok=True)

    try:
        if settings.DATABASE_URL.startswith("sqlite"):
            # For SQLite, just copy the file
            import shutil

            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            shutil.copy2(db_path, backup_path)
        else:
            # For PostgreSQL, use pg_dump
            import subprocess

            db_url = settings.DATABASE_URL
            # Extract connection details from URL
            # This is a simplified version - in production, use proper pg_dump
            subprocess.run(
                [
                    "pg_dump",
                    "-h",
                    settings.POSTGRES_HOST,
                    "-p",
                    str(settings.POSTGRES_PORT),
                    "-U",
                    settings.POSTGRES_USER,
                    "-d",
                    settings.POSTGRES_DB,
                    "-f",
                    backup_path,
                ],
                env={"PGPASSWORD": settings.POSTGRES_PASSWORD},
            )

        logger.info(f"Database backup created: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"Error creating database backup: {e}")
        raise


def restore_database(backup_path: str):
    """Restore database from backup."""
    try:
        if settings.DATABASE_URL.startswith("sqlite"):
            # For SQLite, just copy the file back
            import shutil

            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            shutil.copy2(backup_path, db_path)
        else:
            # For PostgreSQL, use pg_restore
            import subprocess

            subprocess.run(
                [
                    "pg_restore",
                    "-h",
                    settings.POSTGRES_HOST,
                    "-p",
                    str(settings.POSTGRES_PORT),
                    "-U",
                    settings.POSTGRES_USER,
                    "-d",
                    settings.POSTGRES_DB,
                    backup_path,
                ],
                env={"PGPASSWORD": settings.POSTGRES_PASSWORD},
            )

        logger.info(f"Database restored from: {backup_path}")

    except Exception as e:
        logger.error(f"Error restoring database: {e}")
        raise


# Database health check
def health_check() -> dict:
    """Perform database health check."""
    try:
        # Check connection
        connection_ok = check_db_connection()

        # Get basic statistics
        with get_db_context() as db:
            from ..models.biomarker_model import BiomarkerResult
            from ..models.run_model import AnalysisRun

            total_runs = db.query(AnalysisRun).count()
            total_biomarkers = db.query(BiomarkerResult).count()

        return {
            "status": "healthy" if connection_ok else "unhealthy",
            "connection": connection_ok,
            "statistics": {
                "total_runs": total_runs,
                "total_biomarkers": total_biomarkers,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
