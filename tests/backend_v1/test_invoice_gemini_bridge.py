"""Provider failures are mocked; verify deadlines and safe API error reporting."""
import json
import subprocess
from types import SimpleNamespace
import pytest
from operations.domain.common import Problem
from operations.integrations.invoice_gemini import InvoiceGemini

@pytest.mark.parametrize("code,status", [("timeout",504),("rate_limit",429),("unavailable",503)])
def test_provider_failure_and_deadline(monkeypatch, code, status):
    monkeypatch.setenv("GEMINI_API_KEY","test-only-key")
    monkeypatch.setenv("GEMINI_MODEL","test-model")
    def run(*args, **kwargs):
        assert kwargs["timeout"] == 100
        assert kwargs["capture_output"]
        return SimpleNamespace(stdout=json.dumps({"error":code}))
    monkeypatch.setattr(subprocess,"run",run)
    with pytest.raises(Problem) as failure:
        InvoiceGemini().generate("Sink $150",{})
    assert failure.value.status == status
    assert "test-only-key" not in failure.value.message

def test_process_deadline_is_timeout(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY","test-only-key")
    monkeypatch.setenv("GEMINI_MODEL","test-model")
    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired("node",100)
    monkeypatch.setattr(subprocess,"run",run)
    with pytest.raises(Problem) as failure:
        InvoiceGemini().generate("Sink $150",{})
    assert failure.value.status == 504
