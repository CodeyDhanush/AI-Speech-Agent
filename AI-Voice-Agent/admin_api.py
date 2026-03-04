"""
Enterprise Voice AI Gateway — Admin REST API
Provides endpoints for dashboard, analytics, agent management, and audit logs.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel

from database import get_db, Agent, CallRecord, TranscriptMessage, AuditLog
from call_manager import call_manager

router = APIRouter(prefix="/api", tags=["Admin API"])


# ── Schemas ───────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    department: str
    dtmf_key: str
    system_prompt: str


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class OutboundCallRequest(BaseModel):
    to: str
    agent_dtmf: str = "0"


# ── Dashboard Stats ───────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Real-time dashboard summary."""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total calls today
    q = await db.execute(
        select(func.count(CallRecord.id)).where(CallRecord.started_at >= today)
    )
    calls_today = q.scalar() or 0

    # Total completed
    q = await db.execute(
        select(func.count(CallRecord.id)).where(
            CallRecord.status == "completed",
            CallRecord.started_at >= today,
        )
    )
    calls_completed = q.scalar() or 0

    # Average duration
    q = await db.execute(
        select(func.avg(CallRecord.duration_seconds)).where(
            CallRecord.duration_seconds.is_not(None),
            CallRecord.started_at >= today,
        )
    )
    avg_duration = round(q.scalar() or 0, 1)

    # Sentiment breakdown
    sentiments = {}
    for label in ("positive", "neutral", "negative"):
        q = await db.execute(
            select(func.count(CallRecord.id)).where(
                CallRecord.sentiment == label,
                CallRecord.started_at >= today,
            )
        )
        sentiments[label] = q.scalar() or 0

    # Total stored calls
    q = await db.execute(select(func.count(CallRecord.id)))
    total_calls = q.scalar() or 0

    # Agent count
    q = await db.execute(select(func.count(Agent.id)).where(Agent.is_active == True))
    active_agents = q.scalar() or 0

    return {
        "calls_today": calls_today,
        "calls_completed": calls_completed,
        "avg_duration_seconds": avg_duration,
        "sentiment": sentiments,
        "total_calls": total_calls,
        "active_agents": active_agents,
        "live": call_manager.stats(),
        "live_calls": call_manager.all_active(),
    }


# ── Call Records ──────────────────────────────────────────

@router.get("/calls")
async def list_calls(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    q = select(CallRecord).order_by(desc(CallRecord.started_at))
    if status:
        q = q.where(CallRecord.status == status)
    q = q.offset(offset).limit(page_size)

    result = await db.execute(q)
    calls = result.scalars().all()

    # count
    cq = select(func.count(CallRecord.id))
    if status:
        cq = cq.where(CallRecord.status == status)
    count_result = await db.execute(cq)
    total = count_result.scalar() or 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "calls": [
            {
                "id": c.id,
                "call_sid": c.call_sid,
                "caller": c.caller_number,
                "direction": c.direction,
                "status": c.status,
                "sentiment": c.sentiment,
                "duration": c.duration_seconds,
                "summary": c.summary,
                "agent_id": c.agent_id,
                "started_at": c.started_at.isoformat() if c.started_at else None,
            }
            for c in calls
        ],
    }


@router.get("/calls/{call_id}/transcript")
async def get_transcript(call_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TranscriptMessage)
        .where(TranscriptMessage.call_id == call_id)
        .order_by(TranscriptMessage.timestamp)
    )
    messages = result.scalars().all()

    call_result = await db.execute(
        select(CallRecord).where(CallRecord.id == call_id)
    )
    call = call_result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return {
        "call_id": call_id,
        "call_sid": call.call_sid,
        "caller": call.caller_number,
        "summary": call.summary,
        "sentiment": call.sentiment,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "confidence": m.confidence,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ],
    }


# ── Agents ────────────────────────────────────────────────

@router.get("/agents")
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.dtmf_key))
    agents = result.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "department": a.department,
            "dtmf_key": a.dtmf_key,
            "system_prompt": a.system_prompt,
            "is_active": a.is_active,
            "calls_handled": a.calls_handled,
        }
        for a in agents
    ]


@router.post("/agents")
async def create_agent(payload: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent = Agent(**payload.model_dump())
    db.add(agent)
    await db.flush()
    return {"id": agent.id, "name": agent.name}


@router.patch("/agents/{agent_id}")
async def update_agent(
    agent_id: str, payload: AgentUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(agent, k, v)
    return {"success": True}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    return {"success": True}


# ── Analytics ─────────────────────────────────────────────

@router.get("/analytics/calls-over-time")
async def calls_over_time(days: int = 7, db: AsyncSession = Depends(get_db)):
    """Daily call volume for the past N days."""
    now = datetime.now(timezone.utc)
    data = []
    for i in range(days - 1, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        q = await db.execute(
            select(func.count(CallRecord.id)).where(
                CallRecord.started_at >= day_start,
                CallRecord.started_at <= day_end,
            )
        )
        data.append({"date": day_start.strftime("%b %d"), "count": q.scalar() or 0})
    return data


@router.get("/analytics/department-breakdown")
async def dept_breakdown(db: AsyncSession = Depends(get_db)):
    """Call count per agent/department."""
    result = await db.execute(select(Agent).where(Agent.is_active == True))
    agents = result.scalars().all()
    return [
        {"name": a.name, "department": a.department, "calls": a.calls_handled}
        for a in agents
    ]


# ── Audit Log ─────────────────────────────────────────────

@router.get("/audit")
async def get_audit_log(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .offset(offset)
        .limit(page_size)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "event": l.event,
            "details": l.details,
            "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ]


# ── WebSocket — Live Feed ──────────────────────────────────

@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket):
    """Real-time call events pushed to dashboard clients."""
    await websocket.accept()
    call_manager.add_ws_client(websocket)
    try:
        # Send initial state
        import json
        await websocket.send_text(json.dumps({
            "event": "init",
            "data": {
                "live_calls": call_manager.all_active(),
                "stats": call_manager.stats(),
            }
        }))
        while True:
            # Keep alive — wait for disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        call_manager.remove_ws_client(websocket)
    except Exception:
        call_manager.remove_ws_client(websocket)
