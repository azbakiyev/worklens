"""
SQLAlchemy ORM models for WorkLens local database.

PRIVACY RULES:
- ActivityEvent: stores app metadata ONLY (no window content, no keystrokes)
- MessengerIntent: stores LLM-extracted structure ONLY (no message text)
- ReceivedFile: stores file metadata and category (no file content in DB)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, Enum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActivityLevel(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    IDLE = "idle"


class ClipboardType(str, PyEnum):
    TEXT = "text"
    NUMBER = "number"
    TABULAR = "tabular"
    IMAGE = "image"
    FILE_PATH = "file_path"
    UNKNOWN = "unknown"
    EMPTY = "empty"


class IntentType(str, PyEnum):
    TASK = "task"
    AGREEMENT = "agreement"
    QUESTION = "question"
    FILE_REQUEST = "file_request"
    STATUS_UPDATE = "status_update"
    OTHER = "other"


class UrgencyLevel(str, PyEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MessengerSource(str, PyEnum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class DocumentCategory(str, PyEnum):
    INVOICE = "invoice"
    PROPOSAL = "proposal"  # commercial offer / KP
    CONTRACT = "contract"
    REPORT = "report"
    DRAWING = "drawing"    # DWG / RVT
    UNKNOWN = "unknown"


class SuggestionStatus(str, PyEnum):
    PENDING = "pending"
    SHOWN = "shown"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    IMPLEMENTED = "implemented"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ActivityEvent(Base):
    """
    One sample of active-window state (captured every N seconds).

    What IS stored:
        - app_name: e.g. "Microsoft Excel"
        - window_category: broad category e.g. "spreadsheet", "crm", "browser"
        - activity_level: keyboard/mouse activity level
        - clipboard_type: *type* of data in clipboard (not the data itself)
        - session_id: groups events into work sessions

    What is NOT stored:
        - window title (may contain personal info)
        - keystrokes
        - clipboard content
    """

    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    app_name = Column(String(128), nullable=False, index=True)
    window_category = Column(String(64), nullable=True, index=True)
    activity_level = Column(Enum(ActivityLevel), nullable=False, default=ActivityLevel.MEDIUM)
    clipboard_type = Column(Enum(ClipboardType), nullable=False, default=ClipboardType.EMPTY)
    session_id = Column(String(36), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<ActivityEvent ts={self.ts} app={self.app_name}>"


class MessengerIntent(Base):
    """
    Structured intent extracted from a messenger message by local LLM.

    Message TEXT is analysed locally and then discarded — only the
    structured result (has_task, urgency, etc.) is persisted here.
    """

    __tablename__ = "messenger_intents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source = Column(Enum(MessengerSource), nullable=False, index=True)
    chat_category = Column(String(64), nullable=True)   # work_group / direct / channel
    sender_role = Column(String(64), nullable=True)     # manager / colleague / external
    intent_type = Column(Enum(IntentType), nullable=False, default=IntentType.OTHER)
    urgency = Column(Enum(UrgencyLevel), nullable=False, default=UrgencyLevel.LOW)
    has_deadline = Column(Boolean, nullable=False, default=False)
    deadline_dt = Column(DateTime, nullable=True)
    action_required = Column(Boolean, nullable=False, default=False)
    resolved = Column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<MessengerIntent source={self.source} intent={self.intent_type} resolved={self.resolved}>"


class ReceivedFile(Base):
    """
    File received via messenger — metadata only.
    Actual file is stored in ~/WorkLens/cache/ and referenced by path.
    """

    __tablename__ = "received_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source = Column(Enum(MessengerSource), nullable=False)
    file_type = Column(String(16), nullable=True)    # pdf, xlsx, docx, jpg...
    doc_category = Column(Enum(DocumentCategory), nullable=False, default=DocumentCategory.UNKNOWN)
    file_hash = Column(String(64), nullable=True, unique=True)  # SHA-256 for dedup
    local_path = Column(String(512), nullable=True)  # temp path in ~/WorkLens/cache/
    processed = Column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<ReceivedFile source={self.source} type={self.file_type} processed={self.processed}>"


class Pattern(Base):
    """Detected automation opportunity pattern."""

    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_type = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=False)
    frequency = Column(Integer, nullable=False, default=0)       # occurrences observed
    time_min_month = Column(Float, nullable=False, default=0.0)  # estimated minutes/month
    automation_score = Column(Float, nullable=False, default=0.0)  # 0.0 – 1.0
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(32), nullable=False, default="new")   # new / suggested / automated

    def __repr__(self) -> str:
        return f"<Pattern type={self.pattern_type} score={self.automation_score:.2f}>"


class Suggestion(Base):
    """Automation suggestion derived from a Pattern."""

    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_id = Column(Integer, nullable=False, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    time_save_min_month = Column(Float, nullable=False, default=0.0)
    roi_amount = Column(Float, nullable=False, default=0.0)       # in local currency
    extella_task_json = Column(Text, nullable=True)               # JSON payload for extella
    status = Column(Enum(SuggestionStatus), nullable=False, default=SuggestionStatus.PENDING)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Suggestion title={self.title!r} status={self.status}>"
