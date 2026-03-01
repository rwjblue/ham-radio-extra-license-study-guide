from __future__ import annotations

import re

from .models import Question

ABBREVIATIONS = {
    "FCC": "Federal Communications Commission",
    "RF": "radio frequency",
    "EME": "earth moon earth",
    "HF": "high frequency",
    "VHF": "very high frequency",
    "UHF": "ultra high frequency",
    "SSB": "single sideband",
    "CW": "continuous wave",
    "AM": "amplitude modulation",
    "FM": "frequency modulation",
    "RMS": "root mean square",
    "EIRP": "equivalent isotropically radiated power",
}

UNIT_PATTERNS = {
    r"\b([0-9]+(?:\.[0-9]+)?)\s*kHz\b": r"\1 kilohertz",
    r"\b([0-9]+(?:\.[0-9]+)?)\s*MHz\b": r"\1 megahertz",
    r"\b([0-9]+(?:\.[0-9]+)?)\s*GHz\b": r"\1 gigahertz",
    r"\b([0-9]+(?:\.[0-9]+)?)\s*dB\b": r"\1 decibels",
    r"\b([0-9]+(?:\.[0-9]+)?)\s*W\b": r"\1 watts",
    r"\b([0-9]+(?:\.[0-9]+)?)\s*V\b": r"\1 volts",
    r"\b([0-9]+(?:\.[0-9]+)?)\s*A\b": r"\1 amperes",
}


def fact_sentence(question: Question, mode: str, omit_id: bool = False) -> str:
    answer = question.choices[question.correct_choice]
    question_text = question.question_text.strip()

    sentence = _to_declarative(question_text, answer)
    sentence = _normalize_sentence(sentence)

    if mode == "tts":
        sentence = _to_tts(sentence)

    if omit_id:
        return sentence
    return f"{question.question_id}: {sentence}"


def _to_declarative(question_text: str, answer: str) -> str:
    lower = question_text.lower()

    if lower.startswith("what is "):
        stem = _strip_qmark(question_text)
        stem = re.sub(r"^What is\s+", "", stem, flags=re.IGNORECASE)
        return f"{_capitalize_first(stem)} is {answer}."

    if lower.startswith("which of the following"):
        stem = _strip_qmark(question_text)
        return f"For '{stem}', the correct choice is {answer}."

    if lower.startswith("how many"):
        stem = _strip_qmark(question_text)
        return f"For '{stem}', the number is {answer}."

    if lower.startswith("when must"):
        stem = _strip_qmark(question_text)
        stem = re.sub(r"^When must\s+", "", stem, flags=re.IGNORECASE)
        return f"You must {stem} when {answer}."

    stem = _strip_qmark(question_text)
    return f"For '{stem}', the correct answer is {answer}."


def _strip_qmark(text: str) -> str:
    return text.rstrip().rstrip("?").strip()


def _capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _normalize_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text.endswith("."):
        text += "."
    return text


def _to_tts(text: str) -> str:
    out = text

    for pattern, replacement in UNIT_PATTERNS.items():
        out = re.sub(pattern, replacement, out)

    for short, expanded in ABBREVIATIONS.items():
        out = re.sub(rf"\b{re.escape(short)}\b", expanded, out)

    out = out.replace(";", ",")
    out = out.replace("/", " or ")
    out = re.sub(r"\((.*?)\)", r", \1,", out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s+,", ",", out)
    return out.strip()
