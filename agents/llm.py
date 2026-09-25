from __future__ import annotations

from typing import Any

from core.config import settings


def _invoke_groq(prompt: str) -> str:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=300,
    )
    return response.choices[0].message.content or ""


def generate_text(prompt: str, fallback: str) -> str:
    """Run an optional LangChain prompt chain backed by Groq."""
    if settings.llm_provider.lower() != "groq" or not settings.groq_api_key:
        return fallback
    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import PromptTemplate
        from langchain_core.runnables import RunnableLambda

        chain = (
            PromptTemplate.from_template("{prompt}")
            | RunnableLambda(lambda values: _invoke_groq(values["prompt"]))
            | StrOutputParser()
        )
        return chain.invoke({"prompt": prompt}) or fallback
    except Exception:
        return fallback


def profile_interpretation(profile: dict[str, Any]) -> str:
    return generate_text(
        "Interpret this retail profile and list only concise data-quality uncertainties: " + str(profile),
        "Review null handling, duplicate records, inferred dates, and candidate keys before approval.",
    )


def suggest_transformation(
    source_column: str,
    datatype: str,
    layer: str,
    business_intent: str,
    fallback: str,
) -> str:
    prompt = (
        "Suggest one concise, safe transformation for an approved human-reviewed STTM row. "
        f"Layer={layer}; source_column={source_column}; datatype={datatype}; "
        f"business_intent={business_intent or 'general retail analysis'}. "
        "Return only the transformation instruction."
    )
    return generate_text(prompt, fallback)
