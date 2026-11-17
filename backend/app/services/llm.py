"""Вся работа с LLM и эмбеддингами — в одном файле.

Два провайдера:
  * gemini — Google Gemini через официальный SDK google-genai (бесплатный тариф);
  * mock   — локальные детерминированные заглушки: без интернета и без затрат.
             Нужны для автотестов и для демо, когда квота бесплатного тарифа закончилась
             (раздел 9 TSIS 6-7: «use local or mock test responses»).

Сервисы (patient, rag) сами решают, что делать в mock-режиме, через is_mock().
"""
import hashlib
import json
import re
from functools import lru_cache

import numpy as np

from app import config


class LLMError(RuntimeError):
    pass


def is_mock() -> bool:
    return config.LLM_PROVIDER == "mock"


# ---------------------------------------------------------------- Gemini


@lru_cache
def _client():
    from google import genai
    from google.genai import types

    if not config.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set (or use LLM_PROVIDER=mock)")
    return genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=int(config.LLM_TIMEOUT_SECONDS * 1000)),
    )


def generate(
    system: str,
    messages: list[tuple[str, str]],
    *,
    json_mode: bool = False,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> str:
    """messages = [("user", "..."), ("assistant", "..."), ...]. Возвращает текст ответа."""
    if is_mock():
        raise LLMError("generate() is not available in mock mode")
    from google.genai import types

    contents = [
        types.Content(role="model" if role == "assistant" else "user", parts=[types.Part(text=text)])
        for role, text in messages
    ]
    cfg = dict(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    if "2.5" in config.GEMINI_MODEL:
        # «Размышления» модели добавляют секунды — для NFR-02 (≤ 5 с) отключаем
        cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    try:
        resp = _client().models.generate_content(
            model=config.GEMINI_MODEL, contents=contents, config=types.GenerateContentConfig(**cfg)
        )
    except Exception as e:  # сеть, квота, таймаут
        raise LLMError(f"Gemini error: {e}") from e
    text = (resp.text or "").strip()
    if not text:
        raise LLMError("Gemini returned an empty response")
    return text


def generate_json(system: str, prompt: str, **kw) -> dict:
    return parse_json(generate(system, [("user", prompt)], json_mode=True, **kw))


def parse_json(text: str) -> dict:
    """Модель иногда оборачивает JSON в ```json ... ``` — убираем это."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"No JSON object in model output: {text[:200]}")
    return json.loads(text[start : end + 1])


# ---------------------------------------------------------------- Эмбеддинги


def embed(texts: list[str], *, task: str = "document") -> np.ndarray:
    """Вернуть матрицу (len(texts), dim) с L2-нормированными векторами.

    task: "document" — для индексации учебника, "query" — для вопроса пользователя.
    После нормировки косинусное сходство = скалярное произведение.
    """
    if not texts:
        return np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
    vectors = _mock_embed(texts) if is_mock() else _gemini_embed(texts, task)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vectors / norms).astype(np.float32)


def _gemini_embed(texts: list[str], task: str) -> np.ndarray:
    from google.genai import types

    task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):  # лимит API — 100 текстов за запрос
        try:
            resp = _client().models.embed_content(
                model=config.GEMINI_EMBEDDING_MODEL,
                contents=texts[i : i + 100],
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=config.EMBEDDING_DIM
                ),
            )
        except Exception as e:
            raise LLMError(f"Gemini embedding error: {e}") from e
        out.extend(e.values for e in resp.embeddings)
    return np.array(out, dtype=np.float32)


# ---------------------------------------------------------------- Mock

_WORD = re.compile(r"\w+", re.UNICODE)
MOCK_DIM = 512


def tokens(text: str) -> list[str]:
    """Слова в нижнем регистре, обрезанные до 5 букв — грубый стемминг (pain/pains, angina/anginal)."""
    return [w[:5] for w in _WORD.findall(text.lower()) if len(w) > 2]


def _mock_embed(texts: list[str]) -> np.ndarray:
    """Hashing-векторизатор «мешок слов». Похожие тексты → похожие векторы, без сети."""
    m = np.zeros((len(texts), MOCK_DIM), dtype=np.float32)
    for row, text in enumerate(texts):
        for tok in tokens(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            m[row, h % MOCK_DIM] += 1.0
    return m
