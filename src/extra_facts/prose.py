from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

import requests
from requests.adapters import HTTPAdapter

from .facts import fact_sentence
from .models import LlmProse, PoolQuestion, ProseMeta, ProseValidation, QuestionPool

PROSE_SCHEMA_VERSION = 1
NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
UNIT_WITH_NUMBER_RE = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*|-)?"
    r"(hz|khz|mhz|ghz|dbm|dbi|db|w|kw|mw|v|kv|a|ma|ua|ohm|ohms|kohm|mohm|"
    r"meter|meters|m|%|percent)\b",
    re.IGNORECASE,
)
UNIT_WORD_RE = re.compile(
    r"\b(hz|khz|mhz|ghz|dbm|dbi|db|meter|meters|percent|ohm|ohms|kohm|mohm)\b",
    re.IGNORECASE,
)
NEGATION_KEYWORDS = (
    "not",
    "must not",
    "except",
    "only",
    "unless",
    "never",
)


class ProseClient(Protocol):
    def generate(
        self,
        question_id: str,
        question_text: str,
        correct_answer: str,
        feedback: str | None = None,
    ) -> tuple[str, float | None]:
        ...


@dataclass(frozen=True)
class ProseRunSummary:
    total: int
    target: int
    generated: int
    accepted: int
    fallback: int
    errors: int


@dataclass(frozen=True)
class ProseProgressUpdate:
    completed: int
    total: int
    accepted: int
    fallback: int
    errors: int
    question_id: str
    status: Literal["accepted", "fallback", "error"]


class OpenAIProseClient:
    def __init__(
        self,
        model: str,
        prompt_version: str,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {api_key_env}")

        self.model = model
        self.prompt_version = prompt_version
        self.api_key = api_key
        self._local = threading.local()

    def generate(
        self,
        question_id: str,
        question_text: str,
        correct_answer: str,
        feedback: str | None = None,
    ) -> tuple[str, float | None]:
        prompt = _prompt(
            question_id,
            question_text,
            correct_answer,
            self.prompt_version,
            feedback=feedback,
        )
        response = self._session().post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": prompt,
                "text": {"format": {"type": "json_object"}},
            },
            timeout=60,
        )
        response.raise_for_status()

        payload = response.json()
        output_text = _extract_output_text(payload)
        data = json.loads(output_text)
        prose_fact = str(data.get("prose_fact", "")).strip()
        confidence = _parse_confidence(data.get("confidence"))
        return prose_fact, confidence

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if isinstance(session, requests.Session):
            return session

        new_session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
        new_session.mount("https://", adapter)
        self._local.session = new_session
        return new_session


