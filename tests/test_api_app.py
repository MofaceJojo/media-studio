"""Smoke test: the FastAPI app must stay loadable with all routers wired."""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_repo_api_package():
    """Bind 'api' to this repo's api/ package by explicit file path.

    On CI a site-packages dependency can shadow the bare 'api' name, which
    silently loads the wrong app; path-based loading is immune to that.
    """
    for name in [m for m in sys.modules if m == "api" or m.startswith("api.")]:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        "api",
        _REPO_ROOT / "api" / "__init__.py",
        submodule_search_locations=[str(_REPO_ROOT / "api")],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["api"] = module
    spec.loader.exec_module(module)


def test_api_app_loads_with_all_routers() -> None:
    # The API layer needs the full runtime deps (installed on CI via
    # `pip install -e .`); skip in stripped-down local interpreters.
    pytest.importorskip("comfykit")
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    _load_repo_api_package()
    from api.app import app

    paths = sorted({getattr(route, "path", "") for route in app.routes})
    assert any("/health" in path for path in paths), f"routes={paths}"
    assert any("/tts" in path for path in paths), f"routes={paths}"
    assert any("/video" in path for path in paths), f"routes={paths}"
