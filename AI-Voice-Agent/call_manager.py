"""
Enterprise Voice AI Gateway — In-Memory Call State Manager
Tracks live call sessions and broadcasts updates over WebSocket.
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class LiveCall:
    """Runtime state of an active call."""
    call_sid: str
    caller: str
    direction: str = "inbound"
    status: str = "ringing"          # ringing | active | on-hold | ended
    agent_name: str = "Unassigned"
    department: str = "—"
    db_call_id: Optional[str] = None
    agent_id: Optional[str] = None
    history: List[dict] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    turn_count: int = 0
    context: Optional[object] = None  # CallContext from smart_router

    def to_dict(self) -> dict:
        elapsed = (datetime.now(timezone.utc) - self.started_at).seconds
        return {
            "call_sid": self.call_sid,
            "caller": self.caller,
            "direction": self.direction,
            "status": self.status,
            "agent_name": self.agent_name,
            "department": self.department,
            "turn_count": self.turn_count,
            "duration": elapsed,
        }


class CallManager:
    """Thread-safe, async call session registry with WebSocket fan-out."""

    def __init__(self):
        self._calls: Dict[str, LiveCall] = {}
        self._ws_clients: List = []
        self._lock = asyncio.Lock()

    # ── Registration ──────────────────────────────────────

    async def register(self, call: LiveCall):
        async with self._lock:
            self._calls[call.call_sid] = call
            logger.info(f"📞 Call registered: {call.call_sid} from {call.caller}")
        await self._broadcast("call_started", call.to_dict())

    async def update(self, call_sid: str, **kwargs):
        async with self._lock:
            call = self._calls.get(call_sid)
            if not call:
                return
            for k, v in kwargs.items():
                if hasattr(call, k):
                    setattr(call, k, v)
        await self._broadcast("call_updated", self._calls[call_sid].to_dict())

    async def end_call(self, call_sid: str):
        async with self._lock:
            call = self._calls.pop(call_sid, None)
        if call:
            logger.info(f"✅ Call ended: {call_sid}")
            await self._broadcast("call_ended", {"call_sid": call_sid})

    def get(self, call_sid: str) -> Optional[LiveCall]:
        return self._calls.get(call_sid)

    def all_active(self) -> List[dict]:
        return [c.to_dict() for c in self._calls.values()]

    # ── WebSocket ─────────────────────────────────────────

    def add_ws_client(self, ws):
        self._ws_clients.append(ws)

    def remove_ws_client(self, ws):
        if ws in self._ws_clients:
            self._ws_clients.remove(ws)

    async def _broadcast(self, event: str, payload: dict):
        import json
        message = json.dumps({"event": event, "data": payload})
        dead = []
        for ws in list(self._ws_clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove_ws_client(ws)

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        calls = list(self._calls.values())
        return {
            "active_calls": len(calls),
            "inbound": sum(1 for c in calls if c.direction == "inbound"),
            "outbound": sum(1 for c in calls if c.direction == "outbound"),
            "on_hold": sum(1 for c in calls if c.status == "on-hold"),
        }


# Global singleton
call_manager = CallManager()
