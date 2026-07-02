import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from loguru import logger
import httpx
import ffmpeg
from web.i18n import tr, get_language
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.components.digital_tts_config import render_style_config
from web.utils.async_helpers import run_async
from web.utils.streamlit_helpers import check_and_warn_selfhost_workflow
from morpheus_video_studio.config import config_manager
from morpheus_video_studio.services.light_avatar_video import LightAvatarVideoService
from morpheus_video_studio.services.studio_library import StudioLibraryService
from morpheus_video_studio.models.storyboard import Storyboard, StoryboardConfig, StoryboardFrame
from morpheus_video_studio.utils.os_util import create_task_output_dir, get_resource_path

class DigitalHumanPipelineUI(PipelineUI):
    """
    UI for the Digital_Human Video Generation Pipeline.
    Generates videos from user-provided assets (images&videos&audio).
    """
    name = "digital_human"
    icon = "🤖"
    PIXELLE_VIDEO_URL = "http://127.0.0.1:8503"
    
    @property
    def display_name(self):
        return tr("pipeline.digital_human.name")
    
    @property
    def description(self):
        return "用一张人物立绘和一段配音，生成本地轻二维口播视频。"

    def render(self, morpheus_video_studio: Any):
        # Three-column layout
        left_col, middle_col, right_col = st.columns([1, 1, 1])
        
        # ====================================================================
        # Left Column: Asset Upload
        # ====================================================================
        with left_col:
            asset_params = self.render_digital_human_input()
            style_params = render_style_config(morpheus_video_studio)
            # bgm_params = render_bgm_section(key_prefix="asset_")
        
        # ====================================================================
        # Middle Column: Video Configuration
        # ====================================================================
        with middle_col:
            generation_params = self.render_generation_engine()
            workflow_path = self.workflow_path_config() if generation_params["generation_engine"] == "pixelle_legacy" else {}
            if generation_params["generation_engine"] == "local_avatar":
                mode_params = self.render_light_avatar_mode()
            else:
                mode_params = self.render_digital_human_mode(asset_params["character_assets"])
        
        # ====================================================================
        # Right Column: Output Preview
        # ====================================================================
        with right_col:
            # Combine all parameters
            video_params = {
                **mode_params,
                **asset_params,
                **style_params,
                **generation_params,
                "workflow_path": workflow_path
            }
            
            self._render_output_preview(morpheus_video_studio, video_params)

    def render_digital_human_input(self) -> dict:
        """Render digital human character image upload section"""
        with st.container(border=True):
            st.markdown(f"**{tr('digital_human.section.character_assets')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("digital_human.assets.character_what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("digital_human.assets.how"))
            
            # File uploader for multiple files
            uploaded_files = st.file_uploader(
                tr("digital_human.assets.upload"),
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                help=tr("digital_human.assets.upload_help"),
                key="character_files"
            )
            
            # Save uploaded files to temp directory with unique session ID
            character_asset_paths = []
            if uploaded_files:
                import uuid
                session_id = str(uuid.uuid4()).replace('-', '')[:12]
                temp_dir = Path(f"temp/assets_{session_id}")
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                for uploaded_file in uploaded_files:
                    file_path = temp_dir / uploaded_file.name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    character_asset_paths.append(str(file_path.absolute()))
                
                st.success(tr("digital_human.assets.character_sucess"))
                
                # Preview uploaded assets
                with st.expander(tr("digital_human.assets.preview"), expanded=True):
                    # Show in a grid (3 columns)
                    cols = st.columns(3)
                    for i, (file, path) in enumerate(zip(uploaded_files, character_asset_paths)):
                        with cols[i % 3]:
                            # Check if image
                            ext = Path(path).suffix.lower()
                            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                                st.image(file, caption=file.name, use_container_width=True)
            else:
                st.info(tr("digital_human.assets.character_empty_hint"))

            return {"character_assets": character_asset_paths}

    def render_generation_engine(self) -> dict:
        with st.container(border=True):
            st.markdown("**🎭 演出方式**")
            st.caption("当前模块已收敛为本地轻二维口播：人物立绘 + 配音 + 镜头运动 + 简单张嘴。")
            return {"generation_engine": "local_avatar"}

    def _resolve_workflow_resource(self, filename: str) -> str | None:
        try:
            return get_resource_path("workflows", "selfhost", filename)
        except FileNotFoundError:
            return None

    def _get_digital_human_workflows(self) -> tuple[dict[str, str], list[str]]:
        workflow_files = {
            "first_workflow_path": "digital_image.json",
            "second_workflow_path": "digital_combination.json",
            "third_workflow_path": "digital_customize.json",
        }
        workflow_config: dict[str, str] = {}
        missing_files: list[str] = []

        for config_key, filename in workflow_files.items():
            resolved_path = self._resolve_workflow_resource(filename)
            if resolved_path:
                workflow_config[config_key] = resolved_path
            else:
                missing_files.append(filename)

        return workflow_config, missing_files

    def _find_pixelle_video_dir(self) -> Path | None:
        candidates = [
            Path.home() / "Pixelle-Video",
            Path.home() / "projects" / "morpheus-video-studio" / "pixelle_video",
            Path.home() / "Applications" / "morpheus-video-studio" / "pixelle_video",
        ]
        for candidate in candidates:
            if (candidate / "web" / "app.py").exists():
                return candidate
        return None

    def _launch_pixelle_video(self, pixelle_dir: Path) -> str:
        health_url = f"{self.PIXELLE_VIDEO_URL}/_stcore/health"
        try:
            response = httpx.get(health_url, timeout=2.0, trust_env=False)
            if response.status_code == 200:
                return f"Pixelle-Video 已经在运行：{self.PIXELLE_VIDEO_URL}"
        except Exception:
            pass

        log_dir = Path("output/service_logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"pixelle_video_{time.strftime('%Y%m%d_%H%M%S')}.log"
        command = "uv run streamlit run web/app.py --server.address 127.0.0.1 --server.port 8503"

        with open(log_path, "ab") as log_file:
            subprocess.Popen(
                ["/bin/zsh", "-lc", command],
                cwd=str(pixelle_dir),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

        return f"已发送 Pixelle-Video 启动命令。日志：{log_path.resolve()}"

    async def _persist_digital_human_history(
        self,
        morpheus_video_studio: Any,
        *,
        task_id: str,
        final_video_path: str,
        input_params: dict[str, Any],
        narration_text: str,
        character_image: str,
        audio_path: str,
        duration_seconds: float,
    ) -> None:
        if not getattr(morpheus_video_studio, "persistence", None):
            logger.warning("Persistence service unavailable, skipping Digital Human history save")
            return

        storyboard = Storyboard(
            title=input_params.get("goods_title") or input_params.get("title") or "数字人口播",
            config=StoryboardConfig(
                media_width=1080,
                media_height=1920,
                task_id=task_id,
                n_storyboard=1,
                tts_inference_mode=input_params.get("tts_inference_mode", "local"),
                voice_id=input_params.get("tts_voice"),
                tts_speed=input_params.get("tts_speed"),
                tts_instruct=input_params.get("tts_instruct"),
            ),
            frames=[
                StoryboardFrame(
                    index=0,
                    narration=narration_text,
                    image_prompt="light_avatar",
                    audio_path=audio_path,
                    media_type="image",
                    image_path=character_image,
                    video_segment_path=final_video_path,
                    duration=duration_seconds,
                )
            ],
            final_video_path=final_video_path,
            total_duration=duration_seconds,
        )
        storyboard.completed_at = datetime.now()

        video_path_obj = Path(final_video_path)
        metadata = {
            "task_id": task_id,
            "created_at": storyboard.created_at.isoformat() if storyboard.created_at else None,
            "completed_at": storyboard.completed_at.isoformat() if storyboard.completed_at else None,
            "status": "completed",
            "input": {
                **input_params,
                "text": narration_text,
                "mode": input_params.get("mode", "light_avatar"),
                "title": storyboard.title,
                "n_scenes": 1,
                "tts_inference_mode": input_params.get("tts_inference_mode", "local"),
                "tts_voice": input_params.get("tts_voice"),
                "tts_speed": input_params.get("tts_speed"),
            },
            "result": {
                "video_path": final_video_path,
                "duration": duration_seconds,
                "file_size": video_path_obj.stat().st_size if video_path_obj.exists() else 0,
                "n_frames": 1,
            },
            "config": {
                "generation_engine": input_params.get("generation_engine", "local_avatar"),
                "llm_model": morpheus_video_studio.config.get("llm", {}).get("model", "unknown"),
                "comfyui_url": morpheus_video_studio.config.get("comfyui", {}).get("comfyui_url", "unknown"),
            },
        }

        await morpheus_video_studio.persistence.save_task_metadata(task_id, metadata)
        await morpheus_video_studio.persistence.save_storyboard(task_id, storyboard)
        logger.info(f"💾 Saved Digital Human task to history: {task_id}")

    def workflow_path_config(self) -> dict:
        # Workflow source selection
        with st.container(border=True):
            st.markdown(f"**{tr('asset_based.section.source')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("asset_based.source.what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("asset_based.source.how"))
            
            source_options = {"selfhost": tr("asset_based.source.selfhost")}
            
            comfyui_config = config_manager.get_comfyui_config()
            has_selfhost = bool(comfyui_config.get("comfyui_url"))
            
            default_source_index = 0
            
            source = st.radio(
                tr("asset_based.source.select"),
                options=list(source_options.keys()),
                format_func=lambda x: source_options[x],
                index=default_source_index,
                horizontal=True,
                key="digital_human_workflow_source",
                label_visibility="collapsed"
            )
            
            workflow_config, missing_files = self._get_digital_human_workflows()
            if not has_selfhost:
                st.warning(tr("asset_based.source.selfhost_not_configured"))
            elif missing_files:
                st.warning(
                    "当前数字人口播并没有完整接入本地 selfhost 工作流。"
                    "这组 digital workflow 原本来自 Pixelle-Video / RunningHub。"
                )
            else:
                st.info(tr("asset_based.source.selfhost_hint"))
            return workflow_config

    def render_digital_human_mode(self, character_asset_paths: list) -> dict:
        self._apply_selected_content_defaults()
        with st.container(border=True):
            st.markdown(f"**{tr('digital_human.section.select_mode')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("digital_human.assets.mode_what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("digital_human.assets.select_how"))
            
            mode = st.radio(
                "Processing Mode",
                ["digital", "customize"],
                horizontal=True,
                format_func=lambda x: tr(f"mode.{x}"),
                label_visibility="collapsed",
                key="mode_selection"
                )
            
            # Text input (unified for both modes)
            text_placeholder = tr("digital_human.input.topic_placeholder") if mode == "digital" else tr("digital_human.input.content_placeholder")
            text_height = 120 if mode == "digital" else 200
            text_help = tr("input.text_help_digital") if mode == "digital" else tr("input.text_help_fixed")
            
            if mode == "digital":
                # File uploader for multiple files
                uploaded_files = st.file_uploader(
                    tr("digital_human.assets.upload"),
                    type=["jpg", "jpeg", "png", "webp"],
                    accept_multiple_files=True,
                    help=tr("digital_human.assets.upload_help"),
                    key="digital_files"
                )
                
                # Save uploaded files to temp directory with unique session ID
                goods_asset_paths = []
                if uploaded_files:
                    import uuid
                    session_id = str(uuid.uuid4()).replace('-', '')[:12]
                    temp_dir = Path(f"temp/assets_{session_id}")
                    temp_dir.mkdir(parents=True, exist_ok=True)
                
                    for uploaded_file in uploaded_files:
                        file_path = temp_dir / uploaded_file.name
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        goods_asset_paths.append(str(file_path.absolute()))
                
                    st.success(tr("digital_human.assets.goods_sucess"))
                
                    # Preview uploaded assets
                    with st.expander(tr("digital_human.assets.preview"), expanded=True):
                        # Show in a grid (3 columns)
                        cols = st.columns(3)
                        for i, (file, path) in enumerate(zip(uploaded_files, goods_asset_paths)):
                            with cols[i % 3]:
                                # Check if image
                                ext = Path(path).suffix.lower()
                                if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                                    st.image(file, caption=file.name, use_container_width=True)
                else:
                    st.info(tr("digital_human.assets.goods_empty_hint"))
                    # Text input
                goods_text = st.text_area(
                    tr("digital_human.input_text"),
                    placeholder=text_placeholder,
                    height=text_height,
                    help=text_help,
                    key="digital_box"
                    )

                goods_title = st.text_input(
                    tr("digital_human.goods_title"),
                    placeholder=tr("digital_human.goods_title_placeholder"),
                    help=tr("digital_human.goods_title_help"),
                    key="goods_title"
                )

                return {
                    "character_assets": character_asset_paths,
                    "goods_title": goods_title,
                    "goods_assets": goods_asset_paths,
                    "goods_text": goods_text,
                    "mode": mode
                    }

            else:
                goods_text = st.text_area(
                    tr("digital_human.customize_text"),
                    placeholder=text_placeholder,
                    height=text_height,
                    help=text_help,
                    key="customize_box"
                )

                return {
                    "character_assets": character_asset_paths,
                    "goods_text": goods_text,
                    "mode": mode
                    }

    def render_light_avatar_mode(self) -> dict:
        self._apply_selected_content_defaults()
        with st.container(border=True):
            st.markdown("**🪄 轻二维口播**")
            st.caption("本地直接合成一条角色口播视频，不依赖重型数字人口型工作流。")

            avatar_title = st.text_input(
                "视频标题（可选）",
                value=st.session_state.get("goods_title", ""),
                placeholder="例如：水浒人物解读 / 旅游路线讲解 / 生活格言",
                key="light_avatar_title",
            )
            avatar_script = st.text_area(
                "口播文案",
                value=st.session_state.get("avatar_script", st.session_state.get("customize_box", "")),
                placeholder="输入要播报的文案，或先从内容库带入。",
                height=220,
                key="light_avatar_script",
            )

            enable_mouth_animation = st.checkbox(
                "开启简单张嘴效果",
                value=True,
                key="light_avatar_enable_mouth",
                help="不是精准对口型，而是根据声音强弱做一个轻量开合效果。",
            )
            with st.expander("高级微调", expanded=False):
                st.caption("如果角色嘴巴位置不准，再调下面这四个参数。大多数情况下默认即可。")
                mouth_center_x = st.slider("嘴巴中心 X", 0.20, 0.80, 0.50, 0.01, key="light_avatar_mouth_x")
                mouth_center_y = st.slider("嘴巴中心 Y", 0.40, 0.92, 0.74, 0.01, key="light_avatar_mouth_y")
                mouth_width = st.slider("嘴巴宽度", 0.06, 0.35, 0.18, 0.01, key="light_avatar_mouth_w")
                mouth_height = st.slider("嘴巴高度", 0.03, 0.18, 0.08, 0.01, key="light_avatar_mouth_h")

            return {
                "mode": "light_avatar",
                "goods_title": avatar_title,
                "goods_text": avatar_script,
                "enable_mouth_animation": enable_mouth_animation,
                "mouth_center_x": mouth_center_x,
                "mouth_center_y": mouth_center_y,
                "mouth_width": mouth_width,
                "mouth_height": mouth_height,
            }

    def _apply_selected_content_defaults(self) -> None:
        content_id = st.session_state.get("studio_selected_content_id")
        if not content_id:
            return
        if st.session_state.get("studio_applied_content_to_digital_human") == content_id:
            return

        item = StudioLibraryService().get_content_item(content_id)
        if not item:
            return

        extracted_path = item.get("extracted_text_path")
        text = ""
        if extracted_path and Path(extracted_path).exists():
            text = Path(extracted_path).read_text(encoding="utf-8")

        st.session_state["customize_box"] = text
        st.session_state["digital_box"] = text
        st.session_state["avatar_script"] = text
        if not st.session_state.get("goods_title"):
            st.session_state["goods_title"] = item.get("title") or ""
        st.session_state["studio_applied_content_to_digital_human"] = content_id
                    
    def _render_output_preview(self, morpheus_video_studio: Any, video_params: dict):
        """Render output preview section"""
        with st.container(border=True):
            st.markdown(f"**{tr('section.video_generation')}**")
            
            # Check configuration
            if not config_manager.validate():
                st.warning(tr("settings.not_configured"))
            
            # Get input data
            character_assets = video_params.get("character_assets", [])
            goods_assets = video_params.get("goods_assets", [])
            goods_title = video_params.get("goods_title", "")
            goods_text = video_params.get("goods_text", "")
            mode = video_params.get("mode")
            generation_engine = video_params.get("generation_engine", "local_avatar")
            tts_voice = video_params.get("tts_voice", "zh-CN-YunjianNeural")
            tts_speed = video_params.get("tts_speed", 1.2)
            workflow_config = video_params.get("workflow_path", {})
            missing_workflows = [
                filename
                for config_key, filename in {
                    "first_workflow_path": "digital_image.json",
                    "second_workflow_path": "digital_combination.json",
                    "third_workflow_path": "digital_customize.json",
                }.items()
                if not workflow_config.get(config_key)
            ]
            
            logger.info(f"🔧 The obtained TTS parameters:")
            logger.info(f"  - tts_voice: {tts_voice}")
            logger.info(f"  - tts_speed: {tts_speed}")
            logger.info(f"  - video_params中的tts_voice: {video_params.get('tts_voice', 'NOT_FOUND')}")
            logger.info(f"  - video_params: {video_params}")
            
            # Validation
            if not character_assets:
                st.info(tr("digital_human.assets.character_warning"))
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_human_generate_disabled"
                )
                return

            if generation_engine == "pixelle_legacy" and mode == "digital" and not goods_assets:
                st.info(tr("digital_human.assets.goods_warning"))
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_human_goods_vaiidation"
                )
                return

            if generation_engine == "pixelle_legacy" and mode == "digital" and not (goods_text or goods_title):
                st.info(tr("digital_human.assets.digital_mode"))
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_human_digital_disable"
                )
                return
            
            if generation_engine == "pixelle_legacy" and mode == "digital" and (goods_text or goods_title):
                st.warning(tr("digital_human.assets.digital_mode_warning"))
            
            if generation_engine == "pixelle_legacy" and mode == "customize" and not goods_text:
                st.info(tr("digital_human.assets.customize_mode"))
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_human_customize_disable"
                )
                return

            if generation_engine == "local_avatar" and not goods_text.strip():
                st.info("请先输入一段口播文案，或先从内容库带入文本。")
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_human_light_avatar_script_missing",
                )
                return

            if generation_engine == "pixelle_legacy" and missing_workflows:
                st.error(
                    "当前页面无法直接执行这条数字人口播链路。"
                    "根因是本地 selfhost 版 digital workflow 缺失，而 Pixelle-Video 里这部分能力主要挂在 RunningHub 流程上。"
                )
                pixelle_dir = self._find_pixelle_video_dir()
                if pixelle_dir:
                    st.caption(f"已检测到本机 Pixelle-Video：`{pixelle_dir}`")
                    if st.button("启动 Pixelle-Video", key="launch_pixelle_video", use_container_width=True):
                        try:
                            st.success(self._launch_pixelle_video(pixelle_dir))
                        except Exception as exc:
                            st.error(f"启动 Pixelle-Video 失败：{exc}")
                    st.link_button("打开 Pixelle-Video", self.PIXELLE_VIDEO_URL, use_container_width=True)
                else:
                    st.caption("未检测到本机 Pixelle-Video 安装目录。")
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="digital_human_missing_workflows"
                )
                return
            
            # Generate button
            if st.button(tr("btn.generate"), type="primary", use_container_width=True, key="digital_human_generate"):
                # Validate
                if generation_engine == "pixelle_legacy" and not config_manager.validate():
                    st.error(tr("settings.not_configured"))
                    st.stop()
                
                # Show progress
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                start_time = time.time()
                
                try:
                    # Define async generation function
                    async def generate_digital_human_video():
                        task_dir, task_id = create_task_output_dir()
                        workflow_path = video_params["workflow_path"]

                        import json
                        from pathlib import Path

                        if generation_engine == "local_avatar":
                            status_text.text("步骤 1/2：生成配音")
                            progress_bar.progress(25)
                            audio_path = os.path.join(task_dir, "avatar_narration.wav")
                            tts_inference_mode = video_params.get("tts_inference_mode", "local")
                            tts_voice = video_params.get("tts_voice")
                            tts_speed = video_params.get("tts_speed")
                            tts_instruct = video_params.get("tts_instruct")
                            tts_workflow = video_params.get("tts_workflow")
                            ref_audio = video_params.get("ref_audio")

                            tts_kwargs = {
                                "text": goods_text,
                                "output_path": audio_path,
                                "inference_mode": tts_inference_mode,
                            }
                            if tts_inference_mode == "local":
                                tts_kwargs["voice"] = tts_voice
                                tts_kwargs["speed"] = tts_speed
                            elif tts_inference_mode == "omnivoice":
                                tts_kwargs["voice"] = tts_voice
                                tts_kwargs["speed"] = tts_speed
                                tts_kwargs["instruct"] = tts_instruct
                            elif tts_inference_mode == "comfyui":
                                if tts_workflow:
                                    tts_kwargs["workflow"] = tts_workflow
                                if ref_audio:
                                    tts_kwargs["ref_audio"] = ref_audio

                            audio_path = await morpheus_video_studio.tts(**tts_kwargs)
                            progress_bar.progress(60)
                            status_text.text("步骤 2/2：合成二维口播视频")
                            final_video_path = os.path.join(task_dir, "final.mp4")
                            LightAvatarVideoService().create_avatar_video(
                                character_image=character_assets[0],
                                audio_path=audio_path,
                                narration_text=goods_text,
                                output_path=final_video_path,
                                title=goods_title,
                                enable_mouth_animation=bool(video_params.get("enable_mouth_animation", True)),
                                mouth_center_x=float(video_params.get("mouth_center_x", 0.50)),
                                mouth_center_y=float(video_params.get("mouth_center_y", 0.74)),
                                mouth_width=float(video_params.get("mouth_width", 0.18)),
                                mouth_height=float(video_params.get("mouth_height", 0.08)),
                            )
                            duration_seconds = float(
                                ffmpeg.probe(final_video_path)["format"]["duration"]
                            )
                            await self._persist_digital_human_history(
                                morpheus_video_studio,
                                task_id=task_id,
                                final_video_path=final_video_path,
                                input_params=video_params,
                                narration_text=goods_text,
                                character_image=character_assets[0],
                                audio_path=audio_path,
                                duration_seconds=duration_seconds,
                            )
                            progress_bar.progress(100)
                            status_text.text(tr("status.success"))
                            return final_video_path

                        kit = await morpheus_video_studio._get_or_create_comfykit()

                        if mode == "customize":
                            status_text.text(tr("progress.step_audio"))
                            progress_bar.progress(25)
                            generated_image_path = character_assets[0]   
                            generated_text = goods_text                 

                            # TTS
                            audio_path = os.path.join(task_dir, "narration.mp3")
                            tts_inference_mode = video_params.get("tts_inference_mode", "local")
                            tts_voice = video_params.get("tts_voice")
                            tts_speed = video_params.get("tts_speed")
                            tts_instruct = video_params.get("tts_instruct")
                            tts_workflow = video_params.get("tts_workflow")
                            ref_audio = video_params.get("ref_audio")

                            tts_kwargs = {
                                "text": generated_text,
                                "output_path": audio_path,
                                "inference_mode": tts_inference_mode
                            }
                            if tts_inference_mode == "local":
                                tts_kwargs["voice"] = tts_voice
                                tts_kwargs["speed"] = tts_speed
                            elif tts_inference_mode == "omnivoice":
                                tts_kwargs["voice"] = tts_voice
                                tts_kwargs["speed"] = tts_speed
                                tts_kwargs["instruct"] = tts_instruct
                            elif tts_inference_mode == "comfyui":
                                if tts_workflow:
                                    tts_kwargs["workflow"] = tts_workflow
                                if ref_audio:
                                    tts_kwargs["ref_audio"] = ref_audio

                            audio_path = await morpheus_video_studio.tts(**tts_kwargs)
                            progress_bar.progress(65)
                            status_text.text(tr("progress.concatenating"))

                            # Directly call the second workflow
                            second_workflow_path = Path(workflow_path.get("second_workflow_path"))
                            if not second_workflow_path.exists():
                                raise Exception(f"The second step workflow file does not exist:{second_workflow_path}")
                            with open(second_workflow_path, 'r', encoding='utf-8') as f:
                                second_workflow_config = json.load(f)
                            second_workflow_params = {
                                "videoimage": generated_image_path,
                                "audio": audio_path
                            }
                            workflow_input = str(second_workflow_path)
                            second_result = await kit.execute(workflow_input, second_workflow_params)
                            # Video Link Extraction
                            generated_video_url = None
                            if hasattr(second_result, 'videos') and second_result.videos:
                                generated_video_url = second_result.videos[0]
                            elif hasattr(second_result, 'outputs') and second_result.outputs:
                                for node_id, node_output in second_result.outputs.items():
                                    if isinstance(node_output, dict) and 'videos' in node_output:
                                        videos = node_output['videos']
                                        if videos and len(videos) > 0:
                                            generated_video_url = videos[0]
                                            break
                            if not generated_video_url:
                                raise Exception("The second step of the workflow did not return a video. Please check the workflow configuration.")
                                        
                            final_video_path = os.path.join(task_dir, "final.mp4")
                            timeout = httpx.Timeout(300.0)
                            async with httpx.AsyncClient(timeout=timeout) as client:
                                response = await client.get(generated_video_url)
                                response.raise_for_status()
                                with open(final_video_path, 'wb') as f:
                                    f.write(response.content)
                            progress_bar.progress(100)
                            status_text.text(tr("status.success"))
                            return final_video_path
                        
                        else:
                            #Initialization and parameter preparation
                            task_dir, task_id = create_task_output_dir()
                            logger.info(f"[Initialization] Task Directory: {task_dir}")

                            first_workflow_path = Path(workflow_path.get("first_workflow_path"))
                            third_workflow_path = Path(workflow_path.get("third_workflow_path"))
                            second_workflow_path = Path(workflow_path.get("second_workflow_path"))
                            assert first_workflow_path.exists(), "The first_workflow file does not exist."
                            assert third_workflow_path.exists(), "The third_workflow file does not exist."
                            assert second_workflow_path.exists(), "The  second_workflow file does not exist."

                            if goods_text and goods_text.strip():
                                workflow_path = third_workflow_path
                                workflow_params = {"firstimage": character_assets[0], "secondimage": goods_assets[0]}
                                generated_text = goods_text

                                status_text.text(tr("progress.step_image"))
                                kit = await morpheus_video_studio._get_or_create_comfykit()
                                workflow_config = json.load(open(workflow_path, 'r', encoding='utf8'))
                                workflow_input = str(workflow_path)
                                combine_image = await kit.execute(workflow_input, workflow_params)
                                if combine_image.status != "completed":
                                    raise Exception(f"workflow execution failed: {combine_image.msg}")
                                generated_image_url = getattr(combine_image, "images", [None])[0]
                                status_text.text(tr("progress.step_audio"))
                                audio_path = os.path.join(task_dir, "narration.mp3")
                                tts_inference_mode = video_params.get("tts_inference_mode", "local")
                                tts_voice = video_params.get("tts_voice")
                                tts_speed = video_params.get("tts_speed")
                                tts_instruct = video_params.get("tts_instruct")
                                tts_workflow = video_params.get("tts_workflow")
                                ref_audio = video_params.get("ref_audio")

                                tts_kwargs = {
                                    "text": generated_text,
                                    "output_path": audio_path,
                                    "inference_mode": tts_inference_mode
                                }
                                if tts_inference_mode == "local":
                                    tts_kwargs["voice"] = tts_voice
                                    tts_kwargs["speed"] = tts_speed
                                elif tts_inference_mode == "omnivoice":
                                    tts_kwargs["voice"] = tts_voice
                                    tts_kwargs["speed"] = tts_speed
                                    tts_kwargs["instruct"] = tts_instruct
                                elif tts_inference_mode == "comfyui":
                                    if tts_workflow:
                                        tts_kwargs["workflow"] = tts_workflow
                                    if ref_audio:
                                        tts_kwargs["ref_audio"] = ref_audio

                                audio_path = await morpheus_video_studio.tts(**tts_kwargs)
                                progress_bar.progress(65)
                                status_text.text(tr("progress.concatenating"))

                                if not second_workflow_path.exists():
                                    raise Exception(f"The second step workflow file does not exist:{second_workflow_path}")
                                with open(second_workflow_path, 'r', encoding='utf-8') as f:
                                    second_workflow_config = json.load(f)
                                second_workflow_params = {
                                    "videoimage": generated_image_url,
                                    "audio": audio_path
                                }
                                workflow_input = str(second_workflow_path)
                                second_result = await kit.execute(workflow_input, second_workflow_params)
                                # Video Link Extraction
                                generated_video_url = None
                                if hasattr(second_result, 'videos') and second_result.videos:
                                    generated_video_url = second_result.videos[0]
                                elif hasattr(second_result, 'outputs') and second_result.outputs:
                                    for node_id, node_output in second_result.outputs.items():
                                        if isinstance(node_output, dict) and 'videos' in node_output:
                                            videos = node_output['videos']
                                            if videos and len(videos) > 0:
                                                generated_video_url = videos[0]
                                                break
                                if not generated_video_url:
                                    raise Exception("The second step of the workflow did not return a video. Please check the workflow configuration.")
                                            
                                final_video_path = os.path.join(task_dir, "final.mp4")
                                timeout = httpx.Timeout(300.0)
                                async with httpx.AsyncClient(timeout=timeout) as client:
                                    response = await client.get(generated_video_url)
                                    response.raise_for_status()
                                    with open(final_video_path, 'wb') as f:
                                        f.write(response.content)
                                progress_bar.progress(100)
                                status_text.text(tr("status.success"))
                                return final_video_path
                                
                            else:
                                workflow_path = first_workflow_path
                                workflow_params = {"firstimage": character_assets[0], "secondimage": goods_assets[0], "goodstype": goods_title}
                                
                                status_text.text(tr("progress.step_image"))
                                kit = await morpheus_video_studio._get_or_create_comfykit()
                                workflow_config = json.load(open(workflow_path, 'r', encoding='utf8'))
                                workflow_input = str(workflow_path)
                                synthesis_result = await kit.execute(workflow_input, workflow_params)
                                if synthesis_result.status != "completed":
                                    raise Exception(f"workflow execution failed: {synthesis_result.msg}")
                                generated_image_url = getattr(synthesis_result, "images", [None])[0]
                                generated_text = getattr(synthesis_result, "texts", [None])[0]
                                
                                status_text.text(tr("progress.step_audio"))
                                audio_path = os.path.join(task_dir, "narration.mp3")
                                tts_inference_mode = video_params.get("tts_inference_mode", "local")
                                tts_voice = video_params.get("tts_voice")
                                tts_speed = video_params.get("tts_speed")
                                tts_instruct = video_params.get("tts_instruct")
                                tts_workflow = video_params.get("tts_workflow")
                                ref_audio = video_params.get("ref_audio")

                                tts_kwargs = {
                                    "text": generated_text,
                                    "output_path": audio_path,
                                    "inference_mode": tts_inference_mode
                                }
                                if tts_inference_mode == "local":
                                    tts_kwargs["voice"] = tts_voice
                                    tts_kwargs["speed"] = tts_speed
                                elif tts_inference_mode == "omnivoice":
                                    tts_kwargs["voice"] = tts_voice
                                    tts_kwargs["speed"] = tts_speed
                                    tts_kwargs["instruct"] = tts_instruct
                                elif tts_inference_mode == "comfyui":
                                    if tts_workflow:
                                        tts_kwargs["workflow"] = tts_workflow
                                    if ref_audio:
                                        tts_kwargs["ref_audio"] = ref_audio

                                audio_path = await morpheus_video_studio.tts(**tts_kwargs)
                                progress_bar.progress(65)
                                status_text.text(tr("progress.concatenating"))

                                if not second_workflow_path.exists():
                                    raise Exception(f"The second step workflow file does not exist:{second_workflow_path}")
                                with open(second_workflow_path, 'r', encoding='utf-8') as f:
                                    second_workflow_config = json.load(f)
                                second_workflow_params = {
                                    "videoimage": generated_image_url,
                                    "audio": audio_path
                                }
                                workflow_input = str(second_workflow_path)
                                second_result = await kit.execute(workflow_input, second_workflow_params)
                                # Video Link Extraction
                                generated_video_url = None
                                if hasattr(second_result, 'videos') and second_result.videos:
                                    generated_video_url = second_result.videos[0]
                                elif hasattr(second_result, 'outputs') and second_result.outputs:
                                    for node_id, node_output in second_result.outputs.items():
                                        if isinstance(node_output, dict) and 'videos' in node_output:
                                            videos = node_output['videos']
                                            if videos and len(videos) > 0:
                                                generated_video_url = videos[0]
                                                break
                                if not generated_video_url:
                                    raise Exception("The second step of the workflow did not return a video. Please check the workflow configuration.")
                                            
                                final_video_path = os.path.join(task_dir, "final.mp4")
                                timeout = httpx.Timeout(300.0)
                                async with httpx.AsyncClient(timeout=timeout) as client:
                                    response = await client.get(generated_video_url)
                                    response.raise_for_status()
                                    with open(final_video_path, 'wb') as f:
                                        f.write(response.content)
                                progress_bar.progress(100)
                                status_text.text(tr("status.success"))
                                return final_video_path
                                
                    # Execute async generation
                    final_video_path = run_async(generate_digital_human_video())
                    
                    total_time = time.time() - start_time
                    progress_bar.progress(100)
                    status_text.text(tr("status.success"))
                    
                    # Display result
                    st.success(tr("status.video_generated", path=final_video_path))
                    
                    st.markdown("---")
                    
                    # Video info
                    if os.path.exists(final_video_path):
                        file_size_mb = os.path.getsize(final_video_path) / (1024 * 1024)
                        
                        info_text = (
                            f"⏱️ {tr('info.generation_time')} {total_time:.1f}s   "
                            f"📦 {file_size_mb:.2f}MB"
                        )
                        st.caption(info_text)
                        
                        st.markdown("---")
                        
                        # Video preview
                        st.video(final_video_path)
                        
                        # Download button
                        with open(final_video_path, "rb") as video_file:
                            video_bytes = video_file.read()
                            video_filename = os.path.basename(final_video_path)
                            st.download_button(
                                label="⬇️ 下载视频" if get_language() == "zh_CN" else "⬇️ Download Video",
                                data=video_bytes,
                                file_name=video_filename,
                                mime="video/mp4",
                                use_container_width=True
                            )
                    else:
                        st.error(tr("status.video_not_found", path=final_video_path))
                
                except Exception as e:
                    status_text.text("")
                    progress_bar.empty()
                    st.error(tr("status.error", error=str(e)))
                    logger.exception(e)
                    st.stop()


# Register self
register_pipeline_ui(DigitalHumanPipelineUI)
