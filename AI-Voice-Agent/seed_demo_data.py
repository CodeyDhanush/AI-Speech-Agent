# -*- coding: utf-8 -*-
import sys, io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
"""
Enterprise Voice AI Gateway — Demo Data Seeder
Run this once after first boot to populate the dashboard with
realistic historical call records for demonstration purposes.
"""
import asyncio
import random
import uuid
from datetime import datetime, timezone, timedelta

from database import AsyncSessionLocal, init_db, Agent, CallRecord, TranscriptMessage, AuditLog
from sqlalchemy import select


SENTIMENTS = ["positive", "neutral", "negative"]
STATUSES   = ["completed", "completed", "completed", "failed", "busy"]
DIRECTIONS = ["inbound", "inbound", "inbound", "outbound"]

SAMPLE_CALLERS = [
    "+919876543210", "+918765432109", "+917654321098",
    "+916543210987", "+915432109876", "+914321098765",
    "+919123456789", "+918012345678", "+917901234567",
]

SAMPLE_CONVERSATIONS = [
    [
        ("user", "Hi, I'm having trouble logging into my account."),
        ("assistant", "I'm sorry to hear that. Can you please provide your registered email so I can look into this?"),
        ("user", "Sure, it's john.doe@example.com"),
        ("assistant", "Thank you John. I can see your account. It appears your password was recently reset. I'll send a recovery link to your email right away."),
        ("user", "Perfect, thank you so much!"),
        ("assistant", "You're welcome. Is there anything else I can help you with today?"),
    ],
    [
        ("user", "I'd like to know about your enterprise pricing plans."),
        ("assistant", "Absolutely! Our Enterprise plan starts at $999/month and includes unlimited users, dedicated support, and SLA guarantees. Would you like a custom quote?"),
        ("user", "Yes, we have about 500 users."),
        ("assistant", "For 500 users, I can offer you a tailored package at around $1,800/month with a 20% annual discount. Shall I connect you with our sales team?"),
        ("user", "That sounds reasonable, please do."),
    ],
    [
        ("user", "Your service is terrible! I've been waiting for 3 days for a resolution."),
        ("assistant", "I sincerely apologize for the inconvenience. Your frustration is completely understandable. Let me escalate this immediately to our priority support team."),
        ("user", "This is unacceptable."),
        ("assistant", "I completely agree this is not up to our standards. I'm marking your ticket as Priority 1. A senior engineer will contact you within 2 hours."),
    ],
    [
        ("user", "I need help setting up the API integration."),
        ("assistant", "Of course! Which API are you integrating with? REST, GraphQL, or our WebSocket streaming API?"),
        ("user", "The REST API for data exports."),
        ("assistant", "Great choice. The REST endpoint is at api.example.com/v2/export. You'll need your API key from the developer console. Shall I walk you through the authentication flow?"),
        ("user", "Yes please."),
        ("assistant", "First, generate a JWT token using your client ID and secret. Include it in the Authorization header as 'Bearer <token>'. The token expires in 3600 seconds."),
    ],
]

SUMMARIES = [
    "Caller had account access issues. Agent provided a password recovery link. Issue resolved successfully.",
    "Enterprise pricing inquiry for 500-user organization. Quoted $1,800/month with annual discount. Sales follow-up scheduled.",
    "Frustrated caller with 3-day unresolved issue. Escalated to Priority 1. Senior engineer assigned.",
    "API integration assistance. Agent explained REST endpoint authentication using JWT tokens. Customer guided through setup.",
    "General product inquiry. Information provided and documentation link shared.",
    "Billing discrepancy reported. Ticket logged for finance team review. Estimated 24-hour resolution.",
]


async def seed():
    print("[*] Seeding demo data...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Get agents
        result = await session.execute(select(Agent))
        agents = result.scalars().all()
        if not agents:
            print("[!] No agents found. Run the server first to create default agents.")
            return

        # Generate calls over the past 7 days
        now = datetime.now(timezone.utc)
        created = 0

        for day_offset in range(7):
            day = now - timedelta(days=day_offset)
            # More calls on weekdays
            num_calls = random.randint(4, 12) if day.weekday() < 5 else random.randint(1, 4)

            for _ in range(num_calls):
                hour   = random.randint(8, 20)
                minute = random.randint(0, 59)
                started = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

                agent    = random.choice(agents)
                caller   = random.choice(SAMPLE_CALLERS)
                direction = random.choice(DIRECTIONS)
                status   = random.choice(STATUSES)
                duration = random.uniform(30, 280) if status == "completed" else random.uniform(5, 30)
                sentiment = random.choice(SENTIMENTS)
                conv     = random.choice(SAMPLE_CONVERSATIONS)
                summary  = random.choice(SUMMARIES)

                call = CallRecord(
                    id=str(uuid.uuid4()),
                    call_sid="CA" + uuid.uuid4().hex[:32],
                    caller_number=caller,
                    direction=direction,
                    status=status,
                    agent_id=agent.id,
                    duration_seconds=round(duration, 1),
                    sentiment=sentiment,
                    summary=summary,
                    started_at=started,
                    ended_at=started + timedelta(seconds=duration),
                )
                session.add(call)
                await session.flush()

                # Transcript
                for role, content in conv:
                    msg = TranscriptMessage(
                        call_id=call.id,
                        role=role,
                        content=content,
                        confidence=round(random.uniform(0.82, 0.99), 3) if role == "user" else None,
                        timestamp=started + timedelta(seconds=random.randint(1, int(duration))),
                    )
                    session.add(msg)

                # Audit
                audit1 = AuditLog(call_id=call.id, event="call_initiated", details={"from": caller}, timestamp=started)
                audit2 = AuditLog(call_id=call.id, event="agent_assigned",
                                  details={"agent": agent.name, "department": agent.department},
                                  timestamp=started + timedelta(seconds=2))
                session.add_all([audit1, audit2])

                # Update agent call count
                agent.calls_handled += 1
                created += 1

        await session.commit()
        print(f"[OK] Seeded {created} demo calls across 7 days.")


if __name__ == "__main__":
    asyncio.run(seed())
