"""WorkLens — main entry point for development testing."""
import logging
import time
import signal
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("worklens")


def main() -> None:
    logger.info("🔵 WorkLens starting...")

    from worklens.storage.database import DatabaseManager
    from worklens.capture.capture_module import ActivityCapture

    # Init DB
    db = DatabaseManager()
    logger.info(f"✅ Database ready at {db.db_path}")

    # Init capture (5 sec interval)
    capture = ActivityCapture(db_manager=db, interval=5.0)
    capture.start()
    logger.info("✅ Capture started — polling every 5 seconds")
    logger.info("   Press Ctrl+C to stop\n")

    def on_shutdown(sig, frame):
        logger.info("\n🛑 Shutting down WorkLens...")
        capture.stop()
        _print_stats(db)
        sys.exit(0)

    signal.signal(signal.SIGINT, on_shutdown)
    signal.signal(signal.SIGTERM, on_shutdown)

    # Print stats every 30 sec
    while True:
        time.sleep(30)
        _print_stats(db)


def _print_stats(db) -> None:
    """Print quick capture statistics."""
    try:
        from sqlalchemy import text
        with db.get_session() as session:
            total = session.execute(text("SELECT COUNT(*) FROM activity_events")).scalar()
            top = session.execute(text(
                "SELECT app_name, COUNT(*) as cnt FROM activity_events "
                "GROUP BY app_name ORDER BY cnt DESC LIMIT 5"
            )).fetchall()

        logger.info(f"📊 Total events: {total}")
        for row in top:
            logger.info(f"   {row[0]:<30} {row[1]} events")
    except Exception as e:
        logger.error(f"Stats error: {e}")


if __name__ == "__main__":
    main()
