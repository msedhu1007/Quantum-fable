"""Optional LLM reasoning layer.

Deterministic rules in scoring.py decide whether a setup qualifies; this layer
only explains, classifies, and adds risk framing. Disabled unless
ANTHROPIC_API_KEY is set — everything degrades gracefully without it.
"""
import json
import logging

from .config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an options research alerting agent. Your job is to analyze stock, options, volatility, news, and market context data and produce clear CALL, PUT, or NO TRADE alerts.

You are not allowed to guarantee profits or provide certainty. You must explain the evidence, risk, and confidence level. You must avoid recommending illiquid contracts, contracts with wide spreads, or trades where the signal is weak.

Decision rules:
1. Return CALL only when the setup is clearly bullish and a liquid call contract exists.
2. Return PUT only when the setup is clearly bearish and a liquid put contract exists.
3. Return NO TRADE when signals conflict, liquidity is poor, spreads are wide, IV is too high, earnings risk is unclear, or confidence is low.
4. Prefer options with 7 to 45 days to expiration.
5. Prefer Delta between 0.30 and 0.60 for calls.
6. Prefer Delta between -0.30 and -0.60 for puts.
7. Avoid options with open interest below 500 unless explicitly configured otherwise.
8. Avoid options with bid/ask spread greater than 15%.
9. Mention IV risk when IV is elevated.
10. Mention event risk when earnings or major announcements are near.

You will receive a JSON snapshot of the ticker plus the deterministic engine's score and candidate contract. Never override the hard liquidity rules — if the engine found no qualifying contract, the decision must be NO TRADE."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["CALL", "PUT", "NO TRADE"]},
        "confidence": {"type": "string", "enum": ["Low", "Medium", "High"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "invalidation_level": {"type": "string"},
        "alert_message": {"type": "string"},
    },
    "required": ["decision", "confidence", "reasons", "risks", "invalidation_level", "alert_message"],
    "additionalProperties": False,
}


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def analyze(snapshot: dict) -> dict | None:
    """Ask Claude to classify and explain a scored setup. Returns parsed JSON or None."""
    if not enabled():
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": "Analyze this options setup snapshot:\n"
                    + json.dumps(snapshot, default=str, sort_keys=True),
                }
            ],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception:
        log.exception("LLM analysis failed for %s — falling back to deterministic output", snapshot.get("ticker"))
        return None
