"""WorkLens — main entry point for development testing."""
import logging
import time
import signal
import sys

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
    from worklens.pattern.pattern_engine import PatternEngine

    db = DatabaseManager()
    logger.info(f"✅ Database ready at {db.db_path}")

    capture = ActivityCapture(db_manager=db, interval=5.0)
    capture.start()
    logger.info("✅ Capture started — polling every 5 seconds")
    logger.info("   Press Ctrl+C to stop\n")

    pattern_engine = PatternEngine(db)

    def on_shutdown(sig, frame):
        logger.info("\n🛑 Shutting down WorkLens...")
        capture.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_shutdown)
    signal.signal(signal.SIGTERM, on_shutdown)

    tick = 0
    while True:
        time.sleep(30)
        tick += 1
        _print_stats(db)

        # Run pattern analysis every 5 minutes (10 ticks × 30 sec)
        if tick % 10 == 0:
            logger.info("🔍 Running pattern analysis...")
            try:
                report = pattern_engine.run(days_back=14, min_frequency=2)
                logger.info("\n" + report.summary())
            except Exception as e:
                logger.error(f"Pattern analysis failed: {e}")


def _print_stats(db) -> None:
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
