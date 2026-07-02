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
Media Generation Service - ComfyUI Workflow-based implementation

Supports both image and video generation workflows.
Automatically detects output type based on ExecuteResult.
"""

import json
import random
import re
from pathlib import Path
from typing import Optional

from comfykit import ComfyKit
from loguru import logger

from morpheus_video_studio.services.comfy_base_service import ComfyBaseService
from morpheus_video_studio.models.media import MediaResult
from morpheus_video_studio.config import config_manager
from morpheus_video_studio.services.stock_publish_tools import download_material, search_stock_materials
from morpheus_video_studio.utils.comfyui_util import check_comfyui_health


DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, low quality, blurry, bad face, asymmetrical face, cross-eye, "
    "deformed eyes, deformed pupils, bad anatomy, deformed body, extra limbs, "
    "missing limbs, fused limbs, bad hands, malformed hands, extra fingers, "
    "missing fingers, fused fingers, long neck, disfigured, uncanny, text, "
    "watermark, logo, cropped head"
)

LOCAL_LIBRARY_MEDIA_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
LOCAL_LIBRARY_ROOT_CANDIDATES = (
    "media_library",
    "assets/media_library",
    "library/media_library",
    "assets/ip_library",
)


class MediaService(ComfyBaseService):
    """
    Media generation service - Workflow-based
    
    Uses ComfyKit to execute image/video generation workflows.
    Supports both image_ and video_ workflow prefixes.
    
    Usage:
        # Use default workflow (workflows/image_flux.json)
        media = await morpheus_video_studio.media(prompt="a cat")
        if media.is_image:
            print(f"Generated image: {media.url}")
        elif media.is_video:
            print(f"Generated video: {media.url} ({media.duration}s)")
        
        # Use specific workflow
        media = await morpheus_video_studio.media(
            prompt="a cat",
            workflow="image_flux.json"
        )
        
        # List available workflows
        workflows = morpheus_video_studio.media.list_workflows()
    """
    
    WORKFLOW_PREFIX = ""  # Will be overridden by _scan_workflows
    DEFAULT_WORKFLOW = None  # No hardcoded default, must be configured
    WORKFLOWS_DIR = "workflows"
    
    def __init__(self, config: dict, core=None):
        """
        Initialize media service
        
        Args:
            config: Full application config dict
            core: MorpheusVideoStudioCore instance (for accessing shared ComfyKit)
        """
        super().__init__(config, service_name="image", core=core)  # Keep "image" for config compatibility
    
    def _scan_workflows(self):
        """
        Scan workflows for both image_ and video_ prefixes
        
        Override parent method to support multiple prefixes
        """
        from morpheus_video_studio.utils.os_util import list_resource_dirs, list_resource_files, get_resource_path
        from pathlib import Path
        
        workflows = []
        
        # Get all workflow source directories
        source_dirs = list_resource_dirs("workflows")
        
        if not source_dirs:
            logger.warning("No workflow source directories found")
            return workflows
        
        # Scan each source directory for workflow files
        for source_name in source_dirs:
            # Get all JSON files for this source
            workflow_files = list_resource_files("workflows", source_name)
            
            # Filter to only files matching image_ or video_ prefix
            matching_files = [
                f for f in workflow_files 
                if (f.startswith("image_") or f.startswith("video_")) and f.endswith('.json')
            ]
            
            for filename in matching_files:
                try:
                    # Get actual file path
                    file_path = Path(get_resource_path("workflows", source_name, filename))
                    workflow_info = self._parse_workflow_file(file_path, source_name)
                    workflows.append(workflow_info)
                    logger.debug(f"Found workflow: {workflow_info['key']}")
                except Exception as e:
                    logger.error(f"Failed to parse workflow {source_name}/{filename}: {e}")
        
        # Sort by key (source/name)
        return sorted(workflows, key=lambda w: w["key"])
    
    async def __call__(
        self,
        prompt: str,
        workflow: Optional[str] = None,
        # Media type specification (required for proper handling)
        media_type: str = "image",  # "image" or "video"
        # ComfyUI connection (optional overrides)
        comfyui_url: Optional[str] = None,
        selfhost_api_key: Optional[str] = None,
        # Common workflow parameters
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[float] = None,  # Video duration in seconds (for video workflows)
        negative_prompt: Optional[str] = None,
        steps: Optional[int] = None,
        seed: Optional[int] = None,
        cfg: Optional[float] = None,
        sampler: Optional[str] = None,
        **params
    ) -> MediaResult:
        """
        Generate media (image or video) using workflow
        
        Media type must be specified explicitly via media_type parameter.
        Returns a MediaResult object containing media type and URL.
        
        Args:
            prompt: Media generation prompt
            workflow: Workflow filename (default: from config or "image_flux.json")
            media_type: Type of media to generate - "image" or "video" (default: "image")
            comfyui_url: ComfyUI URL (optional, overrides config)
            selfhost_api_key: Selfhost API key (optional, overrides config)
            width: Media width
            height: Media height
            duration: Target video duration in seconds (only for video workflows, typically from TTS audio duration)
            negative_prompt: Negative prompt
            steps: Sampling steps
            seed: Random seed
            cfg: CFG scale
            sampler: Sampler name
            **params: Additional workflow parameters
        
        Returns:
            MediaResult object with media_type ("image" or "video") and url
        
        Examples:
            # Simplest: use default workflow (workflows/image_flux.json)
            media = await morpheus_video_studio.media(prompt="a beautiful cat")
            if media.is_image:
                print(f"Image: {media.url}")
            
            # Use specific workflow
            media = await morpheus_video_studio.media(
                prompt="a cat",
                workflow="image_flux.json"
            )
            
            # Video workflow
            media = await morpheus_video_studio.media(
                prompt="a cat running",
                workflow="image_video.json"
            )
            if media.is_video:
                print(f"Video: {media.url}, duration: {media.duration}s")
            
            # With additional parameters
            media = await morpheus_video_studio.media(
                prompt="a cat",
                workflow="image_flux.json",
                width=1024,
                height=1024,
                steps=20,
                seed=42
            )
            
            # With absolute path
            media = await morpheus_video_studio.media(
                prompt="a cat",
                workflow="/path/to/custom.json"
            )
            
            # With custom ComfyUI server
            media = await morpheus_video_studio.media(
                prompt="a cat",
                comfyui_url="http://192.168.1.100:8188"
            )
        """
        if workflow and workflow.startswith("hyperframe/"):
            if media_type != "video":
                raise ValueError("HyperFrame media generation only supports video templates.")
            try:
                return await self.core.hyperframe.render_media(
                    prompt=prompt,
                    width=width,
                    height=height,
                    duration=duration,
                    **params,
                )
            except Exception as exc:
                logger.warning(f"HyperFrame media generation failed; falling back to stock materials: {exc}")
                return await self._generate_from_stock_materials(
                    prompt=prompt,
                    provider="all",
                    width=width,
                    height=height,
                    selection_mode=params.get("stock_selection_mode", "sequential"),
                )

        if workflow and workflow.startswith("stock/"):
            provider = workflow.split("/", 1)[1] or "all"
            try:
                return await self._generate_from_stock_materials(
                    prompt=prompt,
                    provider="all" if provider in ("turbo", "comfy") else provider,
                    width=width,
                    height=height,
                    selection_mode=params.get("stock_selection_mode", "sequential"),
                )
            except Exception:
                if provider != "comfy":
                    raise
                logger.warning("Stock materials failed; trying ComfyUI as assist fallback")
                fallback_workflow = self._default_selfhost_workflow(media_type)
                if not fallback_workflow:
                    raise
                workflow = fallback_workflow

        # 1. Resolve workflow (returns structured info)
        workflow_info = self._resolve_workflow(workflow=workflow)
        
        # 2. Build workflow parameters (ComfyKit config is now managed by core)
        workflow_params = {"prompt": prompt}
        
        # Add optional parameters
        if width is not None:
            workflow_params["width"] = width
        if height is not None:
            workflow_params["height"] = height
        if duration is not None:
            workflow_params["duration"] = duration
            if media_type == "video":
                logger.info(f"📏 Target video duration: {duration:.2f}s (from TTS audio)")
        workflow_params["negative_prompt"] = negative_prompt or DEFAULT_NEGATIVE_PROMPT
        if steps is not None:
            workflow_params["steps"] = steps
        if seed is not None:
            workflow_params["seed"] = seed
        if cfg is not None:
            workflow_params["cfg"] = cfg
        if sampler is not None:
            workflow_params["sampler"] = sampler
        
        # Add any additional parameters
        workflow_params.update(params)
        
        logger.debug(f"Workflow parameters: {workflow_params}")
        
        # 4. Execute workflow using shared ComfyKit instance from core
        try:
            if workflow_info["source"] == "selfhost":
                comfy_config = self.core.config.get("comfyui", {}) if self.core else {}
                health_url = comfyui_url or comfy_config.get("comfyui_url", "http://127.0.0.1:8188")
                comfy_ok, comfy_msg = check_comfyui_health(health_url, timeout=2.0)
                if not comfy_ok:
                    logger.warning(f"{comfy_msg}; falling back to stock materials")
                    return await self._generate_from_stock_materials(
                        prompt=prompt,
                        provider="all",
                        width=width,
                        height=height,
                    )

            # Get shared ComfyKit instance (lazy initialization + config hot-reload)
            kit = await self.core._get_or_create_comfykit()
            
            # Determine what to pass to ComfyKit based on source
            if workflow_info["source"] == "selfhost" and "workflow_id" in workflow_info:
                # Selfhost: pass workflow_id (ComfyKit will use selfhost backend)
                workflow_input = workflow_info["workflow_id"]
                logger.info(f"Executing Selfhost workflow: {workflow_input}")
            else:
                # Selfhost: pass file path (ComfyKit will use local ComfyUI)
                workflow_input = workflow_info["path"]
                logger.info(f"Executing selfhost workflow: {workflow_input}")
            
            result = await kit.execute(workflow_input, workflow_params)
            
            # 5. Handle result based on specified media_type
            if result.status != "completed":
                error_msg = result.msg or "Unknown error"
                logger.error(f"Media generation failed: {error_msg}")
                raise Exception(f"Media generation failed: {error_msg}")
            
            # Extract media based on specified type
            if media_type == "video":
                # Video workflow - get video from result
                if not result.videos:
                    logger.error("No video generated (workflow returned no videos)")
                    raise Exception("No video generated")
                
                video_url = result.videos[0]
                logger.info(f"✅ Generated video: {video_url}")
                
                # Try to extract duration from result (if available)
                duration = None
                if hasattr(result, 'duration') and result.duration:
                    duration = result.duration
                
                return MediaResult(
                    media_type="video",
                    url=video_url,
                    duration=duration
                )
            else:  # image
                # Image workflow - get image from result
                if not result.images:
                    logger.error("No image generated (workflow returned no images)")
                    raise Exception("No image generated")
                
                image_url = result.images[0]
                logger.info(f"✅ Generated image: {image_url}")
                
                return MediaResult(
                    media_type="image",
                    url=image_url
                )
        
        except Exception as e:
            logger.error(f"Media generation error: {e}")
            if workflow_info["source"] == "selfhost":
                logger.warning("Falling back to stock materials after ComfyUI media generation error")
                return await self._generate_from_stock_materials(
                    prompt=prompt,
                    provider="all",
                    width=width,
                    height=height,
                )
            raise

    async def _generate_from_stock_materials(
        self,
        prompt: str,
        provider: str = "all",
        width: Optional[int] = None,
        height: Optional[int] = None,
        selection_mode: str = "sequential",
    ) -> MediaResult:
        config_manager.reload()
        stock_config = config_manager.get_stock_materials_config()
        configured_providers = [
            name for name in ("pexels", "pixabay")
            if stock_config.get(f"{name}_api_key", "").strip()
        ]
        if provider == "all":
            providers = configured_providers
        else:
            providers = [provider] if provider in configured_providers else []

        if not providers:
            raise RuntimeError("ComfyUI 不可用，且未配置 Pexels/Pixabay API Key，无法使用素材兜底。")

        local_media = self._find_local_library_media(prompt, selection_mode=selection_mode)
        if local_media:
            logger.info(f"Using local library media: {local_media}")
            return MediaResult(media_type="video", url=str(local_media), duration=None)

        orientation = "portrait"
        if width and height:
            if width > height:
                orientation = "landscape"
            elif width == height:
                orientation = "square"

        cleaned_prompt = self._strip_stock_prompt_prefix(prompt)
        queries = await self._build_stock_query_plan(cleaned_prompt)
        logger.info(f"Stock query plan: {queries}")

        candidates = []
        for query in queries:
            logger.info(f"Searching stock materials ({', '.join(providers)}) for: {query}")
            for provider_name in providers:
                api_key = stock_config.get(f"{provider_name}_api_key", "").strip()
                try:
                    candidates.extend(
                        await search_stock_materials(provider_name, api_key, query, orientation, per_page=8)
                    )
                except Exception as exc:
                    logger.warning(f"Stock material search failed for {provider_name}: {exc}")
            if candidates:
                break

        if not candidates:
            raise RuntimeError("ComfyUI 不可用，且 Pexels/Pixabay 没有返回可用素材。")

        if selection_mode == "random":
            random.shuffle(candidates)

        last_download_error = None
        for material in candidates:
            try:
                local_path = await download_material(material.url, material.provider)
                logger.info(f"Using stock material fallback: {local_path}")
                return MediaResult(media_type="video", url=str(local_path), duration=material.duration or None)
            except Exception as exc:
                last_download_error = exc
                logger.warning(f"Stock material download failed for {material.provider}: {exc}")

        raise RuntimeError(f"Pexels/Pixabay 返回了素材，但下载均失败：{last_download_error}")

    def _find_local_library_media(self, prompt: str, selection_mode: str = "sequential") -> Optional[Path]:
        """
        Search local licensed media libraries before public stock providers.

        This is the path for title-specific footage such as TV dramas or movies.
        Public stock APIs will not reliably return copyrighted works like 水浒传,
        so we let users keep licensed/local clips in a conventional library and
        match by title aliases.
        """
        normalized_prompt = self._normalize_lookup_text(prompt)
        if not normalized_prompt:
            return None

        best_folder: Optional[Path] = None
        best_score = 0
        best_alias = ""

        for root in self._iter_local_library_roots():
            for folder in root.iterdir():
                if not folder.is_dir():
                    continue
                score, alias = self._score_library_folder(folder, normalized_prompt)
                if score > best_score:
                    best_folder = folder
                    best_score = score
                    best_alias = alias

        if not best_folder:
            return None

        media_files = sorted(
            item for item in best_folder.rglob("*")
            if item.is_file() and item.suffix.lower() in LOCAL_LIBRARY_MEDIA_EXTENSIONS
        )
        if not media_files:
            logger.warning(f"Matched local library folder but found no media files: {best_folder}")
            return None

        if selection_mode == "random":
            return random.choice(media_files)

        logger.info(
            f"Matched local media library folder '{best_folder.name}' via alias '{best_alias}' "
            f"({len(media_files)} files)"
        )
        return media_files[0]

    def _iter_local_library_roots(self) -> list[Path]:
        cwd = Path.cwd()
        roots: list[Path] = []
        seen: set[str] = set()
        for relative in LOCAL_LIBRARY_ROOT_CANDIDATES:
            path = (cwd / relative).resolve()
            if path.is_dir() and str(path) not in seen:
                roots.append(path)
                seen.add(str(path))
        return roots

    def _score_library_folder(self, folder: Path, normalized_prompt: str) -> tuple[int, str]:
        aliases = self._load_library_aliases(folder)
        best_score = 0
        best_alias = ""
        for alias in aliases:
            normalized_alias = self._normalize_lookup_text(alias)
            if not normalized_alias:
                continue
            if normalized_alias in normalized_prompt:
                score = len(normalized_alias)
                if score > best_score:
                    best_score = score
                    best_alias = alias
        return best_score, best_alias

    def _load_library_aliases(self, folder: Path) -> list[str]:
        aliases = {folder.name}

        # Support folder names like "水浒传__水浒__all-men-are-brothers"
        aliases.update(part.strip() for part in folder.name.split("__") if part.strip())
        aliases.update(part.strip() for part in folder.name.split(",") if part.strip())

        aliases_file = folder / "aliases.txt"
        if aliases_file.is_file():
            try:
                aliases.update(
                    line.strip()
                    for line in aliases_file.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            except Exception as exc:
                logger.warning(f"Failed to read aliases.txt from {folder}: {exc}")

        manifest_file = folder / "manifest.json"
        if manifest_file.is_file():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                if isinstance(manifest, dict):
                    title = str(manifest.get("title", "")).strip()
                    if title:
                        aliases.add(title)
                    for item in manifest.get("aliases", []) or []:
                        value = str(item).strip()
                        if value:
                            aliases.add(value)
            except Exception as exc:
                logger.warning(f"Failed to read manifest.json from {folder}: {exc}")

        return sorted(aliases)

    def _normalize_lookup_text(self, value: str) -> str:
        value = str(value or "").lower()
        value = re.sub(r"[\s\-_]+", "", value)
        value = re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", value)
        return value

    def _strip_stock_prompt_prefix(self, prompt: str) -> str:
        """
        Remove style-oriented prompt prefixes before searching stock footage.

        Stock providers need semantic search terms, not visual-style boilerplate.
        """
        cleaned = (prompt or "").strip()
        if not cleaned:
            return ""

        comfy_config = self.core.config.get("comfyui", {}) if self.core else {}
        prefixes = [
            comfy_config.get("image", {}).get("prompt_prefix", ""),
            comfy_config.get("video", {}).get("prompt_prefix", ""),
        ]
        for prefix in prefixes:
            prefix = (prefix or "").strip().rstrip(",")
            if not prefix:
                continue
            prefixed = f"{prefix}, "
            if cleaned.startswith(prefixed):
                return cleaned[len(prefixed):].strip()
            if cleaned == prefix:
                return ""
        return cleaned

    async def _build_stock_query_plan(self, prompt: str) -> list[str]:
        """
        Build an ordered set of stock-footage queries.

        We prefer semantic fallbacks over generic wallpaper-like queries so that
        missed exact matches still stay close to the script's visual language.
        """
        cleaned = re.sub(r"\s+", " ", (prompt or "").strip())
        if not cleaned:
            return ["background video"]

        queries: list[str] = []

        def add_query(value: str):
            normalized = re.sub(r"[^A-Za-z0-9\s-]", " ", str(value or ""))
            normalized = re.sub(r"\s+", " ", normalized).strip(" -")
            if not normalized:
                return
            lowered = normalized.lower()
            if lowered not in {item.lower() for item in queries}:
                queries.append(normalized)

        ascii_candidate = " ".join(cleaned.split()[:12]).strip(" ,.;:-")
        if ascii_candidate and len(ascii_candidate) <= 120 and any(
            ch.isascii() and ch.isalpha() for ch in ascii_candidate
        ):
            add_query(ascii_candidate)

        for query in await self._build_stock_queries_via_llm(cleaned):
            add_query(query)

        for query in self._build_stock_heuristic_queries(cleaned):
            add_query(query)

        return queries or ["background video"]

    async def _build_stock_queries_via_llm(self, prompt: str) -> list[str]:
        """Ask the configured LLM for a few stock-footage queries with semantic fallbacks."""
        cleaned = re.sub(r"\s+", " ", (prompt or "").strip())
        if not cleaned:
            return []

        llm = getattr(self.core, "llm", None) if self.core else None
        llm_config = self.core.config.get("llm", {}) if self.core else {}
        if not (llm and llm_config.get("api_key") and llm_config.get("model")):
            return []

        try:
            response = await llm(
                (
                    "You are preparing search queries for stock-footage websites like Pexels and Pixabay.\n"
                    "Given one video idea, return JSON with 3 short English search queries ordered from best to fallback.\n"
                    "Rules:\n"
                    "1. Query 1 = exact subject if filmable.\n"
                    "2. Query 2 = realistic scene or activity that conveys the same meaning.\n"
                    "3. Query 3 = visual substitute or metaphor that still matches the narration.\n"
                    "4. Each query must be 2 to 6 words.\n"
                    "5. Avoid generic filler like cinematic background, city night, abstract background.\n"
                    "6. Prefer filmable real-world footage over named fictional IP when the exact subject is unlikely to exist.\n\n"
                    f'Idea: {cleaned}\n\n'
                    'Return only JSON like {"queries":["query 1","query 2","query 3"]}.'
                ),
                temperature=0.2,
                max_tokens=120,
            )
            raw = str(response or "").strip()
            json_match = re.search(r"\{[\s\S]*\}", raw)
            payload = json.loads(json_match.group(0) if json_match else raw)
            queries = payload.get("queries", []) if isinstance(payload, dict) else []
            if isinstance(queries, list):
                return [str(item) for item in queries if str(item).strip()]
        except Exception as exc:
            logger.warning(f"Failed to derive stock query plan via LLM: {exc}")

        return []

    def _build_stock_heuristic_queries(self, prompt: str) -> list[str]:
        """Fallback semantic queries when LLM planning is unavailable or sparse."""
        lowered = (prompt or "").lower()
        queries: list[str] = []

        if any(token in prompt for token in ("国漫", "动漫", "动画", "番剧")) or any(
            token in lowered for token in ("anime", "animation", "cartoon")
        ):
            queries.extend([
                "animation studio artist",
                "anime fans watching screen",
                "comic convention crowd",
            ])

        if any(token in prompt for token in ("排名", "倒数", "最佳", "盘点", "前十", "top")) or any(
            token in lowered for token in ("ranking", "countdown", "best", "top 10", "review")
        ):
            queries.extend([
                "audience reaction watching screen",
                "people discussing favorites",
                "dramatic reveal closeup",
            ])

        if any(token in prompt for token in ("热血", "战斗", "英雄", "冒险")) or any(
            token in lowered for token in ("battle", "hero", "adventure", "warrior")
        ):
            queries.extend([
                "hero silhouette dramatic",
                "team running cinematic",
                "fantasy warrior action",
            ])

        if not queries:
            compact = re.sub(r"[^\w\s]", " ", prompt).strip()
            compact = " ".join(compact.split()[:6])
            if compact:
                queries.append(compact)

        return queries

    def _default_selfhost_workflow(self, media_type: str) -> Optional[str]:
        comfy_config = self.core.config.get("comfyui", {}) if self.core else {}
        media_config_key = "video" if media_type == "video" else "image"
        workflow = comfy_config.get(media_config_key, {}).get("default_workflow")
        if not workflow:
            workflow = (
                "selfhost/video_dreamshaper_m4.json"
                if media_type == "video"
                else "selfhost/image_dreamshaper_m4.json"
            )
        if not str(workflow).startswith("selfhost/"):
            workflow = f"selfhost/{workflow}"

        comfy_url = comfy_config.get("comfyui_url", "http://127.0.0.1:8188")
        comfy_ok, comfy_msg = check_comfyui_health(comfy_url, timeout=2.0)
        if not comfy_ok:
            logger.warning(f"{comfy_msg}; ComfyUI assist fallback skipped")
            return None
        return workflow
