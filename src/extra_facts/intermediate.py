from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from .models import (
    LlmProse,
    ParsedQuestion,
    PoolMetadata,
    PoolQuestion,
    ProseMeta,
    ProseValidation,
    QuestionImage,
    QuestionPool,
)

CHOICE_ORDER = ("A", "B", "C", "D")
SCHEMA_VERSION = 1


def to_question_pool(
    parsed_questions: list[ParsedQuestion],
    excluded_count: int = 0,
    metadata: PoolMetadata | None = None,
) -> QuestionPool:
    questions: list[PoolQuestion] = []
    for parsed in parsed_questions:
        choices = [parsed.choices[label] for label in CHOICE_ORDER]
        correct_choice_index = CHOICE_ORDER.index(parsed.correct_choice)
        questions.append(
            PoolQuestion(
                question_id=parsed.question_id,
                question_text=parsed.question_text,
                choices=choices,
                correct_choice_index=correct_choice_index,
                group=parsed.group,
                subelement=parsed.subelement,
                image_paths=parsed.image_paths,
                images=[QuestionImage(path=image_path) for image_path in parsed.image_paths],
            )
        )
    return QuestionPool(
        schema_version=SCHEMA_VERSION,
        excluded_count=excluded_count,
        questions=questions,
        metadata=metadata,
    )


