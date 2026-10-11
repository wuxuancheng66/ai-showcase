"""Public example configuration. Credentials are read only from environment."""
import os

def load_api_key():
    return os.environ.get("DEEPSEEK_API_KEY", "").strip()

MODEL_SOURCE = "cloud"
CLOUD_BASE_URL = "https://api.deepseek.com"
CLOUD_MODEL = "deepseek-chat"
LOCAL_BASE_URL = "http://localhost:1234/v1"
LOCAL_MODEL = "deepseek-r1-distill-qwen-7b"

def get_config():
    source = os.environ.get("POLICY_MODEL_SOURCE", MODEL_SOURCE).strip()
    if source == "local":
        return (os.environ.get("POLICY_LOCAL_BASE_URL", LOCAL_BASE_URL),
                "lm-studio", os.environ.get("POLICY_LOCAL_MODEL", LOCAL_MODEL))
    if source != "cloud":
        raise RuntimeError("POLICY_MODEL_SOURCE must be cloud or local")
    key = load_api_key()
    if not key:
        raise RuntimeError("Set DEEPSEEK_API_KEY in your environment before cloud requests")
    return CLOUD_BASE_URL, key, CLOUD_MODEL
