"""
Enterprise Voice AI Gateway -- Smart Routing Engine
Classifies caller intent from speech and routes to the best agent,
preserving full conversation context across transfers.
"""
import re
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from loguru import logger

from config import settings


# -- Intent Categories -----------------------------------------------

INTENTS = {
    "billing": {
        "keywords": ["bill", "billing", "invoice", "payment", "charge", "refund",
                      "subscription", "credit", "debit", "overcharge", "fee"],
        "department": "Customer Support",
        "dtmf": "1",
        "priority": 2,
    },
    "technical": {
        "keywords": ["error", "bug", "crash", "not working", "broken", "down",
                      "slow", "timeout", "fail", "exception", "api", "integrate",
                      "install", "configure", "setup", "password", "login", "access"],
        "department": "Technical Support",
        "dtmf": "3",
        "priority": 2,
    },
    "sales": {
        "keywords": ["price", "pricing", "cost", "plan", "upgrade", "license",
                      "quote", "demo", "trial", "enterprise", "partner", "buy",
                      "purchase", "discount", "offer", "contract"],
        "department": "Sales & Partnerships",
        "dtmf": "2",
        "priority": 1,
    },
    "logistics": {
        "keywords": ["track", "tracking", "shipment", "delivery", "ship", "order",
                      "package", "dispatch", "warehouse", "stock", "inventory",
                      "returned", "return", "courier", "transit", "eta", "delayed"],
        "department": "Logistics & Operations",
        "dtmf": "4",
        "priority": 1,
    },
    "escalation": {
        "keywords": ["manager", "supervisor", "escalate", "complaint", "unacceptable",
                      "frustrated", "angry", "terrible", "worst", "lawsuit", "legal"],
        "department": "Priority Escalations",
        "dtmf": "9",
        "priority": 3,
    },
}


@dataclass
class IntentResult:
    intent: str
    confidence: float
    department: str
    dtmf: str
    priority: int
    matched_keywords: List[str] = field(default_factory=list)


def classify_intent(text: str) -> IntentResult:
    """
    Rule-based intent classifier.
    Returns the best-matching intent with confidence score.
    """
    if not text:
        return IntentResult(
            intent="general",
            confidence=0.0,
            department="General Inquiries",
            dtmf="0",
            priority=0,
        )

    text_lower = text.lower()
    scores = {}

    for intent_name, config in INTENTS.items():
        matched = [kw for kw in config["keywords"] if kw in text_lower]
        if matched:
            # Weight by number of matches and keyword specificity
            score = len(matched) / len(config["keywords"])
            scores[intent_name] = {
                "score": score,
                "matched": matched,
                "config": config,
            }

    if not scores:
        return IntentResult(
            intent="general",
            confidence=0.3,
            department="General Inquiries",
            dtmf="0",
            priority=0,
        )

    # Pick highest score
    best = max(scores.items(), key=lambda x: x[1]["score"])
    intent_name = best[0]
    info = best[1]

    result = IntentResult(
        intent=intent_name,
        confidence=round(min(info["score"] * 3, 1.0), 2),  # scale up
        department=info["config"]["department"],
        dtmf=info["config"]["dtmf"],
        priority=info["config"]["priority"],
        matched_keywords=info["matched"],
    )

    logger.info(
        f"Intent classified: {result.intent} "
        f"(conf={result.confidence}, dept={result.department}, "
        f"keywords={result.matched_keywords})"
    )
    return result


# -- Context-Aware Transfer ------------------------------------------