def write_question_pool(pool: QuestionPool, target: Path) -> None:
    payload: dict[str, object] = {
        "schema_version": pool.schema_version,
        "excluded_count": pool.excluded_count,
        "metadata": _serialize_pool_metadata(pool.metadata),
        "prose_schema_version": pool.prose_schema_version,
        "prose_meta": _serialize_prose_meta(pool.prose_meta),
        "questions": [
            {
                "question_id": question.question_id,
                "question_text": question.question_text,
                "choices": question.choices,
                "correct_choice_index": question.correct_choice_index,
                "group": question.group,
                "subelement": question.subelement,
                "image_paths": question.image_paths,
                "images": _serialize_question_images(question.images),
                "llm": _serialize_llm_prose(question.llm),
            }
            for question in pool.questions
        ],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_question_pool(path: Path) -> QuestionPool:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    questions_payload = cast(list[dict[str, Any]], payload["questions"])

    questions = [
        _deserialize_pool_question(question_payload)
        for question_payload in questions_payload
    ]

    return QuestionPool(
        schema_version=int(payload["schema_version"]),
        excluded_count=int(payload.get("excluded_count", 0)),
        questions=questions,
        metadata=_deserialize_pool_metadata(payload.get("metadata")),
        prose_schema_version=(
            int(payload["prose_schema_version"]) if payload.get("prose_schema_version") else None
        ),
        prose_meta=_deserialize_prose_meta(payload.get("prose_meta")),
    )


def group_pool_questions(questions: list[PoolQuestion]) -> dict[str, list[PoolQuestion]]:
    grouped: dict[str, list[PoolQuestion]] = {}
    for question in questions:
        grouped.setdefault(question.group, []).append(question)
    return grouped


def _serialize_llm_prose(llm: LlmProse | None) -> dict[str, object] | None:
    if llm is None:
        return None
    return {
        "prose_fact": llm.prose_fact,
        "status": llm.status,
        "validation": {
            "numbers_preserved": llm.validation.numbers_preserved,
            "units_preserved": llm.validation.units_preserved,
            "negation_preserved": llm.validation.negation_preserved,
        },
        "source_hash": llm.source_hash,
        "confidence": llm.confidence,
        "attempt_count": llm.attempt_count,
        "failure_reasons": llm.failure_reasons,
        "last_candidate": llm.last_candidate,
        "last_error": llm.last_error,
    }


def _deserialize_llm_prose(payload: object) -> LlmProse | None:
    if not isinstance(payload, dict):
        return None
    payload_dict = cast(dict[str, Any], payload)

    validation_payload = payload_dict.get("validation")
    if not isinstance(validation_payload, dict):
        return None
    validation_dict = cast(dict[str, Any], validation_payload)

    raw_status = payload_dict.get("status")
    status = raw_status if raw_status in {"accepted", "fallback", "error"} else "fallback"

    return LlmProse(
        prose_fact=str(payload_dict.get("prose_fact", "")),
        status=status,
        validation=ProseValidation(
            numbers_preserved=bool(validation_dict.get("numbers_preserved", False)),
            units_preserved=bool(validation_dict.get("units_preserved", False)),
            negation_preserved=bool(validation_dict.get("negation_preserved", False)),
        ),
        source_hash=str(payload_dict.get("source_hash", "")),
        confidence=_to_float_or_none(payload_dict.get("confidence")),
        attempt_count=int(payload_dict.get("attempt_count", 1)),
        failure_reasons=_to_str_list_or_none(payload_dict.get("failure_reasons")),
        last_candidate=_to_str_or_none(payload_dict.get("last_candidate")),
        last_error=_to_str_or_none(payload_dict.get("last_error")),
    )


def _serialize_question_images(images: list[QuestionImage]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for image in images:
        image_payload: dict[str, str] = {}
        if image.path:
            image_payload["path"] = image.path
        if image.data_base64:
            image_payload["data_base64"] = image.data_base64
        if image.data_url:
            image_payload["data_url"] = image.data_url
        if image.media_type:
            image_payload["media_type"] = image.media_type
        if image_payload:
            payload.append(image_payload)
    return payload


def _deserialize_pool_question(question_payload: dict[str, Any]) -> PoolQuestion:
    image_paths = _to_str_list(question_payload.get("image_paths"))
    images = _deserialize_question_images(question_payload.get("images"))
    if not images and image_paths:
        images = [QuestionImage(path=image_path) for image_path in image_paths]
    if not image_paths:
        image_paths = [image.path for image in images if image.path is not None]

    return PoolQuestion(
        question_id=question_payload["question_id"],
        question_text=question_payload["question_text"],
        choices=list(question_payload["choices"]),
        correct_choice_index=int(question_payload["correct_choice_index"]),
        group=question_payload["group"],
        subelement=question_payload["subelement"],
        image_paths=image_paths,
        images=images,
        llm=_deserialize_llm_prose(question_payload.get("llm")),
    )


def _deserialize_question_images(payload: object) -> list[QuestionImage]:
    if not isinstance(payload, list):
        return []

    images: list[QuestionImage] = []
    for item in cast(list[object], payload):
        if isinstance(item, str):
            if item.startswith("data:"):
                images.append(QuestionImage(data_url=item))
            else:
                images.append(QuestionImage(path=item))
            continue
        if not isinstance(item, dict):
            continue
        item_dict = cast(dict[str, Any], item)
        path = _first_str(item_dict, "path", "image_path", "src")
        data_base64 = _first_str(item_dict, "data_base64", "base64", "data")
        data_url = _first_str(item_dict, "data_url", "data_uri", "dataUri")
        media_type = _first_str(item_dict, "media_type", "mime_type", "content_type")
        if path or data_base64 or data_url:
            images.append(
                QuestionImage(
                    path=path,
                    data_base64=data_base64,
                    data_url=data_url,
                    media_type=media_type,
                )
            )
    return images


def _serialize_prose_meta(meta: ProseMeta | None) -> dict[str, object] | None:
    if meta is None:
        return None
    return {
        "provider": meta.provider,
        "model": meta.model,
        "prompt_version": meta.prompt_version,
        "generated_at": meta.generated_at,
    }


def _deserialize_prose_meta(payload: object) -> ProseMeta | None:
    if not isinstance(payload, dict):
        return None
    payload_dict = cast(dict[str, Any], payload)
    return ProseMeta(
        provider=str(payload_dict.get("provider", "")),
        model=str(payload_dict.get("model", "")),
        prompt_version=str(payload_dict.get("prompt_version", "")),
        generated_at=str(payload_dict.get("generated_at", "")),
    )


def _serialize_pool_metadata(meta: PoolMetadata | None) -> dict[str, object] | None:
    if meta is None:
        return None
    return {
        "subelement_titles": meta.subelement_titles,
        "group_titles": meta.group_titles,
        "subelement_friendly_titles": meta.subelement_friendly_titles,
        "group_friendly_titles": meta.group_friendly_titles,
    }


def _deserialize_pool_metadata(payload: object) -> PoolMetadata | None:
    if not isinstance(payload, dict):
        return None
    payload_dict = cast(dict[str, Any], payload)
    return PoolMetadata(
        subelement_titles=_to_str_map(payload_dict.get("subelement_titles")),
        group_titles=_to_str_map(payload_dict.get("group_titles")),
        subelement_friendly_titles=_to_str_map(payload_dict.get("subelement_friendly_titles")),
        group_friendly_titles=_to_str_map(payload_dict.get("group_friendly_titles")),
    )


def _to_float_or_none(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _to_str_or_none(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _to_str_list_or_none(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            items.append(item)
    return items




def _to_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            items.append(item)
    return items

def _to_str_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(item, str):
            result[key] = item
    return result


def _first_str(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None
