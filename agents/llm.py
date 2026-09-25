from __future__ import annotations

from typing import Any

from core.config import settings


def generate_text(prompt: str, fallback: str) -> str:
    """Use Groq when configured; never make the pipeline depend on network access."""
    if settings.llm_provider.lower() != "groq" or not settings.groq_api_key:
        return fallback
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        return response.choices[0].message.content or fallback
    except Exception:
        return fallback


def profile_interpretation(profile: dict[str, Any]) -> str:
    return generate_text(
        "Interpret this retail profile and list only concise data-quality uncertainties: " + str(profile),
        "Review null handling, duplicate records, inferred dates, and candidate keys before approval.",
    )
