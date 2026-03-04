import os
import uuid
import tempfile
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from config import settings
from database import get_db, CallRecord, Agent, TranscriptMessage, AuditLog
from ai_engine import transcribe_audio, generate_ai_response, analyze_sentiment, summarize_call
from call_manager import call_manager, LiveCall
from smart_router import classify_intent, CallContext, should_transfer, handle_logistics_query

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/start")
async def start_chat(db: AsyncSession = Depends(get_db)):
    """Initialize a new customer chat session."""
    call_sid = str(uuid.uuid4())
    
    # Check if we have a default agent
    result = await db.execute(select(Agent).where(Agent.dtmf_key == "0", Agent.is_active == True))
    agent = result.scalar_one_or_none()
    
    # Create a CallRecord
    call = CallRecord(
        call_sid=call_sid,
        caller_number="Web User",
        direction="inbound",
        status="active",
        agent_id=agent.id if agent else None
    )
    db.add(call)
    await db.flush()
    
    # Register live state
    live = LiveCall(
        call_sid=call_sid,
        caller="Web User",
        direction="inbound",
        status="active",
        db_call_id=call.id,
        agent_name=agent.name if agent else "Unassigned",
        department=agent.department if agent else "-",
        agent_id=agent.id if agent else None
    )
    live.context = CallContext(caller_number="Web User", original_intent="unknown", transfer_chain=[])
    await call_manager.register(live)
    
    audit = AuditLog(call_id=call.id, event="call_initiated", details={"from": "Web User"})
    db.add(audit)
    await db.commit()
    
    return {"call_sid": call_sid, "agent": agent.name if agent else "System"}

@router.post("/message")
async def send_message(
    call_sid: str = Form(...),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Process an audio message and return the AI text response."""
    live = call_manager.get(call_sid)
    if not live:
        raise HTTPException(status_code=404, detail="Session not found")
        
    call_result = await db.execute(select(CallRecord).where(CallRecord.call_sid == call_sid))
    call = call_result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call record not found")
        
    agent = None
    if call.agent_id:
        agent_result = await db.execute(select(Agent).where(Agent.id == call.agent_id))
        agent = agent_result.scalar_one_or_none()
        
    system_prompt = agent.system_prompt if agent else "You are a helpful AI assistant."
    
    # Save audio temporarily
    tmp_path = Path(tempfile.mkdtemp()) / f"{uuid.uuid4()}.webm"
    try:
        content = await audio.read()
        tmp_path.write_bytes(content)
        
        # Transcribe
        stt_result = await transcribe_audio(str(tmp_path))
        user_text = stt_result["text"]
        confidence = stt_result["confidence"]
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        user_text = ""
        confidence = 0.0
    finally:
        tmp_path.unlink(missing_ok=True)
        
    if not user_text:
        return JSONResponse({"user_text": "", "ai_response": "I couldn't hear that clearly. Could you please repeat?", "agent_name": agent.name if agent else "System"})
        
    # Save user message
    msg = TranscriptMessage(call_id=call.id, role="user", content=user_text, confidence=confidence)
    db.add(msg)
    
    # Intent and generate response
    history = live.history
    ai_reply = ""
    if live.context:
        intent_result = classify_intent(user_text)
        live.context.original_intent = intent_result.intent
        live.context.extract_entities(user_text)
        
        if intent_result.intent == "logistics":
            logistics_response = handle_logistics_query(user_text, live.context)
            if logistics_response:
                ai_reply = logistics_response
                
    if not ai_reply:
        ai_reply = await generate_ai_response(history, system_prompt, user_text)
        
    # Save assistant message
    ai_msg = TranscriptMessage(call_id=call.id, role="assistant", content=ai_reply)
    db.add(ai_msg)
    
    # Update live history
    live.history.append({"role": "user", "content": user_text})
    live.history.append({"role": "assistant", "content": ai_reply})
    live.turn_count += 1
    
    # Check for transfer
    if agent:
        transfer_needed = should_transfer(agent.department, user_text, live.turn_count)
        if transfer_needed:
            # Transfer the agent
            logger.info(f"🔄 Transfer suggested: {agent.department} → {transfer_needed.department}")
            ai_reply = f"I'm detecting you may need our {transfer_needed.department} team. Let me transfer you now to get better assistance."
            # Append transfer message
            transfer_msg = TranscriptMessage(call_id=call.id, role="assistant", content=ai_reply)
            db.add(transfer_msg)
            live.history.append({"role": "assistant", "content": ai_reply})
            
            # Find the new agent
            new_agent_result = await db.execute(select(Agent).where(Agent.dtmf_key == transfer_needed.dtmf, Agent.is_active == True))
            new_agent = new_agent_result.scalar_one_or_none()
            if new_agent:
                call.agent_id = new_agent.id
                live.agent_name = new_agent.name
                live.department = new_agent.department
                live.agent_id = new_agent.id
                
                # Append a connecting message for new agent
                connect_text = f"Hello, I'm {new_agent.name} from {new_agent.department}. How can I help you today?"
                connect_msg = TranscriptMessage(call_id=call.id, role="assistant", content=connect_text)
                db.add(connect_msg)
                live.history.append({"role": "assistant", "content": connect_text})
                
                ai_reply = f"{ai_reply}\n\n[Transferring...]\n\n{connect_text}"
                agent = new_agent
                
    await call_manager.update(call_sid, turn_count=live.turn_count)
    await db.commit()
    
    return {"user_text": user_text, "ai_response": ai_reply, "agent_name": agent.name if agent else "System"}

@router.post("/end")
async def end_chat(call_sid: str = Form(...), db: AsyncSession = Depends(get_db)):
    """End the chat session."""
    live = call_manager.get(call_sid)
    if live:
        history = live.history
        call_result = await db.execute(select(CallRecord).where(CallRecord.call_sid == call_sid))
        call = call_result.scalar_one_or_none()
        if call:
            call.status = "completed"
            call.ended_at = datetime.now(timezone.utc)
            call.duration_seconds = (call.ended_at - call.started_at).total_seconds()
            call.sentiment = await analyze_sentiment(" ".join(m["content"] for m in history if m["role"] == "user"))
            call.summary = await summarize_call(history)
            
            audit = AuditLog(call_id=call.id, event="call_ended")
            db.add(audit)
            await db.commit()
            
        await call_manager.end_call(call_sid)
        
    return {"success": True}
