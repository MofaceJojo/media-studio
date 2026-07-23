from pathlib import Path

from morpheus_video_studio.config.manager import ConfigManager
from morpheus_video_studio.utils.service_launcher import detect_default_service_command


def test_detect_default_web_command_prefers_venv_streamlit(tmp_path: Path) -> None:
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "streamlit").write_text("", encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "app.py").write_text("print('ok')", encoding="utf-8")

    command = detect_default_service_command("web", str(tmp_path))

    assert command == ".venv/bin/streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501"


def test_local_services_config_includes_web_entry(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("project_name: Test Studio\n", encoding="utf-8")

    ConfigManager._instance = None
    manager = ConfigManager(str(config_path))
    manager.set_local_services_config(
        web_workdir="/tmp/media-studio",
        web_command="streamlit run web/app.py",
    )

    services = manager.get_local_services_config()

    assert services["web"]["workdir"] == "/tmp/media-studio"
    assert services["web"]["command"] == "streamlit run web/app.py"
