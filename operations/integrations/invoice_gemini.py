"""Server-side bridge to Google's official JavaScript SDK; stdout contains JSON only."""
import json
import os
from pathlib import Path
import re
import subprocess
from pydantic import ValidationError
from operations.api_v1.invoice_schemas import InvoiceExtraction
from operations.domain.common import Problem


def response_schema():
    """Use portable JSON Schema shapes; enforce all stricter limits with Pydantic."""
    schema = InvoiceExtraction.model_json_schema()
    definitions = schema.get("$defs", {})

    def portable(node):
        if isinstance(node, list):
            return [portable(value) for value in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return portable(definitions[node["$ref"].split("/")[-1]])
        if "anyOf" in node:
            return {"type": [value["type"] for value in node["anyOf"]]}
        return {key: ({name: portable(value) for name, value in child.items()} if key == "properties" else portable(child))
                for key, child in node.items() if key in {"type", "properties", "required", "items", "enum"}}

    return portable(schema)


class InvoiceGemini:
    def generate(self, source_text, context):
        if not os.environ.get("GEMINI_API_KEY") or not re.fullmatch(r"[\w.\-]+", os.environ.get("GEMINI_MODEL", "")):
            raise Problem("Gemini is not configured. Use manual entry or configure GEMINI_API_KEY and GEMINI_MODEL on the server.", 503)
        script = Path(__file__).resolve().parents[2] / "goob-dispatch/scripts/generate-invoice.mjs"
        try:
            result = subprocess.run([os.environ.get("GOOB_NODE_BINARY", "node"), str(script)],
                input=json.dumps({"source_text": source_text, "context": context, "schema": response_schema()}),
                text=True, capture_output=True, timeout=100, check=False)
            response = json.loads(result.stdout)
            code = response.get("error")
            if code:
                raise Problem({"rate_limit": "Google Gemini is still rate limiting requests after automatic retries. Wait before generating again; if this persists, check the key's model quota in Google AI Studio. Your text is preserved and manual entry remains available.",
                    "unavailable": "Gemini is temporarily overloaded or unavailable. Retry shortly or enter charges manually.",
                    "timeout": "Gemini did not respond within 90 seconds. Your text is preserved; retry or enter charges manually."}.get(code, "Gemini returned an invalid response. Retry or enter charges manually."), 429 if code == "rate_limit" else 503 if code == "unavailable" else 504 if code == "timeout" else 502)
            return InvoiceExtraction.model_validate(response["result"]).model_dump(), {"provider": "gemini", "model": response["model"], "schema_version": 1}
        except subprocess.TimeoutExpired:
            raise Problem("Gemini timed out. Retry or enter charges manually.", 504) from None
        except (OSError, ValueError, KeyError, ValidationError):
            raise Problem("Gemini service unavailable or invalid response. Manual entry remains available.", 502) from None