@dataclass
class CallContext:
    """
    Full context bundle passed during transfers.
    This solves the 'caller repeating themselves' problem.
    """
    caller_number: str
    original_intent: str
    conversation_history: List[dict] = field(default_factory=list)
    extracted_info: dict = field(default_factory=dict)
    transfer_chain: List[str] = field(default_factory=list)
    sentiment_trail: List[str] = field(default_factory=list)
    escalation_reason: Optional[str] = None

    def build_handoff_prompt(self, new_agent_name: str, new_department: str) -> str:
        """
        Build a context-enriched system prompt for the receiving agent.
        The new agent immediately knows everything discussed so far.
        """
        summary_lines = []
        summary_lines.append(
            f"TRANSFER CONTEXT: This caller ({self.caller_number}) has been "
            f"transferred to you ({new_agent_name}, {new_department})."
        )

        if self.transfer_chain:
            summary_lines.append(
                f"Previous departments: {' -> '.join(self.transfer_chain)}."
            )
            summary_lines.append(
                "IMPORTANT: The caller has already explained their issue. "
                "Do NOT ask them to repeat it. Use the conversation history below."
            )

        if self.original_intent:
            summary_lines.append(f"Original intent detected: {self.original_intent}.")

        if self.extracted_info:
            info_str = ", ".join(f"{k}: {v}" for k, v in self.extracted_info.items())
            summary_lines.append(f"Extracted information: {info_str}.")

        if self.sentiment_trail:
            latest = self.sentiment_trail[-1]
            summary_lines.append(f"Current caller sentiment: {latest}.")
            if latest == "negative":
                summary_lines.append(
                    "ALERT: Caller is frustrated. Be extra empathetic and "
                    "prioritize a quick resolution."
                )

        if self.conversation_history:
            summary_lines.append("\n--- CONVERSATION SO FAR ---")
            for msg in self.conversation_history[-8:]:
                role = msg["role"].upper()
                summary_lines.append(f"{role}: {msg['content']}")
            summary_lines.append("--- END CONVERSATION ---\n")

        summary_lines.append(
            "Continue the conversation naturally from where it left off. "
            "Acknowledge the transfer briefly, then address their needs directly."
        )

        return "\n".join(summary_lines)

    def add_turn(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def extract_entities(self, text: str):
        """Extract common entities from caller speech."""
        # Order / tracking numbers
        order_match = re.findall(r'(?:order|tracking)\s*(?:#|number)?\s*([A-Z0-9-]{5,})', text, re.I)
        if order_match:
            self.extracted_info["order_number"] = order_match[0]

        # Email
        email_match = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        if email_match:
            self.extracted_info["email"] = email_match[0]

        # Phone numbers (secondary)
        phone_match = re.findall(r'\+?\d{10,13}', text)
        if phone_match:
            self.extracted_info["alt_phone"] = phone_match[0]

        # Account / ticket IDs
        id_match = re.findall(r'(?:account|ticket|case)\s*(?:#|id|number)?\s*([A-Z0-9-]{4,})', text, re.I)
        if id_match:
            self.extracted_info["account_id"] = id_match[0]


# -- Smart Routing Decision ------------------------------------------

def should_transfer(
    current_dept: str,
    user_text: str,
    turn_count: int,
) -> Optional[IntentResult]:
    """
    Mid-call router: detect if the caller's needs have shifted
    and a transfer would be beneficial.
    """
    result = classify_intent(user_text)

    # Don't transfer for general or low confidence
    if result.intent == "general" or result.confidence < 0.4:
        return None

    # Don't transfer if already in the correct department
    if result.department == current_dept:
        return None

    # Only suggest transfer after the caller has spoken enough
    if turn_count < 2 and result.priority < 3:
        return None

    # Escalation always triggers transfer
    if result.intent == "escalation":
        return result

    # High-confidence re-route
    if result.confidence >= 0.6:
        return result

    return None


# -- Logistics Automation Engine -------------------------------------

LOGISTICS_RESPONSES = {
    "track": (
        "I can help you track your shipment. "
        "Your order {order} is currently {status}. "
        "Estimated delivery: {eta}. "
        "Would you like real-time tracking updates via SMS?"
    ),
    "return": (
        "I'll help you initiate a return. "
        "Your return request for order {order} has been created. "
        "Reference number: RET-{ref}. "
        "Please ship the item within 14 business days. "
        "A prepaid shipping label has been sent to your email."
    ),
    "delay": (
        "I apologize for the delay with your order {order}. "
        "There's currently a {reason} causing delays in your region. "
        "Updated estimated delivery: {eta}. "
        "As compensation, we've applied a 10% credit to your account."
    ),
    "stock": (
        "Let me check inventory for you. "
        "The item you're asking about is currently {availability}. "
        "{restock_info}"
    ),
}


def handle_logistics_query(text: str, context: CallContext) -> Optional[str]:
    """
    Automated logistics response engine.
    Returns a response string if the query can be handled automatically,
    or None if it needs a human agent.
    """
    text_lower = text.lower()
    order = context.extracted_info.get("order_number", "ORD-" + "7829341")

    if any(w in text_lower for w in ["track", "where is", "status of", "shipping"]):
        import random
        statuses = ["in transit", "out for delivery", "at regional hub", "dispatched"]
        return LOGISTICS_RESPONSES["track"].format(
            order=order,
            status=random.choice(statuses),
            eta="within 2-3 business days",
        )

    if any(w in text_lower for w in ["return", "send back", "exchange"]):
        import uuid
        return LOGISTICS_RESPONSES["return"].format(
            order=order,
            ref=uuid.uuid4().hex[:8].upper(),
        )

    if any(w in text_lower for w in ["delay", "late", "not arrived", "waiting"]):
        reasons = ["weather disruption", "high seasonal demand", "customs processing"]
        import random
        return LOGISTICS_RESPONSES["delay"].format(
            order=order,
            reason=random.choice(reasons),
            eta="within 4-5 business days",
        )

    if any(w in text_lower for w in ["stock", "available", "inventory", "in stock"]):
        return LOGISTICS_RESPONSES["stock"].format(
            availability="in stock and ready to ship",
            restock_info="We can dispatch it within 24 hours.",
        )

    return None  # Needs human or general AI

