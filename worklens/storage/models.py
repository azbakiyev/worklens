"""
SQLAlchemy models for WorkLens local storage.
All tables store STRUCTURAL metadata only — no personal content.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ActivityEvent(Base):
    """Single window/app activity snapshot (every 5 sec)."""
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    app_name = Column(String(256), nullable=False)
    window_category = Column(String(128), nullable=True)
    activity_level = Column(String(16), default="medium")  # low/medium/high
    clipboard_type = Column(String(32), nullable=True)       # text/number/tabular/image/url
    input_method = Column(String(16), nullable=True)         # keyboard/mouse/idle
    session_id = Column(String(64), nullable=True, index=True)
    is_privacy_zone = Column(Boolean, default=False)


class DetectedPattern(Base):
    """Recurring work pattern found by the pattern engine."""
    __tablename__ = "detected_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_type = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(Integer, default=1)
    time_consumed_minutes = Column(Float, default=0.0)
    automation_score = Column(Float, default=0.0)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    status = Column(String(32), default="new")  # new/suggested/automated/dismissed


class AutomationSuggestion(Base):
    """Automation suggestion derived from a detected pattern."""
    __tablename__ = "automation_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_id = Column(Integer, nullable=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    time_save_minutes_per_week = Column(Float, default=0.0)
    roi_annual = Column(Float, default=0.0)
    implementation_tools = Column(Text, nullable=True)
    extella_task_json = Column(Text, nullable=True)
    status = Column(String(32), default="pending")  # pending/accepted/dismissed/implemented
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class MessengerIntent(Base):
    """
    Structured intent extracted from a messenger message.
    IMPORTANT: message text is NEVER stored here.
    Only the extracted structural intent is saved.
    """
    __tablename__ = "messenger_intents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source = Column(String(32), nullable=False)         # telegram/whatsapp/email
    chat_category = Column(String(64), nullable=True)   # work_group/direct/channel
    sender_role = Column(String(64), nullable=True)     # manager/colleague/client
    intent_type = Column(String(64), nullable=False)    # task/agreement/question/file/info
    has_deadline = Column(Boolean, default=False)
    deadline_dt = Column(DateTime, nullable=True)
    urgency = Column(String(16), default="medium")     # low/medium/high
    action_required = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)


class ReceivedFile(Base):
    """Metadata for a file received through a messenger."""
    __tablename__ = "received_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String(32), nullable=False)          # telegram/whatsapp/email
    file_type = Column(String(32), nullable=True)        # pdf/xlsx/docx/image/voice
    document_category = Column(String(64), nullable=True)  # invoice/proposal/contract/report
    file_hash = Column(String(64), nullable=True, unique=True)
    local_path = Column(String(512), nullable=True)
    processed = Column(Boolean, default=False)
    extella_result_json = Column(Text, nullable=True)
