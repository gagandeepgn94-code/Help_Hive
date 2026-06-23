"""
ai_engine.py — HelpHive AI Emergency Decision Engine

Standalone module that predicts emergency priority, severity, and
recommended response radius using the NVIDIA NIM Chat Completions API.

Usage (future integration):
    from ai_engine import predict_emergency

    result = predict_emergency(
        category="Doctor",
        description="Person collapsed, not breathing",
        request_time="23-06-2026 10:45",
        nearby_volunteers=3
    )

This module does NOT modify Flask routes, the database, or app.py.
"""

import json
import logging
import os
import re
from typing import Any

import requests as http_requests  # Aliased to avoid conflict with Flask's `request`
from dotenv import load_dotenv

# ================= CONFIGURATION =================

load_dotenv()

NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL", "meta/llama-3.2-3b-instruct")
NVIDIA_API_URL: str = "https://integrate.api.nvidia.com/v1/chat/completions"

# API timeout in seconds (connect timeout, read timeout)
API_TIMEOUT: tuple[int, int] = (10, 30)

# ================= LOGGING =================

logger = logging.getLogger("helphive.ai")
logger.setLevel(logging.DEBUG)

# Add a console handler if none exist (avoids duplicate handlers on reimport)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(name)s] %(levelname)s — %(message)s")
    )
    logger.addHandler(_handler)

# ================= FALLBACK RESPONSE =================

FALLBACK_RESPONSE: dict[str, Any] = {
    "priority": "Medium",
    "severity_score": 5.0,
    "confidence": 0.0,
    "recommended_radius": 10,
    "notify_immediately": False,
    "reason": "AI unavailable — using default assessment"
}

# ================= SYSTEM PROMPT =================

SYSTEM_PROMPT: str = """You are the HelpHive Emergency Decision Engine.

You are NOT a chatbot. You are a deterministic emergency triage system.
You receive structured emergency data and return a JSON assessment.

## YOUR TASK
Analyze the emergency and return a priority classification with a severity score.

## PRIORITY RULES (strict)

**Critical** (severity_score 9.0–10.0):
- Unconscious person
- Not breathing / respiratory failure
- Cardiac arrest / heart attack
- Stroke symptoms
- Fire with people trapped
- Severe uncontrolled bleeding
- Drowning
- Electrocution
- Building collapse with casualties

**High** (severity_score 7.0–8.9):
- Serious injury requiring immediate care
- Chest pain / difficulty breathing
- Road accident with injuries
- Fractures / broken bones
- Burns (second degree or higher)
- Allergic reaction (anaphylaxis)
- Assault / violence with injury

**Medium** (severity_score 4.0–6.9):
- Moderate illness (fever, infection, pain)
- Minor road accident (no severe injuries)
- Minor burns or cuts needing medical attention
- Non-life-threatening allergic reaction
- Mental health crisis (non-suicidal)

**Low** (severity_score 1.0–3.9):
- General assistance request
- Non-urgent medical consultation
- Minor first aid
- Information or resource request
- Wellness check

## RADIUS RECOMMENDATION
- Critical: 30–50 KM (cast wide net)
- High: 20–30 KM
- Medium: 10–20 KM
- Low: 10 KM

Consider nearby_volunteers count:
- If 0 nearby volunteers → recommend LARGER radius
- If 5+ nearby volunteers → recommend SMALLER radius

## NOTIFY_IMMEDIATELY RULES
- Set to true for Critical priority (life-threatening)
- Set to true for High priority with severity_score >= 8.5
- Set to false for all other cases

## RESPONSE FORMAT
Return ONLY a valid JSON object. No markdown, no explanation, no extra text.

{
    "priority": "<Critical|High|Medium|Low>",
    "severity_score": <float 1.0–10.0>,
    "confidence": <float 0.0–1.0>,
    "recommended_radius": <int in KM>,
    "notify_immediately": <true|false>,
    "reason": "<one-line clinical justification>"
}"""

# ================= CORE FUNCTION =================


