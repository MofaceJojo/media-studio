"""Smoke test: the FastAPI app must stay loadable with all routers wired."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_api_app_loads_with_all_routers() -> None:
    from api.app import app

    # Route count varies with optional dependencies (fewer on CI), so we
    # assert only the essential routers that must always be present.
    paths = {getattr(route, "path", "") for route in app.routes}
    assert any("/health" in path for path in paths)
    assert any("/tts" in path for path in paths)
    assert any("/video" in path for path in paths)
