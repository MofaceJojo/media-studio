# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Configuration Manager - Singleton pattern

Provides unified access to configuration with automatic validation.
"""
from pathlib import Path
from typing import Any, Optional
from loguru import logger
from .schema import MorpheusVideoStudioConfig
from .loader import load_config_dict, save_config_dict


class ConfigManager:
    """
    Configuration Manager (Singleton)
    
    Provides unified access to configuration with automatic validation.
    """
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls, config_path: str = "config.yaml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config_path: str = "config.yaml"):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
        
        self.config_path = Path(config_path)
        self.config: MorpheusVideoStudioConfig = self._load()
        self._initialized = True
    
    def _load(self) -> MorpheusVideoStudioConfig:
        """Load configuration from file"""
        data = load_config_dict(str(self.config_path))
        config = MorpheusVideoStudioConfig(**data)
        
        # Validate template path exists
        self._validate_template(config.template.default_template)
        
        return config
    
    def _validate_template(self, template_path: str):
        """Validate that the configured template exists"""
        from morpheus_video_studio.utils.template_util import resolve_template_path
        
        try:
            # Try to resolve the template path
            resolved_path = resolve_template_path(template_path)
            logger.debug(f"Template validation passed: {template_path} -> {resolved_path}")
        except FileNotFoundError as e:
            logger.warning(
                f"Configured default template '{template_path}' not found. "
                f"Will fall back to '1080x1920/default.html' if needed. Error: {e}"
            )
    
    def reload(self):
        """Reload configuration from file"""
        self.config = self._load()
        logger.info("Configuration reloaded")
    
    def save(self):
        """Save current configuration to file"""
        save_config_dict(self.config.to_dict(), str(self.config_path))
    
    def update(self, updates: dict):
        """
        Update configuration with new values
        
        Args:
            updates: Dictionary of updates (e.g., {"llm": {"api_key": "xxx"}})
        """
        current = self.config.to_dict()
        
        # Deep merge
        def deep_merge(base: dict, updates: dict) -> dict:
            for key, value in updates.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        merged = deep_merge(current, updates)
        self.config = MorpheusVideoStudioConfig(**merged)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like access (for backward compatibility)"""
        return self.config.to_dict().get(key, default)
    
    def validate(self) -> bool:
        """Validate configuration completeness"""
        return self.config.validate_required()
    
    def get_llm_config(self) -> dict:
        """Get LLM configuration as dict"""
        return {
            "api_key": self.config.llm.api_key,
            "base_url": self.config.llm.base_url,
            "model": self.config.llm.model,
            "timeout_seconds": self.config.llm.timeout_seconds,
        }
    
    def set_llm_config(self, api_key: str, base_url: str, model: str, timeout_seconds: Optional[int] = None):
        """Set LLM configuration"""
        updates = {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }
        if timeout_seconds is not None:
            updates["timeout_seconds"] = int(timeout_seconds)
        self.update({"llm": updates})
    
    def get_comfyui_config(self) -> dict:
        """Get ComfyUI configuration as dict"""
        return {
            "comfyui_url": self.config.comfyui.comfyui_url,
            "comfyui_api_key": self.config.comfyui.comfyui_api_key,
            "tts": {
                "inference_mode": self.config.comfyui.tts.inference_mode,
                "local": {
                    "voice": self.config.comfyui.tts.local.voice,
                    "speed": self.config.comfyui.tts.local.speed,
                },
                "omnivoice": {
                    "base_url": self.config.comfyui.tts.omnivoice.base_url,
                    "model": self.config.comfyui.tts.omnivoice.model,
                    "voice": self.config.comfyui.tts.omnivoice.voice,
                    "speed": self.config.comfyui.tts.omnivoice.speed,
                    "language": self.config.comfyui.tts.omnivoice.language,
                    "instruct": self.config.comfyui.tts.omnivoice.instruct,
                },
                "comfyui": {
                    "default_workflow": self.config.comfyui.tts.comfyui.default_workflow,
                },
                "default_workflow": self.config.comfyui.tts.default_workflow,
            },
            "image": {
                "default_workflow": self.config.comfyui.image.default_workflow,
                "prompt_prefix": self.config.comfyui.image.prompt_prefix,
            },
            "video": {
                "default_workflow": self.config.comfyui.video.default_workflow,
                "prompt_prefix": self.config.comfyui.video.prompt_prefix,
            }
        }

    def get_hyperframe_config(self) -> dict:
        """Get HyperFrame configuration as dict"""
        return {
            "enabled": self.config.hyperframe.enabled,
            "command": self.config.hyperframe.command,
            "quality": self.config.hyperframe.quality,
            "fps": self.config.hyperframe.fps,
            "timeout_seconds": self.config.hyperframe.timeout_seconds,
        }
    
    def set_comfyui_config(
        self, 
        comfyui_url: Optional[str] = None,
        comfyui_api_key: Optional[str] = None,
    ):
        """Set ComfyUI global configuration"""
        updates = {}
        if comfyui_url is not None:
            updates["comfyui_url"] = comfyui_url
        if comfyui_api_key is not None:
            updates["comfyui_api_key"] = comfyui_api_key
        
        if updates:
            self.update({"comfyui": updates})

    def set_hyperframe_config(
        self,
        enabled: Optional[bool] = None,
        command: Optional[str] = None,
        quality: Optional[str] = None,
        fps: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ):
        """Set HyperFrame renderer configuration"""
        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if command is not None:
            updates["command"] = command
        if quality is not None:
            updates["quality"] = quality
        if fps is not None:
            updates["fps"] = fps
        if timeout_seconds is not None:
            updates["timeout_seconds"] = timeout_seconds

        if updates:
            self.update({"hyperframe": updates})

    def get_stock_materials_config(self) -> dict:
        """Get stock material source configuration as dict"""
        return {
            "default_provider": self.config.stock_materials.default_provider,
            "pexels_api_key": self.config.stock_materials.pexels_api_key,
            "pixabay_api_key": self.config.stock_materials.pixabay_api_key,
        }

    def set_stock_materials_config(
        self,
        default_provider: Optional[str] = None,
        pexels_api_key: Optional[str] = None,
        pixabay_api_key: Optional[str] = None,
    ):
        """Set stock material source configuration"""
        updates = {}
        if default_provider is not None:
            updates["default_provider"] = default_provider
        if pexels_api_key is not None:
            updates["pexels_api_key"] = pexels_api_key
        if pixabay_api_key is not None:
            updates["pixabay_api_key"] = pixabay_api_key

        if updates:
            self.update({"stock_materials": updates})

    def get_notebooklm_config(self) -> dict:
        """Get NotebookLM beta configuration as dict"""
        return {
            "enabled": self.config.notebooklm.enabled,
            "profile": self.config.notebooklm.profile,
            "auth_json_path": self.config.notebooklm.auth_json_path,
            "language": self.config.notebooklm.language,
            "report_format": self.config.notebooklm.report_format,
            "timeout_seconds": self.config.notebooklm.timeout_seconds,
            "auto_cleanup_notebook": self.config.notebooklm.auto_cleanup_notebook,
        }

    def set_notebooklm_config(
        self,
        enabled: Optional[bool] = None,
        profile: Optional[str] = None,
        auth_json_path: Optional[str] = None,
        language: Optional[str] = None,
        report_format: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        auto_cleanup_notebook: Optional[bool] = None,
    ):
        """Set NotebookLM beta configuration"""
        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if profile is not None:
            updates["profile"] = profile
        if auth_json_path is not None:
            updates["auth_json_path"] = auth_json_path
        if language is not None:
            updates["language"] = language
        if report_format is not None:
            updates["report_format"] = report_format
        if timeout_seconds is not None:
            updates["timeout_seconds"] = timeout_seconds
        if auto_cleanup_notebook is not None:
            updates["auto_cleanup_notebook"] = auto_cleanup_notebook

        if updates:
            self.update({"notebooklm": updates})

    def get_local_services_config(self) -> dict:
        """Get local one-click service launcher config as dict"""
        return {
            "comfyui": {
                "workdir": self.config.local_services.comfyui.workdir,
                "command": self.config.local_services.comfyui.command,
            },
            "omnivoice": {
                "workdir": self.config.local_services.omnivoice.workdir,
                "command": self.config.local_services.omnivoice.command,
            },
            "web": {
                "workdir": self.config.local_services.web.workdir,
                "command": self.config.local_services.web.command,
            },
        }

    def set_local_services_config(
        self,
        comfyui_workdir: Optional[str] = None,
        comfyui_command: Optional[str] = None,
        omnivoice_workdir: Optional[str] = None,
        omnivoice_command: Optional[str] = None,
        web_workdir: Optional[str] = None,
        web_command: Optional[str] = None,
    ):
        """Set local one-click service launcher config"""
        updates: dict[str, dict[str, str]] = {}
        if comfyui_workdir is not None or comfyui_command is not None:
            updates["comfyui"] = {}
            if comfyui_workdir is not None:
                updates["comfyui"]["workdir"] = comfyui_workdir
            if comfyui_command is not None:
                updates["comfyui"]["command"] = comfyui_command
        if omnivoice_workdir is not None or omnivoice_command is not None:
            updates["omnivoice"] = {}
            if omnivoice_workdir is not None:
                updates["omnivoice"]["workdir"] = omnivoice_workdir
            if omnivoice_command is not None:
                updates["omnivoice"]["command"] = omnivoice_command
        if web_workdir is not None or web_command is not None:
            updates["web"] = {}
            if web_workdir is not None:
                updates["web"]["workdir"] = web_workdir
            if web_command is not None:
                updates["web"]["command"] = web_command

        if updates:
            self.update({"local_services": updates})
