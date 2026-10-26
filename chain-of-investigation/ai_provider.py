"""Gemini through Google's official OpenAI-compatible endpoint."""
import os
from pathlib import Path

DEFAULT_MODEL = "gemini-3.8-flash"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

def load_settings():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")

def model_name():
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

def create_client():
    load_settings()
    from openai import OpenAI
    key = os.getenv("GEMINI_API_KEY")
    if not key or not key.strip():
        raise ValueError("GEMINI_API_KEY_MISSING")
    return OpenAI(api_key=key.strip(), base_url=BASE_URL, timeout=90.0, max_retries=0)

def error_code(exc):
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return "AI_AUTH_ERROR"
    if status == 429:
        return "AI_RATE_LIMIT_OR_QUOTA"
    if status in (502, 503, 504):
        return "AI_SERVICE_UNAVAILABLE"
    if status == 404:
        return "AI_MODEL_NOT_FOUND"
    if status == 400:
        return "AI_REQUEST_INVALID"
    if isinstance(exc, TimeoutError) or type(exc).__name__ == "APITimeoutError":
        return "AI_TIMEOUT"
    if type(exc).__name__ == "APIConnectionError":
        return "AI_CONNECTION_ERROR"
    return "AI_API_ERROR"
