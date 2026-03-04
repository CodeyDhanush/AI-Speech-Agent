"""
Enterprise Voice AI Gateway — Database Models & Session
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from config import settings


# ── Engine ────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────

class Agent(Base):
    """A virtual AI agent / department routing profile."""
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    dtmf_key: Mapped[str] = mapped_column(String(5), nullable=True)   # e.g. "1", "2"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    calls_handled: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    calls: Mapped[List["CallRecord"]] = relationship("CallRecord", back_populates="agent")


class CallRecord(Base):
    """Full lifecycle record of a call session."""
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_sid: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    caller_number: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), default="inbound")   # inbound | outbound
    status: Mapped[str] = mapped_column(String(20), default="initiated")    # initiated | active | completed | failed
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # positive | neutral | negative
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recording_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="calls")
    messages: Mapped[List["TranscriptMessage"]] = relationship("TranscriptMessage", back_populates="call", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="call", cascade="all, delete-orphan")


class TranscriptMessage(Base):
    """Individual turn in a call conversation."""
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_id: Mapped[str] = mapped_column(String(36), ForeignKey("calls.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)   # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    call: Mapped["CallRecord"] = relationship("CallRecord", back_populates="messages")


class AuditLog(Base):
    """Immutable security & compliance audit trail."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("calls.id"), nullable=True)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    call: Mapped[Optional["CallRecord"]] = relationship("CallRecord", back_populates="audit_logs")


# ── Helpers ───────────────────────────────────────────────

async def get_db():
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables and seed default agents."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(Agent))
        existing = result.scalars().all()

        if not existing:
            default_agents = [
                Agent(
                    name="Aria",
                    department="Customer Support",
                    dtmf_key="1",
                    system_prompt=(
                        "You are Aria, a professional enterprise customer support AI. "
                        "Help resolve product issues, billing queries, and service requests with empathy. "
                        "Keep answers concise and professional. Escalate if needed."
                    ),
                ),
                Agent(
                    name="Maxwell",
                    department="Sales & Partnerships",
                    dtmf_key="2",
                    system_prompt=(
                        "You are Maxwell, an enterprise sales AI assistant. "
                        "Answer product pricing, licensing, and partnership inquiries. "
                        "Be persuasive yet accurate, always maintaining professionalism."
                    ),
                ),
                Agent(
                    name="Priya",
                    department="Technical Support",
                    dtmf_key="3",
                    system_prompt=(
                        "You are Priya, an enterprise technical support specialist AI. "
                        "Diagnose and resolve technical issues step-by-step. "
                        "Use clear, jargon-free language unless the caller is technical."
                    ),
                ),
                Agent(
                    name="Operator",
                    department="General Inquiries",
                    dtmf_key="0",
                    system_prompt=(
                        "You are a professional enterprise AI operator. "
                        "Handle general inquiries, direct callers to the right department, "
                        "and provide company information politely and efficiently."
                    ),
                ),
            ]
            session.add_all(default_agents)
            await session.commit()
