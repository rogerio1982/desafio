"""
app/core/intents.py

Intent classification — keyword-first with a GPT-4o-mini semantic fallback.

Classification order:
    1. Score each intent by keyword overlap (O(n) string scan, no API cost).
    2. If the top score is tied, resolve by explicit priority:
       Escalation > Purchase Intent > Voice Request > Space Analysis > Product Info
    3. If no keyword matches, ask GPT-4o-mini for a classification.
    4. If the API call fails, default to "Escalation" (safest terminal state).
"""

from app.config import client

INTENTS = [
    "Product Info",
    "Space Analysis",
    "Purchase Intent",
    "Voice Request",
    "Escalation",
]

# Tie-break priority: most operationally specific intent wins
_PRIORITY = ["Escalation", "Purchase Intent", "Voice Request", "Space Analysis", "Product Info"]

_KEYWORDS: dict[str, list[str]] = {
    "Product Info":    ["car", "vehicle", "product", "model", "engine", "price", "color", "specification"],
    "Space Analysis":  ["layout", "space", "showroom", "area", "floor plan", "arrangement", "environment"],
    "Purchase Intent": ["buy", "purchase", "want to acquire", "financing", "installment", "order"],
    "Voice Request":   ["speak", "voice", "read", "audio", "listen", "pronounce"],
    "Escalation":      ["human", "attendant", "person", "help", "support", "manager"],
}


def _keyword_classify(message: str) -> str | None:
    msg = message.lower()
    scores = {intent: 0 for intent in INTENTS}
    for intent, words in _KEYWORDS.items():
        for word in words:
            if word in msg:
                scores[intent] += 1
    max_score = max(scores.values())
    if max_score == 0:
        return None
    for intent in _PRIORITY:
        if scores[intent] == max_score:
            return intent
    return None


async def classify_intent(message: str) -> str:
    """Return the intent name for *message*."""
    intent = _keyword_classify(message)
    if intent:
        return intent

    try:
        prompt = (
            f"Classify the intent of this message for a 3D digital car showroom.\n"
            f"Message: '{message}'\n"
            f"Possible intents: {', '.join(INTENTS)}\n"
            "Reply with the exact intent name only."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an intent classifier for a car showroom."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=20,
            temperature=0,
        )
        result = response.choices[0].message.content.strip()
        if result in INTENTS:
            return result
    except Exception:
        pass

    return "Escalation"