def predict_emergency(
    category: str,
    description: str,
    request_time: str,
    nearby_volunteers: int
) -> dict[str, Any]:
    """Predict emergency priority and severity using NVIDIA NIM API.

    Sends structured emergency data to the LLM and parses the returned
    JSON into a Python dictionary. If the API call fails for any reason,
    returns a safe fallback response so the Flask app never crashes.

    Args:
        category: Emergency category (e.g. 'Doctor', 'Fire Rescue').
        description: Free-text description of the emergency.
        request_time: Timestamp string (e.g. '23-06-2026 10:45').
        nearby_volunteers: Number of volunteers currently within range.

    Returns:
        Dictionary with keys: priority, severity_score, confidence,
        recommended_radius, reason.
    """

    # ---- Guard: missing API key ----
    if not NVIDIA_API_KEY:
        logger.error("NVIDIA_API_KEY is not set — returning fallback")
        return {**FALLBACK_RESPONSE, "reason": "AI unavailable — API key not configured"}

    # ---- Build the user message ----
    user_message: str = (
        f"Emergency Category: {category}\n"
        f"Description: {description}\n"
        f"Time of Request: {request_time}\n"
        f"Nearby Volunteers Available: {nearby_volunteers}"
    )

    # ---- Build the API payload ----
    payload: dict[str, Any] = {
        "model": NVIDIA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1,       # Low temperature for deterministic output
        "max_tokens": 256,        # JSON response is small
        "top_p": 0.9,
        "stream": False
    }

    headers: dict[str, str] = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # ---- Call the NVIDIA NIM API ----
    try:
        logger.info(
            "Calling NVIDIA NIM API — model=%s, category=%s",
            NVIDIA_MODEL, category
        )

        response = http_requests.post(
            NVIDIA_API_URL,
            headers=headers,
            json=payload,
            timeout=API_TIMEOUT
        )

        # ---- Handle HTTP errors ----
        if response.status_code == 401:
            logger.error("NVIDIA API authentication failed (401) — check NVIDIA_API_KEY")
            return {**FALLBACK_RESPONSE, "reason": "AI unavailable — authentication failed"}

        if response.status_code == 429:
            logger.warning("NVIDIA API rate limit hit (429) — returning fallback")
            return {**FALLBACK_RESPONSE, "reason": "AI unavailable — rate limit exceeded"}

        if response.status_code >= 500:
            logger.error("NVIDIA API server error (%d)", response.status_code)
            return {**FALLBACK_RESPONSE, "reason": "AI unavailable — server error"}

        response.raise_for_status()

        # ---- Extract the model's response text ----
        response_data: dict = response.json()

        # Log full API response structure for debugging
        logger.info("NVIDIA API HTTP status: %d", response.status_code)

        usage = response_data.get("usage", {})
        logger.info(
            "NVIDIA API usage — prompt_tokens=%s, completion_tokens=%s, total=%s",
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
            usage.get("total_tokens", "?")
        )

        choices = response_data.get("choices", [])
        if not choices:
            logger.error("NVIDIA API returned no choices — full response: %s", json.dumps(response_data, indent=2))
            return {**FALLBACK_RESPONSE, "reason": "AI unavailable — no choices in response"}

        first_choice = choices[0]
        finish_reason = first_choice.get("finish_reason", "unknown")
        logger.info("NVIDIA API finish_reason: %s", finish_reason)

        if finish_reason == "length":
            logger.warning("NVIDIA API response was TRUNCATED (finish_reason=length) — increase max_tokens")

        raw_content: str = (
            first_choice
            .get("message", {})
            .get("content", "")
            .strip()
        )

        # Log the FULL raw content at INFO level (not debug) so it's always visible
        logger.info("[DEBUG] Raw AI content (%d chars): %s", len(raw_content), raw_content)

        if not raw_content:
            logger.error("NVIDIA API returned empty content — full response: %s", json.dumps(response_data, indent=2))
            return {**FALLBACK_RESPONSE, "reason": "AI unavailable — empty response"}

        # ---- Parse and validate the JSON ----
        return _parse_ai_response(raw_content)

    except http_requests.exceptions.Timeout:
        logger.error("NVIDIA API request timed out after %s seconds", API_TIMEOUT)
        return {**FALLBACK_RESPONSE, "reason": "AI unavailable — request timed out"}

    except http_requests.exceptions.ConnectionError:
        logger.error("NVIDIA API connection failed — network error")
        return {**FALLBACK_RESPONSE, "reason": "AI unavailable — network error"}

    except http_requests.exceptions.RequestException as e:
        logger.error("NVIDIA API request failed: %s", e)
        return {**FALLBACK_RESPONSE, "reason": "AI unavailable — request error"}

    except Exception as e:
        # Catch-all: never let an unexpected error propagate to Flask
        logger.exception("Unexpected error in predict_emergency: %s", e)
        return {**FALLBACK_RESPONSE, "reason": "AI unavailable — unexpected error"}


