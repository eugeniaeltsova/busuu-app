from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, ForeignKey, JSON, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    busuu_user_id   = Column(String(64),  nullable=True)
    language        = Column(String(8),   default="es")
    native_language = Column(String(8),   default="en")   # learner's native language
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    last_sync       = Column(DateTime(timezone=True), nullable=True)

    vocab_items     = relationship("VocabItem",    back_populates="user", cascade="all, delete-orphan")
    grammar_topics  = relationship("GrammarTopic", back_populates="user", cascade="all, delete-orphan")
    exercises       = relationship("Exercise",     back_populates="user", cascade="all, delete-orphan")


class VocabItem(Base):
    __tablename__ = "vocab_items"
    __table_args__ = (
        UniqueConstraint("user_id", "busuu_item_id", name="uq_user_vocab"),
    )

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    busuu_item_id   = Column(String(64),  nullable=True)
    entity_id       = Column(String(64),  nullable=True)
    word            = Column(String(512), nullable=False)
    translation     = Column(String(512), nullable=True)
    image_url       = Column(Text,        nullable=True)
    strength        = Column(Float,       default=0.0)   # 0.0–1.0 normalised
    strength_raw    = Column(Integer,     default=0)     # 0–5 from Busuu
    saved           = Column(Boolean,     default=False)
    last_reviewed   = Column(DateTime(timezone=True), nullable=True)
    raw             = Column(JSON,        nullable=True)

    user = relationship("User", back_populates="vocab_items")


class GrammarTopic(Base):
    __tablename__ = "grammar_topics"
    __table_args__ = (
        UniqueConstraint("user_id", "busuu_topic_id", name="uq_user_grammar"),
    )

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    busuu_topic_id  = Column(String(128), nullable=True)
    unit_name       = Column(String(256), nullable=False)
    topic_name      = Column(String(256), nullable=True)   # category name
    cert_level      = Column(String(4),   nullable=True)
    strength        = Column(Integer,     default=0)       # 0–4 from Busuu
    strength_norm   = Column(Float,       default=0.0)     # 0.0–1.0
    percentage      = Column(Integer,     default=0)       # 0–100
    completed       = Column(Boolean,     default=False)
    raw             = Column(JSON,        nullable=True)

    user = relationship("User", back_populates="grammar_topics")


class Exercise(Base):
    __tablename__ = "exercises"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    exercise_type   = Column(String(64), nullable=False)   # short_story | gap_text | translation | dialogue
    prompt_summary  = Column(Text,  nullable=True)
    content         = Column(Text,  nullable=False)
    answer_key      = Column(Text,  nullable=True)
    difficulty      = Column(String(8), nullable=True)     # A1–C2
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    completed       = Column(Boolean, default=False)
    user_answer     = Column(Text, nullable=True)
    feedback        = Column(Text, nullable=True)
    raw_response     = Column(JSON, nullable=True)
    structured_data  = Column(JSON, nullable=True)  # structured exercise data for UI rendering

    user = relationship("User", back_populates="exercises")
