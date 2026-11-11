"""LLM providers: one tiny interface, so the model/service can be swapped.

A provider only knows how to turn (system prompt, user prompt) into text.
Everything else (prompts, parsing, validation) lives in generate.py and does
not depend on which provider is used. No Streamlit here.

To add a provider (another local runtime or an API service): subclass
`Provider`, implement `generate_text`, and raise `ProviderError` with a clear
Hebrew message on any failure.

Ollama settings come from environment variables (nothing is hardcoded):
    CONQUEST_OLLAMA_MODEL   model name, e.g. the name shown by `ollama list` (required)
    CONQUEST_OLLAMA_URL     server address (default http://localhost:11434)
    CONQUEST_OLLAMA_TIMEOUT seconds to wait for one answer (default 180)
"""

import json
import os
import socket
import urllib.error
import urllib.request

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_TIMEOUT = 180


class ProviderError(Exception):
    """The provider could not answer. The message is in Hebrew and safe to show."""


class ProviderUnavailable(ProviderError):
    """The provider is not reachable or not configured: retrying other chunks is pointless."""


class Provider:
    name = "provider"

    def generate_text(self, system_prompt, user_prompt):
        """Return the model's text answer (we ask for JSON). Raise ProviderError on failure."""
        raise NotImplementedError


class OllamaProvider(Provider):
    """Talks to a local Ollama server through its HTTP API (/api/chat). Needs no extra package."""

    def __init__(self, model, base_url=DEFAULT_OLLAMA_URL, timeout=DEFAULT_OLLAMA_TIMEOUT):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.name = f"Ollama ({model})"

    def generate_text(self, system_prompt, user_prompt):
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",                      # ask Ollama to return valid JSON
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise ProviderUnavailable(
                    f"המודל '{self.model}' לא נמצא ב-Ollama. בדקו את השם עם הפקודה ollama list "
                    "והתקינו אותו ידנית אם צריך (המערכת לא מורידה מודלים)."
                ) from error
            raise ProviderError(f"Ollama החזיר שגיאה (קוד {error.code}).") from error
        except (socket.timeout, TimeoutError) as error:
            raise ProviderError("Ollama לא הגיב בזמן. נסו מודל קטן יותר או מקטע קצר יותר.") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise ProviderError("Ollama לא הגיב בזמן. נסו מודל קטן יותר או מקטע קצר יותר.") from error
            raise ProviderUnavailable(
                f"לא ניתן להתחבר לשרת Ollama בכתובת {self.base_url}. "
                "ודאו ש-Ollama מותקן ופועל."
            ) from error
        except (OSError, ValueError) as error:
            raise ProviderError("התקבלה תשובה לא תקינה משרת Ollama.") from error

        text = (body.get("message") or {}).get("content") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("Ollama החזיר תשובה ריקה.")
        return text


class MockProvider(Provider):
    """For tests: returns a fixed text (or the result of a function), never touches the network."""

    name = "Mock"

    def __init__(self, responder):
        """responder: a string, or a function (system_prompt, user_prompt) -> string.
        A function may raise ProviderError to simulate a failure."""
        self.responder = responder
        self.calls = []

    def generate_text(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if callable(self.responder):
            return self.responder(system_prompt, user_prompt)
        return self.responder


def provider_from_env(environ=None):
    """Build the Ollama provider from environment variables, or raise ProviderUnavailable."""
    env = os.environ if environ is None else environ
    model = (env.get("CONQUEST_OLLAMA_MODEL") or "").strip()
    if not model:
        raise ProviderUnavailable(
            "לא הוגדר מודל. הגדירו את משתנה הסביבה CONQUEST_OLLAMA_MODEL לשם מודל "
            "שמותקן אצלכם ב-Ollama (ראו ollama list) והפעילו מחדש את האפליקציה."
        )
    url = (env.get("CONQUEST_OLLAMA_URL") or DEFAULT_OLLAMA_URL).strip()
    try:
        timeout = float(env.get("CONQUEST_OLLAMA_TIMEOUT") or DEFAULT_OLLAMA_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_OLLAMA_TIMEOUT
    return OllamaProvider(model, url, timeout)