def enrich_pool_with_prose(
    pool: QuestionPool,
    client: ProseClient,
    provider: str,
    model: str,
    prompt_version: str,
    max_questions: int | None = None,
    resume: bool = False,
    workers: int = 6,
    max_attempts: int = 3,
    progress_callback: Callable[[ProseProgressUpdate], None] | None = None,
) -> tuple[QuestionPool, ProseRunSummary]:
    questions = list(pool.questions)
    generated = 0
    accepted = 0
    fallback = 0
    errors = 0

    target = _target_count(pool=pool, max_questions=max_questions, resume=resume)
    candidates = _candidate_indices(pool=pool, target=target, resume=resume)

    if workers <= 1:
        for index in candidates:
            question = pool.questions[index]
            llm = _generate_llm_prose(question, client, max_attempts=max_attempts)
            generated, accepted, fallback, errors = _update_counters(
                generated=generated,
                accepted=accepted,
                fallback=fallback,
                errors=errors,
                llm=llm,
            )
            questions[index] = _with_llm(question, llm)
            _emit_progress(
                progress_callback=progress_callback,
                generated=generated,
                total=target,
                accepted=accepted,
                fallback=fallback,
                errors=errors,
                question_id=question.question_id,
                status=llm.status,
            )
    else:
        max_workers = max(1, workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[Future[LlmProse], int] = {
                executor.submit(
                    _generate_llm_prose,
                    pool.questions[index],
                    client,
                    max_attempts,
                ): index
                for index in candidates
            }

            for future in as_completed(futures):
                index = futures[future]
                question = pool.questions[index]
                llm = future.result()
                generated, accepted, fallback, errors = _update_counters(
                    generated=generated,
                    accepted=accepted,
                    fallback=fallback,
                    errors=errors,
                    llm=llm,
                )
                questions[index] = _with_llm(question, llm)
                _emit_progress(
                    progress_callback=progress_callback,
                    generated=generated,
                    total=target,
                    accepted=accepted,
                    fallback=fallback,
                    errors=errors,
                    question_id=question.question_id,
                    status=llm.status,
                )

    enriched = QuestionPool(
        schema_version=pool.schema_version,
        excluded_count=pool.excluded_count,
        questions=questions,
        metadata=pool.metadata,
        prose_schema_version=PROSE_SCHEMA_VERSION,
        prose_meta=ProseMeta(
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            generated_at=datetime.now(UTC).isoformat(),
        ),
    )
    summary = ProseRunSummary(
        total=len(pool.questions),
        target=target,
        generated=generated,
        accepted=accepted,
        fallback=fallback,
        errors=errors,
    )
    return enriched, summary


def validate_prose(question_text: str, correct_answer: str, prose_fact: str) -> ProseValidation:
    source = f"{question_text} {correct_answer}".lower()
    prose = prose_fact.lower()

    source_numbers = {num.replace(",", "") for num in NUM_RE.findall(source)}
    prose_numbers = {num.replace(",", "") for num in NUM_RE.findall(prose)}
    numbers_preserved = source_numbers.issubset(prose_numbers)

    source_units = _extract_units(source)
    prose_units = _extract_units(prose)
    units_preserved = source_units.issubset(prose_units)

    required_negations = _extract_negations(source)
    prose_negations = _extract_negations(prose)
    negation_preserved = required_negations.issubset(prose_negations)

    return ProseValidation(
        numbers_preserved=numbers_preserved,
        units_preserved=units_preserved,
        negation_preserved=negation_preserved,
    )


def _extract_units(text: str) -> set[str]:
    units: set[str] = set()
    for match in UNIT_WITH_NUMBER_RE.finditer(text):
        units.add(_canonical_unit(match.group(1)))
    for match in UNIT_WORD_RE.finditer(text):
        units.add(_canonical_unit(match.group(1)))
    return units


def _extract_negations(text: str) -> set[str]:
    found: set[str] = set()
    for token in NEGATION_KEYWORDS:
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, text):
            found.add(token)
    return found


def _canonical_unit(raw: str) -> str:
    unit = raw.lower()
    if unit in {"m", "meter", "meters"}:
        return "meter"
    if unit in {"%", "percent"}:
        return "percent"
    if unit == "ohms":
        return "ohm"
    return unit


def _fallback_llm_prose(
    question: PoolQuestion,
    source_hash: str,
    validation: ProseValidation,
    status: Literal["fallback", "error"] = "fallback",
    attempt_count: int = 1,
    failure_reasons: list[str] | None = None,
    last_candidate: str | None = None,
    last_error: str | None = None,
) -> LlmProse:
    return LlmProse(
        prose_fact=fact_sentence(question, mode="literal", omit_id=True),
        status=status,
        validation=validation,
        source_hash=source_hash,
        confidence=None,
        attempt_count=attempt_count,
        failure_reasons=failure_reasons,
        last_candidate=last_candidate,
        last_error=last_error,
    )


def _is_valid(validation: ProseValidation) -> bool:
    return (
        validation.numbers_preserved
        and validation.units_preserved
        and validation.negation_preserved
    )


def _source_hash(question: PoolQuestion) -> str:
    basis = f"{question.question_id}\n{question.question_text}\n{question.correct_answer}".encode()
    return f"sha256:{hashlib.sha256(basis).hexdigest()}"


def _parse_confidence(raw: object) -> float | None:
    if isinstance(raw, int | float):
        value = float(raw)
        if 0.0 <= value <= 1.0:
            return value
    return None


