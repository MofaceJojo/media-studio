from web.components.tts_preferences import (
    LOCAL_SPEED_STATE_KEY,
    LOCAL_VOICE_STATE_KEY,
    OMNI_INSTRUCT_STATE_KEY,
    OMNI_MODEL_STATE_KEY,
    OMNI_SPEED_STATE_KEY,
    OMNI_VOICE_STATE_KEY,
    get_local_tts_preferences,
    get_omnivoice_tts_preferences,
    persist_local_tts_preferences,
    persist_omnivoice_tts_preferences,
)


class DummyConfigManager:
    def __init__(self) -> None:
        self.updated: list[dict] = []
        self.saved = 0
        self.config = {
            "tts": {
                "local": {"voice": "zh-CN-YunjianNeural", "speed": 1.2},
                "omnivoice": {
                    "voice": "default",
                    "speed": 1.0,
                    "model": "omnivoice",
                    "instruct": "男，青年",
                },
            }
        }

    def get_comfyui_config(self) -> dict:
        return self.config

    def update(self, updates: dict) -> None:
        self.updated.append(updates)
        local = updates.get("comfyui", {}).get("tts", {}).get("local")
        if local:
            self.config["tts"]["local"].update(local)
        omnivoice = updates.get("comfyui", {}).get("tts", {}).get("omnivoice")
        if omnivoice:
            self.config["tts"]["omnivoice"].update(omnivoice)

    def save(self) -> None:
        self.saved += 1


def test_get_local_tts_preferences_prefers_last_used_session_value() -> None:
    state = {
        LOCAL_VOICE_STATE_KEY: "zh-CN-XiaoxiaoNeural",
        LOCAL_SPEED_STATE_KEY: 1.4,
    }

    voice, speed = get_local_tts_preferences(
        "zh-CN-YunjianNeural",
        1.2,
        state=state,
    )

    assert voice == "zh-CN-XiaoxiaoNeural"
    assert speed == 1.4


def test_get_omnivoice_tts_preferences_prefers_last_used_session_value() -> None:
    state = {
        OMNI_VOICE_STATE_KEY: "demo0001",
        OMNI_SPEED_STATE_KEY: 0.9,
        OMNI_MODEL_STATE_KEY: "omni-v2",
        OMNI_INSTRUCT_STATE_KEY: "女，青年",
    }

    voice, speed, model, instruct = get_omnivoice_tts_preferences(
        "default",
        1.0,
        "omnivoice",
        "男，青年",
        state=state,
    )

    assert voice == "demo0001"
    assert speed == 0.9
    assert model == "omni-v2"
    assert instruct == "女，青年"


def test_persist_local_tts_preferences_updates_config_and_state() -> None:
    state: dict[str, object] = {}
    manager = DummyConfigManager()

    persist_local_tts_preferences(
        "zh-CN-XiaoxiaoNeural",
        1.1,
        state=state,
        manager=manager,
    )

    assert state[LOCAL_VOICE_STATE_KEY] == "zh-CN-XiaoxiaoNeural"
    assert state[LOCAL_SPEED_STATE_KEY] == 1.1
    assert manager.config["tts"]["local"]["voice"] == "zh-CN-XiaoxiaoNeural"
    assert manager.config["tts"]["local"]["speed"] == 1.1
    assert manager.saved == 1


def test_persist_omnivoice_tts_preferences_updates_config_and_state() -> None:
    state: dict[str, object] = {}
    manager = DummyConfigManager()

    persist_omnivoice_tts_preferences(
        "demo0001",
        0.95,
        model="omni-v2",
        instruct="女，青年",
        state=state,
        manager=manager,
    )

    assert state[OMNI_VOICE_STATE_KEY] == "demo0001"
    assert state[OMNI_SPEED_STATE_KEY] == 0.95
    assert state[OMNI_MODEL_STATE_KEY] == "omni-v2"
    assert state[OMNI_INSTRUCT_STATE_KEY] == "女，青年"
    assert manager.config["tts"]["omnivoice"]["voice"] == "demo0001"
    assert manager.config["tts"]["omnivoice"]["speed"] == 0.95
    assert manager.config["tts"]["omnivoice"]["model"] == "omni-v2"
    assert manager.config["tts"]["omnivoice"]["instruct"] == "女，青年"
    assert manager.saved == 1
