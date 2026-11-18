"""Local ad-vision settings; credentials are protected by Windows current-user DPAPI."""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import urllib.parse


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "ad_ai.dat"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"


def unprotect(encoded):
    if os.name != "nt":
        raise ValueError("Windows current-user credentials are required")
    raw = base64.b64decode(encoded, validate=True)
    if not raw or len(raw) > 16384:
        raise ValueError("Invalid protected credential")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt, kernel = ctypes.WinDLL("crypt32", use_last_error=True), ctypes.WinDLL("kernel32")
    crypt.CryptUnprotectData.argtypes = [
        ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [ctypes.c_void_p], ctypes.c_void_p
    if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError("Cannot unlock credential for the current Windows user")
    try:
        return ctypes.string_at(target.data, target.size).decode("utf-8")
    finally:
        kernel.LocalFree(target.data)


def load_config(path=None):
    path = CONFIG_PATH if path is None else Path(path)
    if not path.is_file():
        return None
    if path.stat().st_size > 32768:
        raise ValueError("Advertisement settings exceed limit")
    raw = json.loads(path.read_text("utf-8-sig"))
    if (not isinstance(raw, dict) or set(raw) != {"version", "enabled", "endpoint", "model", "protected_key"}
            or raw["version"] != 1 or type(raw["enabled"]) is not bool):
        raise ValueError("Invalid advertisement settings")
    if not raw["enabled"]:
        return None
    values = {key: raw[key] for key in ("endpoint", "model", "protected_key")}
    if not all(isinstance(value, str) and value and value.strip() == value for value in values.values()):
        raise ValueError("Complete advertisement settings are required")
    parsed = urllib.parse.urlsplit(values["endpoint"])
    if (parsed.scheme != "https" or parsed.hostname != "api.deepseek.com"
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path != "/chat/completions"):
        raise ValueError("Only the configured official DeepSeek endpoint is supported")
    key = unprotect(values["protected_key"])
    if not key or key.strip() != key or "\r" in key or "\n" in key:
        raise ValueError("Invalid advertisement credential")
    return {"endpoint": values["endpoint"], "model": values["model"], "api_key": key}