# ================= RESPONSE PARSER =================


def _extract_json_from_text(text: str) -> str | None:
    """Extract a JSON object {...} from arbitrary surrounding text.

    Uses brace-depth counting to find the outermost { ... } block.
    Returns the extracted JSON string, or None if no valid block found.
    """
    start = text.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape_next:
            escape_next = False
            continue

        if ch == '\\':
            if in_string:
                escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return None


def _parse_ai_response(raw_content: str) -> dict[str, Any]:
    """Parse and validate the AI model's JSON response.

    Uses multiple strategies to handle common LLM output quirks:
      1. Direct JSON parse
      2. Strip markdown code fences (```json ... ```)
      3. Extract {...} from surrounding text
      4. Unescape doubly-escaped JSON strings

    Returns the validated dictionary or the fallback if all strategies fail.

    Args:
        raw_content: Raw string content from the AI model.

    Returns:
        Validated prediction dictionary.
    """

    cleaned = raw_content.strip()

    # ---- Strategy 1: Direct parse ----
    try:
        result: dict = json.loads(cleaned)
        logger.info("[PARSE] Strategy 1 succeeded: direct JSON parse")
        logger.info("[PARSE] Parsed dict: %s", json.dumps(result, indent=2))
        return _validate_prediction(result)
    except json.JSONDecodeError:
        logger.debug("[PARSE] Strategy 1 failed: direct parse")

    # ---- Strategy 2: Strip markdown code fences ----
    fence_cleaned = cleaned
    # Handle ```json, ```JSON, ``` or similar opening fences
    fence_pattern = re.match(r'^```[a-zA-Z]*\s*\n?', fence_cleaned)
    if fence_pattern:
        fence_cleaned = fence_cleaned[fence_pattern.end():]
        # Remove closing fence
        fence_cleaned = re.sub(r'\n?```\s*$', '', fence_cleaned)
        fence_cleaned = fence_cleaned.strip()
        logger.info("[PARSE] After stripping code fences: %s", fence_cleaned[:500])

        try:
            result = json.loads(fence_cleaned)
            logger.info("[PARSE] Strategy 2 succeeded: stripped code fences")
            logger.info("[PARSE] Parsed dict: %s", json.dumps(result, indent=2))
            return _validate_prediction(result)
        except json.JSONDecodeError as e:
            logger.debug("[PARSE] Strategy 2 failed: %s", e)

    # ---- Strategy 3: Extract {...} from surrounding text ----
    extracted = _extract_json_from_text(cleaned)
    if extracted:
        logger.info("[PARSE] Extracted JSON block: %s", extracted[:500])
        try:
            result = json.loads(extracted)
            logger.info("[PARSE] Strategy 3 succeeded: brace extraction")
            logger.info("[PARSE] Parsed dict: %s", json.dumps(result, indent=2))
            return _validate_prediction(result)
        except json.JSONDecodeError as e:
            logger.debug("[PARSE] Strategy 3 failed: %s", e)

    # ---- Strategy 4: Unescape doubly-escaped JSON ----
    # Some models return: "{\"priority\": \"Critical\", ...}"
    if cleaned.startswith('"') and cleaned.endswith('"'):
        try:
            unescaped = json.loads(cleaned)  # First parse removes outer quotes
            if isinstance(unescaped, str):
                result = json.loads(unescaped)  # Second parse gets the dict
                logger.info("[PARSE] Strategy 4 succeeded: double-escaped JSON")
                logger.info("[PARSE] Parsed dict: %s", json.dumps(result, indent=2))
                return _validate_prediction(result)
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug("[PARSE] Strategy 4 failed: %s", e)

    # ---- All strategies failed ----
    logger.error("[PARSE] ALL 4 parsing strategies failed")
    logger.error("[PARSE] Raw content (full): %s", raw_content)
    logger.error("[PARSE] Content repr: %r", raw_content[:1000])
    logger.error("[PARSE] Content length: %d chars", len(raw_content))
    logger.error("[PARSE] First 20 char codes: %s", [ord(c) for c in raw_content[:20]])
    return {**FALLBACK_RESPONSE, "reason": "AI unavailable — could not parse response (all strategies failed)"}


