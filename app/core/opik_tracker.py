import os
import opik
from opik import track, opik_context
from app.config import settings

_opik_configured = False

def init_opik():
    global _opik_configured
    try:
        if settings.opik_api_key:
            opik.configure(use_local=False, api_key=settings.opik_api_key, workspace=settings.opik_workspace)
            _opik_configured = True
        else:
            # Avoid interactive prompts: only configure local if a URL is provided via env.
            local_url = os.environ.get("OPIK_URL")
            if local_url:
                opik.configure(use_local=True, url=local_url)
                _opik_configured = True
    except Exception:
        _opik_configured = False

def get_trace_id() -> str | None:
    try:
        return opik_context.get_current_trace_id()
    except Exception:
        return None

def update_trace_metadata(metadata: dict):
    try:
        opik_context.update_current_trace(metadata=metadata)
    except Exception:
        pass

def traced(name: str):
    """Apply Opik's @track only when Opik is configured, so unconfigured
    deployments don't try (and fail) to ship traces on every call."""
    def decorator(fn):
        if _opik_configured:
            return track(name=name, project_name=settings.opik_project_name)(fn)
        return fn
    return decorator

init_opik()
