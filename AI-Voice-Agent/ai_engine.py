"""
Enterprise Voice AI Gateway — AI Brain
Handles STT, LLM inference, TTS, and sentiment analysis.
"""
import os
import uuid
import asyncio
import tempfile
from pathlib import Path
from typing import Optional
from loguru import logger

from config import settings

# ── Optional heavy deps (graceful degradation) ────────────
try:
    import openai
    _openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    _has_openai = bool(settings.openai_api_key)
except ImportError:
    _has_openai = False

try:
    import whisper as _whisper
    _whisper_model = None          # lazy load
    _has_whisper = True
except ImportError:
    _has_whisper = False

try:
    from gtts import gTTS
    _has_gtts = True
except ImportError:
    _has_gtts = False


# ── Speech-to-Text ────────────────────────────────────────

def _load_whisper():
    global _whisper_model
    if _whisper_model is None and _has_whisper:
        logger.info(f"Loading Whisper model '{settings.whisper_model}'…")
        _whisper_model = _whisper.load_model(settings.whisper_model)
        logger.info("Whisper ready ✓")
    return _whisper_model


async def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribe an audio file using Whisper.
    Returns {"text": str, "confidence": float}
    """
    if not _has_whisper:
        return {"text": "[Whisper not installed]", "confidence": 0.0}

    loop = asyncio.get_event_loop()
    try:
        model = _load_whisper()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(audio_path, fp16=False)
        )
        text = result.get("text", "").strip()
        # crude confidence from avg log-prob
        segments = result.get("segments", [])
        if segments:
            avg_logprob = sum(s.get("avg_logprob", -1) for s in segments) / len(segments)
            confidence = round(max(0.0, min(1.0, (avg_logprob + 1) / 1)), 3)
        else:
            confidence = 0.5
        logger.info(f"Transcribed: '{text[:80]}' (conf={confidence})")
        return {"text": text, "confidence": confidence}
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return {"text": "", "confidence": 0.0}


# ── LLM Response ──────────────────────────────────────────

async def generate_ai_response(
    conversation_history: list[dict],
    system_prompt: str,
    user_message: str,
) -> str:
    """
    Generate an AI response using OpenAI GPT.
    Falls back to a rule-based response if OpenAI is unavailable.
    """
    if not _has_openai:
        return _rule_based_response(user_message)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history[-10:])   # keep last 10 turns
    messages.append({"role": "user", "content": user_message})

    try:
        resp = await _openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=200,
            temperature=0.4,
        )
        reply = resp.choices[0].message.content.strip()
        logger.info(f"AI response: '{reply[:80]}'")
        return reply
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return (
            "I'm experiencing a temporary issue. "
            "Please hold while I reconnect you with a human agent."
        )


def _rule_based_response(text: str) -> str:
    """Simple fallback when OpenAI is not configured."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["billing", "invoice", "payment", "charge"]):
        return "I understand you have a billing concern. Let me pull up your account details and assist you right away."
    if any(w in text_lower for w in ["error", "bug", "crash", "not working", "broken"]):
        return "I'm sorry you're experiencing technical difficulties. Can you describe the error message you're seeing?"
    if any(w in text_lower for w in ["price", "cost", "plan", "upgrade", "license"]):
        return "I'd be happy to walk you through our enterprise pricing options. Are you looking to upgrade an existing plan?"
    if any(w in text_lower for w in ["thank", "thanks", "goodbye", "bye"]):
        return "Thank you for calling. It was a pleasure assisting you today. Have a wonderful day!"
    return (
        "Thank you for that information. I'm processing your request and "
        "will have an answer for you shortly. Is there anything else you'd like to add?"
    )


# ── Sentiment Analysis ────────────────────────────────────

async def analyze_sentiment(text: str) -> str:
    """Returns 'positive', 'neutral', or 'negative'."""
    if not _has_openai or not text:
        return _simple_sentiment(text)

    try:
        resp = await _openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the sentiment of this customer call text as exactly one word: "
                        "positive, neutral, or negative. Reply with only that one word."
                    ),
                },
                {"role": "user", "content": text[:500]},
            ],
            max_tokens=5,
        )
        label = resp.choices[0].message.content.strip().lower()
        if label in ("positive", "neutral", "negative"):
            return label
        return "neutral"
    except Exception:
        return _simple_sentiment(text)


def _simple_sentiment(text: str) -> str:
    negative = ["angry", "frustrated", "terrible", "awful", "worst", "disappointed", "bad"]
    positive = ["great", "wonderful", "excellent", "happy", "satisfied", "love", "thank"]
    tl = text.lower()
    if any(w in tl for w in negative):
        return "negative"
    if any(w in tl for w in positive):
        return "positive"
    return "neutral"


# ── Call Summary ──────────────────────────────────────────

async def summarize_call(transcript: list[dict]) -> str:
    """Generate a brief call summary for the admin dashboard."""
    if not _has_openai or not transcript:
        return "Call completed."

    conv = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in transcript)
    try:
        resp = await _openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize this enterprise support call in 2-3 sentences. "
                        "Include the main issue, outcome, and any follow-up needed."
                    ),
                },
                {"role": "user", "content": conv[:2000]},
            ],
            max_tokens=120,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Summary error: {e}")
        return "Call completed. Summary unavailable."


# ── Text-to-Speech ────────────────────────────────────────

def text_to_speech_file(text: str, lang: str = "en") -> Optional[str]:
    """Convert text to an MP3 file. Returns the file path or None."""
    if not _has_gtts:
        return None
    try:
        path = Path(tempfile.mkdtemp()) / f"tts_{uuid.uuid4().hex[:8]}.mp3"
        gTTS(text=text, lang=lang, slow=False).save(str(path))
        return str(path)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None