def _extract_output_text(payload: dict[str, object]) -> str:
    payload_dict = cast(dict[str, Any], payload)
    output_obj = payload_dict.get("output")
    if not isinstance(output_obj, list):
        raise RuntimeError("Unexpected OpenAI response payload: output is missing")
    output_list = cast(list[Any], output_obj)

    for item_obj in output_list:
        if not isinstance(item_obj, dict):
            continue
        item_dict = cast(dict[str, Any], item_obj)
        content = item_dict.get("content")
        if not isinstance(content, list):
            continue
        content_list = cast(list[Any], content)
        for content_obj in content_list:
            if not isinstance(content_obj, dict):
                continue
            content_dict = cast(dict[str, Any], content_obj)
            text = content_dict.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise RuntimeError("No text output returned by model")


def _prompt(
    question_id: str,
    question_text: str,
    correct_answer: str,
    prompt_version: str,
    feedback: str | None = None,
) -> str:
    prompt = (
        "You are rewriting ham radio exam facts for study clarity. "
        f"Prompt version: {prompt_version}. "
        "Return strict JSON with keys prose_fact and confidence. "
        "Rules: one sentence, declarative tone, preserve every number, unit, "
        "negation, and constraint exactly. "
        "Do not add information, do not mention wrong choices, do not speculate. "
        f"Question ID: {question_id}. Question: {question_text}. Correct answer: {correct_answer}."
    )
    if feedback:
        prompt += f" Validator feedback for retry: {feedback}."
    return prompt


def _target_count(pool: QuestionPool, max_questions: int | None, resume: bool) -> int:
    pending = len(_candidate_indices(pool=pool, target=None, resume=resume))
    if max_questions is None:
        return pending
    return min(max_questions, pending)


def _candidate_indices(pool: QuestionPool, target: int | None, resume: bool) -> list[int]:
    indices: list[int] = []
    for index, question in enumerate(pool.questions):
        if target is not None and len(indices) >= target:
            break
        source_hash = _source_hash(question)
        if resume and question.llm is not None and question.llm.source_hash == source_hash:
            continue
        indices.append(index)
    return indices


def _generate_llm_prose(
    question: PoolQuestion,
    client: ProseClient,
    max_attempts: int = 3,
) -> LlmProse:
    source_hash = _source_hash(question)
    attempts = max(1, max_attempts)
    saw_validation_failure = False
    last_validation = ProseValidation(
        numbers_preserved=False,
        units_preserved=False,
        negation_preserved=False,
    )
    last_candidate: str | None = None
    last_error: str | None = None
    failure_reasons_seen: list[str] = []
    feedback: str | None = None

    for attempt in range(1, attempts + 1):
        try:
            candidate, confidence = client.generate(
                question_id=question.question_id,
                question_text=question.question_text,
                correct_answer=question.correct_answer,
                feedback=feedback,
            )
        except Exception as error:
            last_error = str(error)
            if attempt >= attempts:
                if saw_validation_failure:
                    reasons = failure_reasons_seen or _validation_failures(last_validation)
                    return _fallback_llm_prose(
                        question,
                        source_hash=source_hash,
                        validation=last_validation,
                        attempt_count=attempt,
                        failure_reasons=reasons,
                        last_candidate=last_candidate,
                        last_error=last_error,
                    )
                return _fallback_llm_prose(
                    question,
                    source_hash=source_hash,
                    validation=last_validation,
                    status="error",
                    attempt_count=attempt,
                    failure_reasons=failure_reasons_seen or ["llm_error"],
                    last_candidate=last_candidate,
                    last_error=last_error,
                )
            feedback = _error_feedback(error, attempt=attempt, max_attempts=attempts)
            continue

        last_candidate = candidate
        validation = validate_prose(
            question_text=question.question_text,
            correct_answer=question.correct_answer,
            prose_fact=candidate,
        )
        if _is_valid(validation):
            return LlmProse(
                prose_fact=candidate,
                status="accepted",
                validation=validation,
                source_hash=source_hash,
                confidence=confidence,
                attempt_count=attempt,
                failure_reasons=failure_reasons_seen or None,
                last_candidate=last_candidate,
                last_error=last_error,
            )
        saw_validation_failure = True
        last_validation = validation
        failure_reasons_seen = _merge_failure_reasons(
            failure_reasons_seen,
            _validation_failures(validation),
        )
        if attempt < attempts:
            feedback = _validation_feedback(
                validation=validation,
                candidate=candidate,
                attempt=attempt,
                max_attempts=attempts,
                question_text=question.question_text,
                correct_answer=question.correct_answer,
            )

    return _fallback_llm_prose(
        question,
        source_hash=source_hash,
        validation=last_validation,
        attempt_count=attempts,
        failure_reasons=failure_reasons_seen or _validation_failures(last_validation),
        last_candidate=last_candidate,
        last_error=last_error,
    )