def _validate_prediction(result: dict) -> dict[str, Any]:
    """Validate and sanitize the parsed prediction dictionary.

    Ensures all required fields exist with correct types and values
    within expected ranges. Applies safe defaults for any missing or
    out-of-range fields. Logs every field that uses a default or gets clamped.

    Args:
        result: Raw parsed dictionary from the AI model.

    Returns:
        Sanitized prediction dictionary.
    """

    logger.info("[VALIDATE] Input dict keys: %s", list(result.keys()))
    logger.info("[VALIDATE] Input dict: %s", json.dumps(result, indent=2, default=str))

    valid_priorities = {"Critical", "High", "Medium", "Low"}
    defaulted_fields: list[str] = []  # Track which fields used defaults

    # Priority
    priority = result.get("priority")
    if priority is None:
        logger.warning("[VALIDATE] 'priority' MISSING from AI response — defaulting to Medium")
        priority = "Medium"
        defaulted_fields.append("priority")
    elif priority not in valid_priorities:
        logger.warning("[VALIDATE] 'priority' = '%s' is INVALID (expected: %s) — defaulting to Medium", priority, valid_priorities)
        priority = "Medium"
        defaulted_fields.append("priority")
    else:
        logger.info("[VALIDATE] priority = %s ✓", priority)

    # Severity score (clamp to 1.0–10.0)
    raw_severity = result.get("severity_score")
    if raw_severity is None:
        logger.warning("[VALIDATE] 'severity_score' MISSING — defaulting to 5.0")
        severity_score = 5.0
        defaulted_fields.append("severity_score")
    else:
        try:
            severity_score = float(raw_severity)
            original = severity_score
            severity_score = max(1.0, min(10.0, severity_score))
            if severity_score != original:
                logger.warning("[VALIDATE] severity_score clamped: %.1f → %.1f", original, severity_score)
            else:
                logger.info("[VALIDATE] severity_score = %.1f ✓", severity_score)
        except (ValueError, TypeError):
            logger.warning("[VALIDATE] 'severity_score' = %r is NOT a number — defaulting to 5.0", raw_severity)
            severity_score = 5.0
            defaulted_fields.append("severity_score")

    # Confidence (clamp to 0.0–1.0)
    raw_confidence = result.get("confidence")
    if raw_confidence is None:
        logger.warning("[VALIDATE] 'confidence' MISSING — defaulting to 0.5")
        confidence = 0.5
        defaulted_fields.append("confidence")
    else:
        try:
            confidence = float(raw_confidence)
            original = confidence
            confidence = max(0.0, min(1.0, confidence))
            if confidence != original:
                logger.warning("[VALIDATE] confidence clamped: %.2f → %.2f (was it a percentage?)", original, confidence)
            else:
                logger.info("[VALIDATE] confidence = %.2f ✓", confidence)
        except (ValueError, TypeError):
            logger.warning("[VALIDATE] 'confidence' = %r is NOT a number — defaulting to 0.5", raw_confidence)
            confidence = 0.5
            defaulted_fields.append("confidence")

    # Recommended radius (clamp to 5–50 KM)
    raw_radius = result.get("recommended_radius")
    if raw_radius is None:
        logger.warning("[VALIDATE] 'recommended_radius' MISSING — defaulting to 10")
        recommended_radius = 10
        defaulted_fields.append("recommended_radius")
    else:
        try:
            recommended_radius = int(raw_radius)
            original = recommended_radius
            recommended_radius = max(5, min(50, recommended_radius))
            if recommended_radius != original:
                logger.warning("[VALIDATE] recommended_radius clamped: %d → %d", original, recommended_radius)
            else:
                logger.info("[VALIDATE] recommended_radius = %d KM ✓", recommended_radius)
        except (ValueError, TypeError):
            logger.warning("[VALIDATE] 'recommended_radius' = %r is NOT an int — defaulting to 10", raw_radius)
            recommended_radius = 10
            defaulted_fields.append("recommended_radius")

    # Reason
    reason = result.get("reason")
    if not reason or not str(reason).strip():
        logger.warning("[VALIDATE] 'reason' MISSING or empty — defaulting")
        reason = "AI assessment"
        defaulted_fields.append("reason")
    else:
        reason = str(reason)
        logger.info("[VALIDATE] reason = '%s' ✓", reason)

    # Notify immediately (boolean)
    raw_notify = result.get("notify_immediately")
    if raw_notify is None:
        logger.warning("[VALIDATE] 'notify_immediately' MISSING — defaulting to False")
        notify_immediately = False
        defaulted_fields.append("notify_immediately")
    else:
        notify_immediately = bool(raw_notify)
        logger.info("[VALIDATE] notify_immediately = %s ✓", notify_immediately)

    # Force notify_immediately for Critical, or High with severity >= 8.5
    if priority == "Critical" or (priority == "High" and severity_score >= 8.5):
        if not notify_immediately:
            logger.info("[VALIDATE] Overriding notify_immediately to True (priority=%s, severity=%.1f)", priority, severity_score)
        notify_immediately = True

    validated: dict[str, Any] = {
        "priority": priority,
        "severity_score": round(severity_score, 1),
        "confidence": round(confidence, 2),
        "recommended_radius": recommended_radius,
        "notify_immediately": notify_immediately,
        "reason": reason
    }

    # Summary log
    if defaulted_fields:
        logger.warning(
            "[VALIDATE] ⚠️ %d field(s) used defaults: %s",
            len(defaulted_fields), defaulted_fields
        )
    else:
        logger.info("[VALIDATE] ✅ All fields validated successfully — no defaults used")

    logger.info(
        "[VALIDATE] Final result — priority=%s, severity=%.1f, confidence=%.2f, radius=%d KM, notify=%s",
        validated["priority"],
        validated["severity_score"],
        validated["confidence"],
        validated["recommended_radius"],
        validated["notify_immediately"]
    )

    return validated


# ================= STANDALONE TEST =================

if __name__ == "__main__":
    """Quick standalone test — run with: python ai_engine.py"""

    print("=" * 60)
    print("HelpHive AI Engine — Standalone Test")
    print("=" * 60)

    test_cases = [
        {
            "category": "Doctor",
            "description": "Person collapsed on the street, not breathing, bystanders performing CPR",
            "request_time": "23-06-2026 10:45",
            "nearby_volunteers": 2
        },
        {
            "category": "Fire Rescue",
            "description": "Kitchen fire, smoke spreading, one person trapped inside",
            "request_time": "23-06-2026 11:00",
            "nearby_volunteers": 0
        },
        {
            "category": "Doctor",
            "description": "Minor headache and mild fever since yesterday",
            "request_time": "23-06-2026 09:30",
            "nearby_volunteers": 5
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: {case['category']} ---")
        print(f"Description: {case['description']}")

        prediction = predict_emergency(**case)

        print(f"Result: {json.dumps(prediction, indent=2)}")
        print()

    print("=" * 60)
    print("Test complete.")
