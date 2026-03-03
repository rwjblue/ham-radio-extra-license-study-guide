from __future__ import annotations

import re

from .models import PoolQuestion

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

LLM_EXPLANATION_PREFIX = "Notes: "


def fact_sentence(question: PoolQuestion, mode: str, omit_id: bool = False) -> str:
    if mode == "qa":
        sentence = _to_qa(question.question_text, question.correct_answer)
        sentence = _append_augmented_context(sentence, question)
    elif mode == "prose" and question.llm is not None:
        sentence = _normalize_sentence(question.llm.prose_fact)
        sentence = _append_augmented_context(sentence, question)
    else:
        answer = question.correct_answer
        question_text = question.question_text.strip()

        sentence = _to_declarative(question_text, answer)
        sentence = _normalize_sentence(sentence)

    if mode == "tts":
        sentence = _to_tts(sentence)

    if omit_id:
        return sentence
    return f"{question.question_id}: {sentence}"


def _append_augmented_context(sentence: str, question: PoolQuestion) -> str:
    if question.llm is None:
        return sentence
    explanation = _normalize_sentence(question.llm.answer_explanation)
    if not explanation:
        return sentence
    return f"{sentence}\n{LLM_EXPLANATION_PREFIX}{explanation}"


def _to_qa(question_text: str, answer: str) -> str:
    cleaned_question = question_text.strip()
    cleaned_answer = answer.strip()
    if not cleaned_question.endswith("?"):
        cleaned_question = f"{cleaned_question}?"
    return f"Q: {cleaned_question} A: {cleaned_answer}."


def _to_declarative(question_text: str, answer: str) -> str:
    stem = _strip_qmark(question_text)
    lower = stem.lower()

    if lower.startswith("what is "):
        if lower.startswith("what is meant by "):
            subject = re.sub(r"^What is meant by\s+", "", stem, flags=re.IGNORECASE)
            return f"{_capitalize_first(subject)} means {answer}."

        if lower.startswith("what is required to "):
            subject = re.sub(r"^What is required to\s+", "", stem, flags=re.IGNORECASE)
            return f"The requirement to {subject} is {answer}."

        if lower.startswith("what is required in "):
            subject = re.sub(r"^What is required in\s+", "", stem, flags=re.IGNORECASE)
            return f"The required item in {subject} is {answer}."

        subject = re.sub(r"^What is\s+", "", stem, flags=re.IGNORECASE)
        return f"{_capitalize_first(subject)} is {answer}."

    if lower.startswith("what are "):
        subject = re.sub(r"^What are\s+", "", stem, flags=re.IGNORECASE)
        return f"{_capitalize_first(subject)} are {answer}."

    if lower.startswith("which of the following "):
        return f"{stem}: {answer}."

    if lower.startswith("how many "):
        return f"{stem}: {answer}."

    if lower.startswith("when must "):
        return f"{stem}: {answer}."

    if lower.startswith("when may "):
        return f"{stem}: {answer}."

    if lower.startswith("under what circumstances may "):
        return f"{stem}: {answer}."

    if lower.startswith("why "):
        if lower.startswith("why is "):
            clause = re.sub(r"^Why is\s+", "", stem, flags=re.IGNORECASE)
            clause = re.sub(r"^this\s+", "", clause, flags=re.IGNORECASE)
            clause = re.sub(r"^it\s+", "", clause, flags=re.IGNORECASE)
            return f"It is {clause} because {answer}."
        if lower.startswith("why are "):
            clause = re.sub(r"^Why are\s+", "", stem, flags=re.IGNORECASE)
            return f"They are {clause} because {answer}."
        clause = re.sub(r"^Why\s+", "", stem, flags=re.IGNORECASE)
        return f"Because {clause}, {answer}."

    return f"{stem}: {answer}."


def _strip_qmark(text: str) -> str:
    return text.rstrip().rstrip("?").strip()


def _capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _normalize_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    text = re.sub(r"\s+:", ":", text)
    if not text.endswith("."):
        text += "."
    return text


def _to_tts(text: str) -> str:
    out = text

    for pattern, replacement in UNIT_PATTERNS.items():
        out = re.sub(pattern, replacement, out)

    for short, expanded in ABBREVIATIONS.items():
        out = re.sub(rf"\b{re.escape(short)}\b", expanded, out)

    out = re.sub(
        r"equivalent isotropically radiated power\s*\(equivalent isotropic radiated power\)",
        "equivalent isotropically radiated power",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"\b1\s*/\s*2(?:\s*-\s*|\s+)wavelength(s?)\b",
        r"half wavelength\1",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"\b1\s*/\s*4(?:\s*-\s*|\s+)wavelength(s?)\b",
        r"quarter wavelength\1",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r"\ban Federal\b", "a Federal", out)
    out = out.replace(";", ",")
    out = out.replace("/", " slash ")
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s+,", ",", out)
    return out.strip()