def _merge_failure_reasons(existing: list[str], new_reasons: list[str]) -> list[str]:
    merged = list(existing)
    seen = set(merged)
    for reason in new_reasons:
        if reason in seen:
            continue
        merged.append(reason)
        seen.add(reason)
    return merged


def _validation_failures(validation: ProseValidation) -> list[str]:
    failures: list[str] = []
    if not validation.numbers_preserved:
        failures.append("numbers")
    if not validation.units_preserved:
        failures.append("units")
    if not validation.negation_preserved:
        failures.append("negation")
    return failures


def _validation_feedback(
    validation: ProseValidation,
    candidate: str,
    attempt: int,
    max_attempts: int,
    question_text: str,
    correct_answer: str,
) -> str:
    failure_map = {
        "numbers": "Missing or changed numeric values",
        "units": "Missing or changed units",
        "negation": "Missing or changed negation or constraint wording",
    }
    failure_keys = _validation_failures(validation)
    failures = [failure_map[failure] for failure in failure_keys]
    details = _validation_feedback_details(
        failure_keys=failure_keys,
        question_text=question_text,
        correct_answer=correct_answer,
        candidate=candidate,
    )

    joined_failures = "; ".join(failures) if failures else "Validation did not pass"
    detail_suffix = f" Missing details: {details}." if details else ""
    return (
        f"Attempt {attempt}/{max_attempts} failed validation: {joined_failures}. "
        f"Previous prose was: {candidate!r} "
        f"Revise to preserve all numbers, units, negations, and constraints exactly.{detail_suffix}"
    )


def _error_feedback(error: Exception, attempt: int, max_attempts: int) -> str:
    return (
        f"Attempt {attempt}/{max_attempts} failed with API/parsing error: {error}. "
        "Retry with strict JSON and one valid prose_fact sentence."
    )


def _validation_feedback_details(
    failure_keys: list[str],
    question_text: str,
    correct_answer: str,
    candidate: str,
) -> str:
    source = f"{question_text} {correct_answer}".lower()
    prose = candidate.lower()
    details: list[str] = []
    if "numbers" in failure_keys:
        source_numbers = {num.replace(",", "") for num in NUM_RE.findall(source)}
        prose_numbers = {num.replace(",", "") for num in NUM_RE.findall(prose)}
        missing_numbers = sorted(source_numbers - prose_numbers)
        if missing_numbers:
            details.append("numbers=" + ", ".join(missing_numbers))
    if "units" in failure_keys:
        missing_units = sorted(_extract_units(source) - _extract_units(prose))
        if missing_units:
            details.append("units=" + ", ".join(missing_units))
    if "negation" in failure_keys:
        missing_negations = sorted(_extract_negations(source) - _extract_negations(prose))
        if missing_negations:
            details.append("negations=" + ", ".join(missing_negations))
    return "; ".join(details)


def _with_llm(question: PoolQuestion, llm: LlmProse) -> PoolQuestion:
    return PoolQuestion(
        question_id=question.question_id,
        question_text=question.question_text,
        choices=question.choices,
        correct_choice_index=question.correct_choice_index,
        group=question.group,
        subelement=question.subelement,
        llm=llm,
    )


def _update_counters(
    generated: int,
    accepted: int,
    fallback: int,
    errors: int,
    llm: LlmProse,
) -> tuple[int, int, int, int]:
    generated += 1
    if llm.status == "accepted":
        accepted += 1
    elif llm.status == "fallback":
        fallback += 1
    else:
        errors += 1
    return generated, accepted, fallback, errors


def _emit_progress(
    progress_callback: Callable[[ProseProgressUpdate], None] | None,
    generated: int,
    total: int,
    accepted: int,
    fallback: int,
    errors: int,
    question_id: str,
    status: Literal["accepted", "fallback", "error"],
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        ProseProgressUpdate(
            completed=generated,
            total=total,
            accepted=accepted,
            fallback=fallback,
            errors=errors,
            question_id=question_id,
            status=status,
        )
    )
