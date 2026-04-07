"""WorkLens -- entry point."""
import logging
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

if "--setup-telegram" in sys.argv:
    for _lg in ("worklens.capture", "worklens.storage", "worklens.pattern",
                "telethon", "asyncio", "werkzeug", "urllib3"):
        logging.getLogger(_lg).setLevel(logging.CRITICAL)

logging.getLogger("worklens").setLevel(logging.DEBUG)
logger = logging.getLogger("worklens")


def main() -> None:
    logger.info("[WorkLens] Starting...")

    from worklens.storage.database import DatabaseManager
    from worklens.capture.capture_module import ActivityCapture
    from worklens.pattern.pattern_engine import PatternEngine
    from worklens.config_manager import ConfigManager
    from worklens.dashboard.app import start_dashboard

    config = ConfigManager()
    db     = DatabaseManager()
    logger.info(f"[OK] Database: {db.db_path}")

    capture = ActivityCapture(db_manager=db, interval=5.0)

    if "--setup-telegram" not in sys.argv:
        capture.start()
        logger.info("[OK] Capture started")

    pattern_engine = PatternEngine(db)
    tg_monitor = _setup_telegram(db, config)

    if tg_monitor:
        tg_monitor.start()
        logger.info("[OK] Telegram monitor started")
    else:
        logger.info("[--] Telegram skipped  (run with --setup-telegram to configure)")

    if "--setup-telegram" in sys.argv:
        capture.start()
        logger.info("[OK] Capture started")

    # Start dashboard
    start_dashboard(db, config, capture=capture, tg_monitor=tg_monitor)
    logger.info("[OK] Dashboard at http://localhost:7771")

    def on_shutdown(sig, frame):
        logger.info("[WorkLens] Shutting down...")
        capture.stop()
        if tg_monitor:
            tg_monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  on_shutdown)
    signal.signal(signal.SIGTERM, on_shutdown)

    logger.info("   Press Ctrl+C to stop\n")
    tick = 0
    while True:
        time.sleep(30)
        tick += 1
        _print_stats(db)
        if tick % 10 == 0:
            logger.info("[WorkLens] Running pattern analysis...")
            try:
                report = pattern_engine.run(days_back=14, min_frequency=2)
                if report.sequence_patterns or report.time_patterns:
                    logger.info("\n" + report.summary())
                else:
                    logger.info("Pattern analysis: not enough data yet")
            except Exception as e:
                logger.error(f"Pattern analysis error: {e}")


def _setup_telegram(db, config):
    from pathlib import Path
    SESSION_PATH = Path.home() / ".worklens" / "telegram.session"
    run_setup    = "--setup-telegram" in sys.argv
    already_configured = SESSION_PATH.exists() and config.has("telegram_api_id")
    if not already_configured and not run_setup:
        return None
    if not config.has("telegram_api_id") or not config.has("openai_api_key"):
        if not run_setup:
            logger.info("Telegram not configured. Run: python main.py --setup-telegram")
            return None
        print("\n[Setup] Telegram API keys")
        print("  Get them at: https://my.telegram.org -> API development tools\n")
        api_id   = input("  api_id   : ").strip()
        api_hash = input("  api_hash : ").strip()
        config.set("telegram_api_id",   int(api_id))
        config.set("telegram_api_hash", api_hash)
        print("\n[Setup] OpenAI API key")
        openai_key = input("  OpenAI key (sk-...): ").strip()
        config.set("openai_api_key", openai_key)
    from worklens.messenger.telegram_monitor import TelegramMonitor
    monitor = TelegramMonitor(
        db_manager     = db,
        api_id         = config.get("telegram_api_id"),
        api_hash       = config.get("telegram_api_hash"),
        openai_api_key = config.get("openai_api_key"),
    )
    if run_setup or not SESSION_PATH.exists():
        if not monitor.setup():
            return None
    return monitor


def _print_stats(db) -> None:
    try:
        from sqlalchemy import text
        with db.get_session() as session:
            total   = session.execute(text("SELECT COUNT(*) FROM activity_events")).scalar()
            top     = session.execute(text(
                "SELECT app_name, COUNT(*) as cnt FROM activity_events "
                "GROUP BY app_name ORDER BY cnt DESC LIMIT 5"
            )).fetchall()
            intents = session.execute(text("SELECT COUNT(*) FROM messenger_intents")).scalar() or 0
            files   = session.execute(text("SELECT COUNT(*) FROM received_files")).scalar()   or 0
        logger.info(f"[Stats] Events: {total} | Intents: {intents} | Files: {files}")
        for row in top:
            logger.info(f"   {row[0]:<30} {row[1]} events")
    except Exception as e:
        logger.error(f"Stats error: {e}")


if __name__ == "__main__":
    main()
