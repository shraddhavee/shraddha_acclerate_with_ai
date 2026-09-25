from __future__ import annotations

import importlib
import json

import pytest

import core.config as config
from core.audit import audit_event


def test_dotenv_values_validate_without_printing_key(monkeypatch, capsys):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_" + "x" * 32)
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    loaded = importlib.reload(config)

    loaded.settings.validate(require_api_key=True)
    captured = capsys.readouterr()
    assert "gsk_" not in captured.out + captured.err


def test_invalid_provider_and_missing_required_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "other")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        importlib.reload(config)


def test_audit_redacts_secret_fields(tmp_path):
    secret = "gsk_" + "s" * 32
    audit_event("run", "test", {"api_key": secret, "nested": {"token": secret}}, tmp_path)
    record = json.loads((tmp_path / "run.jsonl").read_text(encoding="utf-8"))
    serialized = json.dumps(record)
    assert secret not in serialized
    assert record["details"]["api_key"] == "[REDACTED]"
    assert record["details"]["nested"]["token"] == "[REDACTED]"