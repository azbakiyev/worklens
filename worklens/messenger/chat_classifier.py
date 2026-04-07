"""Chat Classifier -- classifies Telegram dialogs as work or personal."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Set

logger = logging.getLogger(__name__)

WORK_KEYWORDS = {
    "команда", "team", "отдел", "dept", "проект", "project",
    "office", "офис", "работа", "work", "закуп", "омто",
    "продаж", "sales", "marketing", "hr", "бухгал", "finance",
    "support", "тех", "task", "задач", "devops", "договор"
}
PERSONAL_KEYWORDS = {
    "семья", "family", "друз", "friends", "личн",
    "дом", "home", "мама", "папа", "родител"
}
MIN_WORK_GROUP_SIZE = 3


@dataclass
class ChatInfo:
    chat_id: int
    title: str
    chat_type: str
    member_count: int = 0
    is_suggested_work: bool = False


class ChatClassifier:
    """Classifies dialogs and manages the approved chat list in SQLite."""

    def __init__(self, db_manager) -> None:
        self.db = db_manager

    def classify(self, chats: List[ChatInfo]) -> List[ChatInfo]:
        for chat in chats:
            chat.is_suggested_work = self._is_work(chat)
        return chats

    def _is_work(self, chat: ChatInfo) -> bool:
        title = chat.title.lower()
        if chat.chat_type in ("saved", "direct"):
            return False
        if any(kw in title for kw in PERSONAL_KEYWORDS):
            return False
        if any(kw in title for kw in WORK_KEYWORDS):
            return True
        if chat.chat_type == "group" and chat.member_count >= MIN_WORK_GROUP_SIZE:
            return True
        return False

    def save_approved(self, chats: List[ChatInfo]) -> None:
        from sqlalchemy import text
        with self.db.get_session() as session:
            session.execute(text("DELETE FROM approved_chats"))
            for c in chats:
                session.execute(text("""
                    INSERT INTO approved_chats
                        (chat_id, title, chat_type, member_count, approved, created_at)
                    VALUES (:cid, :title, :ctype, :cnt, 1, :ts)
                """), {
                    "cid": c.chat_id, "title": c.title,
                    "ctype": c.chat_type, "cnt": c.member_count,
                    "ts": datetime.utcnow().isoformat(),
                })
        logger.info(f"Saved {len(chats)} approved chats")

    def load_approved_ids(self) -> Set[int]:
        from sqlalchemy import text
        try:
            with self.db.get_session() as session:
                rows = session.execute(
                    text("SELECT chat_id FROM approved_chats WHERE approved = 1")
                ).fetchall()
                return {r[0] for r in rows}
        except Exception as e:
            logger.error(f"Failed to load approved chats: {e}")
            return set()

    def has_approved_chats(self) -> bool:
        return bool(self.load_approved_ids())
