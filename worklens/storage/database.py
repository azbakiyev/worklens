"""
Database manager for WorkLens local SQLite storage.
All data is stored locally — never sent to remote servers.
"""
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from worklens.storage.models import Base

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".worklens" / "data.db"


class DatabaseManager:
    """Manages the local SQLite database for WorkLens."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self._SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=False,  # keeps ORM attrs accessible after session.close()
        )
        self._init_db()
        logger.info(f"Database initialized at {self.db_path}")

    def _init_db(self) -> None:
        """Create all tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)
        logger.debug("All tables ensured")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Context manager that yields a database session with auto-commit/rollback."""
        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error, rolled back: {e}")
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        """Return True if the database is reachable."""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"DB health check failed: {e}")
            return False

    def get_event_count(self) -> int:
        """Return total number of activity events recorded."""
        try:
            with self.get_session() as session:
                return session.execute(
                    text("SELECT COUNT(*) FROM activity_events")
                ).scalar() or 0
        except Exception:
            return 0
