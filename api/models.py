"""Pydantic request/response models for the API."""
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    provider: str = "ollama"          # ollama | openai | anthropic
    model: str | None = None          # override the default model
    api_key: str | None = None        # override env var for this request
    base_url: str | None = None       # override Ollama URL


class SessionInfo(BaseModel):
    session_id: str
    files: list[str]
