"""Shared presentation helpers for the official FPS reputation system.

The Google Sheet remains the authoritative score source. Nothing in this file
writes reputation, credits, or Discord messages automatically.
"""


def score_number(raw):
    """Only accept finite, whole-number 0..100 reputation scores."""
    try:
        number = float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("FPS reputation score is missing or not numeric") from exc
    if not (0 <= number <= 100) or not number.is_integer():
        raise ValueError("FPS reputation score must be a whole number from 0 to 100")
    return int(number)


def bar_color(score):
    """Pick a stable 10-step color scheme consistent with reputation tiers."""
    if score < 25:
        return "🟥"
    if score < 40:
        return "🟧"
    if score < 60:
        return "🟨"
    if score < 90:
        return "🟩"
    return "🟦"


def reputation_bar(score):
    """Ten visible blocks with the accompanying score shown separately."""
    score = score_number(score)
    filled = min(10, (score + 5) // 10)
    return bar_color(score) * filled + "⬛" * (10 - filled)


def embed_color(score):
    score = score_number(score)
    if score < 25:
        return 0xD94A46
    if score < 40:
        return 0xDD8733
    if score < 60:
        return 0xD1AC36
    if score < 90:
        return 0x3D9F63
    return 0x4E8AE6
