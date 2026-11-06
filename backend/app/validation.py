"""Deterministic checks: model JSON is a proposal, never an alert decision."""

import re

from .models import Intent, ProposedEvent, Segment

TOKEN_PATTERN = r"[AP]?[0-9]{3}"
COUNTERS = {str(i) for i in range(1, 11)}
DIGITS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "പൂജ്യം": "0",
    "ഒന്ന്": "1",
    "രണ്ട്": "2",
    "മൂന്ന്": "3",
    "നാല്": "4",
    "അഞ്ച്": "5",
    "ആറ്": "6",
    "ഏഴ്": "7",
    "എട്ട്": "8",
    "ഒൻപത്": "9",
    "ഒമ്പത്": "9",
    "പി": "P",
    "എ": "A",
}
CARDINALS = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "പത്ത്": 10,
    "പതിനൊന്ന്": 11,
    "പന്ത്രണ്ട്": 12,
    "പതിമൂന്ന്": 13,
    "പതിനാല്": 14,
    "പതിനഞ്ച്": 15,
    "പതിനാറ്": 16,
    "പതിനേഴ്": 17,
    "പതിനെട്ട്": 18,
    "പത്തൊമ്പത്": 19,
    "ഇരുപത്": 20,
    "ഇരുപത്തി": 20,
    "മുപ്പത്": 30,
    "മുപ്പത്തി": 30,
    "നാല്പത്": 40,
    "നാല്പത്തി": 40,
    "നാൽപ്പത്": 40,
    "നാൽപ്പത്തി": 40,
    "അമ്പത്": 50,
    "അമ്പത്തി": 50,
    "അറുപത്": 60,
    "അറുപത്തി": 60,
    "എഴുപത്": 70,
    "എഴുപത്തി": 70,
    "എൺപത്": 80,
    "എൺപത്തി": 80,
    "തൊണ്ണൂറ്": 90,
    "തൊണ്ണൂറ്റി": 90,
    "നൂറ്": 100,
    "നൂറ്റി": 100,
    "ഇരുനൂറ്": 200,
    "ഇരുനൂറ്റി": 200,
    "മുന്നൂറ്": 300,
    "മുന്നൂറ്റി": 300,
    "നാനൂറ്": 400,
    "നാനൂറ്റി": 400,
    "അഞ്ഞൂറ്": 500,
    "അഞ്ഞൂറ്റി": 500,
    "അറുനൂറ്": 600,
    "അറുനൂറ്റി": 600,
    "എഴുനൂറ്": 700,
    "എഴുനൂറ്റി": 700,
    "എണ്ണൂറ്": 800,
    "എണ്ണൂറ്റി": 800,
    "തൊള്ളായിരം": 900,
    "തൊള്ളായിരത്തി": 900,
}


def normalize_token(raw: str) -> str | None:
    if not re.fullmatch(r"[A-Za-z0-9\u0D00-\u0D7F\s,.-]+", raw):
        return None
    words = re.findall(r"[A-Za-z]+|[0-9]+|[\u0D00-\u0D7F]+", raw)
    words = [DIGITS.get(w.casefold(), w.casefold()) for w in words]
    prefix = ""
    if words and words[0].upper() in {"A", "P"}:
        prefix = words.pop(0).upper()
    if words and all(w.isascii() and w.isdigit() for w in words):
        value = prefix + "".join(words)
        return value if re.fullmatch(TOKEN_PATTERN, value) else None
    # Cardinal forms are deliberately narrow: never pad or guess a leading zero.
    words = [w for w in words if w != "and"]
    values = []
    for word in words:
        if word == "hundred" and len(values) == 1 and 1 <= values[0] <= 9:
            values[0] *= 100
        elif word in CARDINALS:
            values.append(CARDINALS[word])
        elif word.isascii() and word.isdigit() and len(word) == 1:
            values.append(int(word))
        else:
            return None
    if not values or values[0] < 100 or len(values) > 3:
        return None
    if len(values) >= 2 and not 0 < values[1] < 100:
        return None
    if len(values) == 3 and not (values[1] in range(20, 100, 10) and 0 < values[2] < 10):
        return None
    value = prefix + str(sum(values))
    return value if re.fullmatch(TOKEN_PATTERN, value) else None


def exact_span(phrase: str, text: str) -> bool:
    """Do not ground 042 in P042, or 123 in 1234."""
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def counter_grounded(counter: str, evidence: str, token_raw: str) -> bool:
    # The token's own digits must not count as counter evidence.
    remainder = evidence.replace(token_raw, " ")
    forms = {counter}
    forms.update(word for word, value in DIGITS.items() if value == counter)
    if counter == "10":
        forms.update({"ten", "പത്ത്"})
    return any(exact_span(form, remainder.casefold()) for form in forms)


def intent_errors(intent: Intent, request: str) -> list[str]:
    errors = []
    if intent.intent != "monitor_announcement":
        errors.append("Only queue-token monitoring is supported in this venue.")
    if intent.context != "hospital_pharmacy":
        errors.append("This build supports the configured hospital pharmacy only.")
    if not intent.target_evidence or not exact_span(intent.target_evidence, request):
        errors.append("The target must be grounded in your request.")
    elif normalize_token(intent.target_evidence) != intent.token:
        errors.append("The token is unclear; type its exact prefix and three digits.")
    if not intent.token or not re.fullmatch(TOKEN_PATTERN, intent.token):
        errors.append("Use this venue's token format: P042, A007, or 042.")
    if not ({"vibration", "sound", "visual"} & set(intent.alert_preferences)):
        errors.append("Specify visual, vibration, or sound alerts.")
    if intent.clarification:
        errors.append(intent.clarification)
    return errors


def validate_event(event: ProposedEvent, window: list[Segment]) -> ProposedEvent:
    by_id = {segment.id: segment for segment in window}
    sources = [by_id[sid] for sid in event.source_segment_ids if sid in by_id]
    text = " ".join(segment.text for segment in sources)
    reason = None
    if not sources or len(sources) != len(event.source_segment_ids):
        reason = "Unknown source segment."
    elif event.source_segment_ids != [
        segment.id for segment in window if segment.id in event.source_segment_ids
    ]:
        reason = "Source segments must be unique and chronological."
    elif not event.evidence_text or event.evidence_text not in text:
        reason = "Evidence is not a verbatim span of the source."
    elif event.type not in {"OTHER", "UNCERTAIN"}:
        if not event.token_raw or not exact_span(event.token_raw, event.evidence_text):
            reason = "Token has no exact evidence span."
        elif (
            not event.token_normalized or normalize_token(event.token_raw) != event.token_normalized
        ):
            reason = "Token normalization is unsupported or unclear."
        elif event.counter is not None and event.counter not in COUNTERS:
            reason = "Counter is outside the configured venue grammar."
        elif event.counter is not None and not counter_grounded(
            event.counter, event.evidence_text, event.token_raw
        ):
            reason = "Counter has no exact evidence span."
        elif event.ambiguity_reason:
            reason = event.ambiguity_reason
    if reason:
        return event.model_copy(update={"type": "UNCERTAIN", "ambiguity_reason": reason})
    return event
