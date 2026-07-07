"""Smoke test: the FastAPI app must stay loadable with all routers wired."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_api_app_loads_with_all_routers() -> None:
    # The API layer needs the full runtime deps (installed on CI via
    # `pip install -e .`); skip in stripped-down local interpreters.
    pytest.importorskip("comfykit")
    # A dependency may ship its own top-level `api` package that shadows
    # this repo's api/ directory (seen on CI); force repo-first resolution.
    for name in [m for m in sys.modules if m == "api" or m.startswith("api.")]:
        del sys.modules[name]
    from api.app import app

    # Route count varies with optional dependencies (fewer on CI), so we
    # assert only the essential routers that must always be present.
    paths = sorted({getattr(route, "path", "") for route in app.routes})
    assert any("/health" in path for path in paths), f"app={app.__module__} routes={paths}"
    assert any("/tts" in path for path in paths), f"routes={paths}"
    assert any("/video" in path for path in paths), f"routes={paths}"
