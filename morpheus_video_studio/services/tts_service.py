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
TTS (Text-to-Speech) Service - Supports both local and ComfyUI inference
"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Optional

import httpx
from comfykit import ComfyKit
from loguru import logger

from morpheus_video_studio.services.comfy_base_service import ComfyBaseService
from morpheus_video_studio.utils.omnivoice_util import (
    fetch_omnivoice_model_status,
    format_omnivoice_error,
    generate_omnivoice_openai_speech,
    normalize_omnivoice_instruct,
)
from morpheus_video_studio.utils.tts_util import edge_tts
from morpheus_video_studio.tts_voices import speed_to_rate


class TTSService(ComfyBaseService):
    """
    TTS (Text-to-Speech) service - Workflow-based
    
    Uses ComfyKit to execute TTS workflows.
    
    Usage:
        # Use default workflow
        audio_path = await morpheus_video_studio.tts(text="Hello, world!")
        
        # Use specific workflow
        audio_path = await morpheus_video_studio.tts(
            text="你好，世界！",
            workflow="tts_edge.json"
        )
        
        # List available workflows
        workflows = morpheus_video_studio.tts.list_workflows()
    """
    
    WORKFLOW_PREFIX = "tts_"
    DEFAULT_WORKFLOW = None  # No hardcoded default, must be configured
    WORKFLOWS_DIR = "workflows"
    OMNIVOICE_TIMEOUT_READY_SECONDS = 600.0
    OMNIVOICE_TIMEOUT_COLD_START_SECONDS = 1200.0
    _OMNIVOICE_FORMAT_ALIASES = {
        ".mp3": "mp3",
        ".wav": "wav",
        ".flac": "flac",
        ".ogg": "opus",
        ".opus": "opus",
        ".aac": "aac",
        ".m4a": "aac",
        ".pcm": "pcm",
    }

    @staticmethod
    def _is_omnivoice_stuck_status(model_status: Optional[dict]) -> bool:
        """Detect the pseudo-ready state where Omni reports ready but never finishes loading."""
        if not model_status:
            return False
        detail = (model_status.get("detail") or model_status.get("sub_stage") or "").strip()
        return (
            bool(model_status.get("loading"))
            and not bool(model_status.get("loaded"))
            and detail == "Model ready"
        )

    @classmethod
    def _infer_omnivoice_response_format(cls, output_path: Optional[str], requested_format: str) -> str:
        if output_path:
            suffix = Path(output_path).suffix.lower()
            if suffix in cls._OMNIVOICE_FORMAT_ALIASES:
                return cls._OMNIVOICE_FORMAT_ALIASES[suffix]
        return requested_format
    
    def __init__(self, config: dict, core=None):
        """
        Initialize TTS service
        
        Args:
            config: Full application config dict
            core: MorpheusVideoStudioCore instance (for accessing shared ComfyKit)
        """
        super().__init__(config, service_name="tts", core=core)
        # Backward/forward compatibility: older service code expects
        # comfyui.tts.default_workflow, while the UI stores it under
        # comfyui.tts.comfyui.default_workflow.
        if not self.config.get("default_workflow"):
            nested_default = self.config.get("comfyui", {}).get("default_workflow")
            if nested_default:
                self.config["default_workflow"] = nested_default
    
    
    async def __call__(
        self,
        text: str,
        workflow: Optional[str] = None,
        # ComfyUI connection (optional overrides)
        comfyui_url: Optional[str] = None,
        # TTS parameters
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        # Inference mode override
        inference_mode: Optional[str] = None,
        # Output path
        output_path: Optional[str] = None,
        **params
    ) -> str:
        """
        Generate speech using local Edge TTS, OmniVoice, or ComfyUI workflow
        
        Args:
            text: Text to convert to speech
            workflow: Workflow filename (for ComfyUI mode, default: from config)
            comfyui_url: ComfyUI URL (optional, overrides config)
            voice: Voice ID (for local mode: Edge TTS voice ID; for ComfyUI: workflow-specific)
            speed: Speech speed multiplier (1.0 = normal, >1.0 = faster, <1.0 = slower)
            inference_mode: Override inference mode ("local", "omnivoice", or "comfyui", default: from config)
            output_path: Custom output path (auto-generated if None)
            **params: Additional workflow parameters
        
        Returns:
            Generated audio file path
        
        Examples:
            # Local inference (Edge TTS)
            audio_path = await morpheus_video_studio.tts(
                text="Hello, world!",
                inference_mode="local",
                voice="zh-CN-YunjianNeural",
                speed=1.2
            )
            
            # ComfyUI inference
            audio_path = await morpheus_video_studio.tts(
                text="你好，世界！",
                inference_mode="comfyui",
                workflow="selfhost/tts_edge.json"
            )
        """
        # Determine inference mode (param > config)
        mode = inference_mode or self.config.get("inference_mode", "local")
        
        # Route to appropriate implementation
        if mode == "local":
            return await self._call_local_tts(
                text=text,
                voice=voice,
                speed=speed,
                output_path=output_path
            )
        if mode == "omnivoice":
            try:
                return await self._call_omnivoice_tts(
                    text=text,
                    voice=voice,
                    speed=speed,
                    output_path=output_path,
                    **params
                )
            except Exception as exc:
                # OmniVoice is the flaky link (pseudo-ready hang, upstream 5xx).
                # Its stuck state is detected and raised instantly, so instead of
                # failing the whole render, degrade to Edge TTS for this segment
                # and keep going. Edge ignores the OmniVoice voice/instruct, so
                # fall back to the configured local voice.
                logger.warning(
                    f"OmniVoice TTS failed ({exc}); falling back to Edge TTS for this segment."
                )
                return await self._call_local_tts(
                    text=text,
                    voice=None,
                    speed=speed,
                    output_path=output_path,
                )
        else:  # comfyui
            # 1. Resolve workflow (returns structured info)
            workflow_info = self._resolve_workflow(workflow=workflow)
            
            # 2. Execute ComfyUI workflow
            return await self._call_comfyui_workflow(
                workflow_info=workflow_info,
                text=text,
                comfyui_url=comfyui_url,
                voice=voice,
                speed=speed,
                output_path=output_path,
                **params
            )
    
    async def _call_local_tts(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate speech using local Edge TTS
        
        Args:
            text: Text to convert to speech
            voice: Edge TTS voice ID (default: from config)
            speed: Speech speed multiplier (default: from config)
            output_path: Custom output path (auto-generated if None)
        
        Returns:
            Generated audio file path
        """
        # Get config defaults
        local_config = self.config.get("local", {})
        
        # Determine voice and speed (param > config)
        final_voice = voice or local_config.get("voice", "zh-CN-YunjianNeural")
        final_speed = speed if speed is not None else local_config.get("speed", 1.2)
        
        # Convert speed to rate parameter
        rate = speed_to_rate(final_speed)
        
        logger.info(f"🎙️  Using local Edge TTS: voice={final_voice}, speed={final_speed}x (rate={rate})")
        
        # Generate output path if not provided
        if not output_path:
            # Generate unique filename
            unique_id = uuid.uuid4().hex
            output_path = f"output/{unique_id}.mp3"
            
            # Ensure output directory exists
            Path("output").mkdir(parents=True, exist_ok=True)
        
        # Call Edge TTS
        try:
            audio_bytes = await edge_tts(
                text=text,
                voice=final_voice,
                rate=rate,
                output_path=output_path
            )
            
            logger.info(f"✅ Generated audio (local Edge TTS): {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"Local TTS generation error: {e}")
            raise

    async def _call_omnivoice_tts(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        output_path: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        instruct: Optional[str] = None,
        base_url: Optional[str] = None,
        response_format: str = "mp3",
        **params,
    ) -> str:
        """Generate speech using the local OmniVoice OpenAI-compatible API."""
        omni_config = self.config.get("omnivoice", {})
        final_base_url = (base_url or omni_config.get("base_url") or "http://127.0.0.1:3900").rstrip("/")
        final_model = model or omni_config.get("model", "omnivoice")
        final_voice = voice or omni_config.get("voice", "default")
        final_speed = speed if speed is not None else omni_config.get("speed", 1.0)
        final_language = language if language is not None else omni_config.get("language")
        final_instruct = normalize_omnivoice_instruct(
            instruct if instruct is not None else omni_config.get("instruct")
        )

        response_format = self._infer_omnivoice_response_format(output_path, response_format)

        if not output_path:
            unique_id = uuid.uuid4().hex
            output_path = f"output/{unique_id}.{response_format}"
            Path("output").mkdir(parents=True, exist_ok=True)
        else:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"🎙️  Using local OmniVoice TTS: {final_base_url}, "
            f"voice={final_voice}, speed={final_speed}x, instruct={final_instruct!r}"
        )
        model_status = None
        read_timeout = self.OMNIVOICE_TIMEOUT_READY_SECONDS
        try:
            model_status = fetch_omnivoice_model_status(final_base_url, timeout=4.0)
            if model_status.get("status") in {"idle", "loading"} or model_status.get("loading"):
                read_timeout = self.OMNIVOICE_TIMEOUT_COLD_START_SECONDS
            if self._is_omnivoice_stuck_status(model_status):
                raise RuntimeError(
                    "OmniVoice 后端状态异常：模型显示 `Model ready`，但仍停留在 loading。"
                    "请先重启 OmniVoice Studio，再重试。"
                )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            logger.warning(f"Failed to read OmniVoice model status before TTS: {exc}")

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                generated = await asyncio.to_thread(
                    generate_omnivoice_openai_speech,
                    final_base_url,
                    text=text,
                    model=final_model,
                    voice=final_voice,
                    response_format=response_format,
                    language=final_language,
                    instruct=final_instruct,
                    speed=final_speed,
                    seed=params.get("seed"),
                    duration=params.get("duration"),
                    timeout=read_timeout,
                )
                Path(output_path).write_bytes(generated["audio_bytes"])
                break
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                # Client errors (4xx) are not transient: bad instruct/voice won't
                # fix itself, so surface them immediately.
                is_client_error = (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code < 500
                )
                if is_client_error or attempt == max_attempts:
                    try:
                        model_status = fetch_omnivoice_model_status(final_base_url, timeout=4.0)
                    except Exception as status_exc:
                        logger.warning(f"Failed to refresh OmniVoice model status after TTS error: {status_exc}")
                    logger.error(f"OmniVoice TTS failed (attempt {attempt}/{max_attempts}): {exc}")
                    raise RuntimeError(
                        format_omnivoice_error(
                            exc,
                            model_status=model_status,
                            timeout_seconds=read_timeout,
                        )
                    ) from exc
                wait_seconds = 2 ** (attempt - 1)
                logger.warning(
                    f"OmniVoice TTS transient error (attempt {attempt}/{max_attempts}): {exc}, "
                    f"retrying in {wait_seconds}s"
                )
                await asyncio.sleep(wait_seconds)

        logger.info(f"✅ Generated audio (OmniVoice): {output_path}")
        return output_path
    
    async def _call_comfyui_workflow(
        self,
        workflow_info: dict,
        text: str,
        comfyui_url: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_path: Optional[str] = None,
        **params
    ) -> str:
        """
        Generate speech using ComfyUI workflow
        
        Args:
            workflow_info: Workflow info dict from _resolve_workflow()
            text: Text to convert to speech
            comfyui_url: ComfyUI URL
            voice: Voice ID (workflow-specific)
            speed: Speech speed multiplier (workflow-specific)
            output_path: Custom output path (downloads if URL returned)
            **params: Additional workflow parameters
        
        Returns:
            Generated audio file path (local if output_path provided, otherwise URL)
        """
        logger.info(f"🎙️  Using workflow: {workflow_info['key']}")
        
        # 1. Build workflow parameters (ComfyKit config is now managed by core)
        workflow_params = {"text": text}
        
        # Add optional TTS parameters (only if explicitly provided and not None)
        if voice is not None:
            workflow_params["voice"] = voice
        if speed is not None and speed != 1.0:
            workflow_params["speed"] = speed
        
        # Add any additional parameters
        workflow_params.update(params)
        
        logger.debug(f"Workflow parameters: {workflow_params}")
        
        # 3. Execute workflow using shared ComfyKit instance from core
        try:
            # Get shared ComfyKit instance (lazy initialization + config hot-reload)
            kit = await self.core._get_or_create_comfykit()
            
            workflow_input = workflow_info["path"]
            logger.info(f"Executing selfhost TTS workflow: {workflow_input}")
            
            result = await kit.execute(workflow_input, workflow_params)
            
            # 4. Handle result
            if result.status != "completed":
                error_msg = result.msg or "Unknown error"
                logger.error(f"TTS generation failed: {error_msg}")
                raise Exception(f"TTS generation failed: {error_msg}")
            
            # ComfyKit result can have audio files in different output types
            # Try to get audio file path from result
            audio_path = None
            
            # Check for audio files in result.audios (if available)
            if hasattr(result, 'audios') and result.audios:
                audio_path = result.audios[0]
                logger.debug(f"✅ Found audio in result.audios: {audio_path}")
            # Check for files in result.files
            elif hasattr(result, 'files') and result.files:
                audio_path = result.files[0]
                logger.debug(f"✅ Found audio in result.files: {audio_path}")
            # Check in outputs dictionary
            elif hasattr(result, 'outputs') and result.outputs:
                logger.debug(f"Searching for audio file in result.outputs: {result.outputs}")
                # Try to find audio file in outputs
                for key, value in result.outputs.items():
                    if isinstance(value, str) and any(value.endswith(ext) for ext in ['.mp3', '.wav', '.flac']):
                        audio_path = value
                        logger.debug(f"✅ Found audio in result.outputs[{key}]: {audio_path}")
                        break
            
            if not audio_path:
                logger.error("No audio file generated")
                logger.error(f"❌ Result analysis:")
                logger.error(f"   - result.audios: {getattr(result, 'audios', 'NOT_FOUND')}")
                logger.error(f"   - result.files: {getattr(result, 'files', 'NOT_FOUND')}")
                logger.error(f"   - result.outputs: {getattr(result, 'outputs', 'NOT_FOUND')}")
                logger.error(f"   - Full __dict__: {result.__dict__}")
                raise Exception("No audio file generated by workflow")
            
            # If output_path provided and audio_path is URL, download to local
            if output_path and audio_path.startswith(('http://', 'https://')):
                import httpx
                import os
                
                # Ensure parent directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                logger.info(f"Downloading audio from {audio_path} to {output_path}")
                download_timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0)
                async with httpx.AsyncClient(timeout=download_timeout) as client:
                    response = await client.get(audio_path)
                    response.raise_for_status()
                    
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                
                logger.info(f"✅ Generated audio (ComfyUI): {output_path}")
                return output_path
            
            logger.info(f"✅ Generated audio (ComfyUI): {audio_path}")
            return audio_path
        
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            raise
