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
Content input components for web UI (left column)
"""

import uuid
from collections.abc import Callable
from pathlib import Path

import streamlit as st
from loguru import logger

from morpheus_video_studio.prompts.content_recipes import (
    get_recipe_visual_rules,
    resolve_content_recipe,
)
from morpheus_video_studio.services.scene_draft_generator import (
    SceneDraftGenerationResult,
    generate_scene_drafts,
)
from morpheus_video_studio.services.studio_library import StudioLibraryService
from morpheus_video_studio.utils.content_generators import (
    estimate_scene_plan,
    generate_image_prompts,
    generate_video_prompts,
)
from web.i18n import tr
from web.utils.async_helpers import run_async


def _normalize_scene_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _scene_draft_stage_label(stage: str) -> str:
    return {
        "narration": "正在生成解说...",
        "image_prompts": "正在生成图片提示词...",
        "video_prompts": "正在生成视频提示词...",
    }.get(stage, "正在生成分镜草稿...")


def _scene_draft_completion_status(
    errors: dict[str, str],
) -> tuple[str, str]:
    if errors:
        return "分镜草稿已生成，但部分画面提示词失败", "error"
    return "分镜草稿生成完成", "complete"


def normalize_scene_drafts(
    drafts: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    """Return serializable scene drafts with stable, sequential indices."""
    return [
        {
            "index": index,
            "narration": _normalize_scene_text(draft.get("narration", "")),
            "image_prompt": _normalize_scene_text(draft.get("image_prompt", "")),
            "video_prompt": _normalize_scene_text(draft.get("video_prompt", "")),
        }
        for index, draft in enumerate(drafts or [], start=1)
    ]


def scene_drafts_to_script(drafts: list[dict[str, object]] | None) -> str:
    """Build the legacy script value from narration only."""
    return "\n".join(
        str(draft["narration"]) for draft in normalize_scene_drafts(drafts)
    )


def _missing_scene_prompt_types(
    drafts: list[dict[str, object]] | None,
) -> set[str]:
    """Return visual stages that still have at least one empty scene field."""
    scenes = normalize_scene_drafts(drafts)
    missing: set[str] = set()
    if any(not str(scene["image_prompt"]).strip() for scene in scenes):
        missing.add("image_prompts")
    if any(not str(scene["video_prompt"]).strip() for scene in scenes):
        missing.add("video_prompts")
    return missing


def _apply_selected_content_defaults() -> None:
    content_id = st.session_state.get("studio_selected_content_id")
    if not content_id:
        return
    if st.session_state.get("studio_applied_content_to_quick_create") == content_id:
        return

    item = StudioLibraryService().get_content_item(content_id)
    if not item:
        return

    extracted_path = item.get("extracted_text_path")
    text = ""
    if extracted_path and Path(extracted_path).exists():
        text = Path(extracted_path).read_text(encoding="utf-8")

    st.session_state["quick_create_input_source"] = "手动输入"
    st.session_state["quick_create_text_input_手动输入"] = text
    st.session_state["quick_create_title_input_手动输入"] = item.get("title") or ""
    if text and len(text) > 180:
        st.session_state["quick_create_mode"] = "generate"
    st.session_state["studio_applied_content_to_quick_create"] = content_id


def _clear_quick_create_draft() -> None:
    for key in (
        "quick_create_ai_script_draft",
        "quick_create_ai_script_source_text",
        "quick_create_ai_script_source_mode",
        "quick_create_ai_script_source_scenes",
        "quick_create_ai_script_source_recipe",
        "quick_create_scene_drafts",
        "quick_create_scene_draft_errors",
    ):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith("quick_scene_"):
            st.session_state.pop(key, None)


def _draft_is_stale(
    text: str,
    mode: str,
    n_scenes: int,
    content_recipe: str | None,
) -> bool:
    return any(
        [
            st.session_state.get("quick_create_ai_script_source_text") != text,
            st.session_state.get("quick_create_ai_script_source_mode") != mode,
            st.session_state.get("quick_create_ai_script_source_scenes") != n_scenes,
            st.session_state.get("quick_create_ai_script_source_recipe")
            != content_recipe,
        ]
    )


def resolve_effective_scene_count(
    mode: str,
    selected_scenes: int,
    planning: dict | None,
) -> int:
    """Keep topic targets explicit; only full documents can drive scene count."""
    if mode == "document" and planning:
        return int(planning["recommended_scenes"])
    return int(selected_scenes)


def resolve_narration_length_bounds(target_scene_seconds: float) -> tuple[int, int]:
    """Return a useful spoken-copy range for one scene.

    Chinese narration is roughly three to five characters per second at a
    natural short-video pace.  Keeping the lower bound explicit prevents a
    short topic from being answered with a single fragment.
    """
    seconds = max(float(target_scene_seconds or 6), 3.0)
    return max(12, round(seconds * 3)), max(20, round(seconds * 5))


def _generate_quick_create_scene_drafts(
    morpheus_video_studio,
    *,
    text: str,
    mode: str,
    n_scenes: int,
    content_recipe: str | None = None,
    target_scene_seconds: float = 6,
    progress_callback: Callable[[str], None] | None = None,
) -> SceneDraftGenerationResult:
    if morpheus_video_studio is None or morpheus_video_studio.llm is None:
        raise RuntimeError("当前未初始化 LLM，无法先生成文案草稿。")
    if not text.strip():
        raise RuntimeError("请先输入主题或内容，再生成文案草稿。")

    min_words, max_words = resolve_narration_length_bounds(target_scene_seconds)
    effective_recipe = resolve_content_recipe(text, content_recipe)
    return run_async(
        generate_scene_drafts(
            morpheus_video_studio.llm,
            text=text,
            mode=mode,
            n_scenes=n_scenes,
            min_words=min_words,
            max_words=max_words,
            content_recipe=effective_recipe,
            visual_rules=get_recipe_visual_rules(effective_recipe),
            progress_callback=progress_callback,
        )
    )


def _retry_missing_scene_prompts(
    morpheus_video_studio,
    drafts: list[dict[str, object]],
    errors: dict[str, str],
    *,
    min_words: int,
    max_words: int,
    visual_rules: str,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    scenes = normalize_scene_drafts(drafts)
    remaining_errors = dict(errors)

    missing_image_indexes = [
        index
        for index, scene in enumerate(scenes)
        if not str(scene["image_prompt"]).strip()
    ]
    if missing_image_indexes:
        try:
            prompts = run_async(
                generate_image_prompts(
                    morpheus_video_studio.llm,
                    narrations=[
                        str(scenes[index]["narration"])
                        for index in missing_image_indexes
                    ],
                    min_words=min_words,
                    max_words=max_words,
                    visual_rules=visual_rules,
                )
            )
            if len(prompts) != len(missing_image_indexes):
                raise ValueError(
                    "图片提示词数量不匹配："
                    f"需要 {len(missing_image_indexes)} 条，实际 {len(prompts)} 条"
                )
            normalized_prompts = [_normalize_scene_text(prompt) for prompt in prompts]
            if any(not prompt for prompt in normalized_prompts):
                raise ValueError("图片提示词包含空内容")
            for index, prompt in zip(missing_image_indexes, normalized_prompts):
                scenes[index]["image_prompt"] = prompt
            remaining_errors.pop("image_prompts", None)
        except Exception as exc:
            remaining_errors["image_prompts"] = f"图片提示词生成失败：{exc}"
    else:
        remaining_errors.pop("image_prompts", None)

    missing_video_indexes = [
        index
        for index, scene in enumerate(scenes)
        if not str(scene["video_prompt"]).strip()
    ]
    if missing_video_indexes:
        try:
            prompts = run_async(
                generate_video_prompts(
                    morpheus_video_studio.llm,
                    narrations=[
                        str(scenes[index]["narration"])
                        for index in missing_video_indexes
                    ],
                    min_words=min_words,
                    max_words=max_words,
                )
            )
            if len(prompts) != len(missing_video_indexes):
                raise ValueError(
                    "视频提示词数量不匹配："
                    f"需要 {len(missing_video_indexes)} 条，实际 {len(prompts)} 条"
                )
            normalized_prompts = [_normalize_scene_text(prompt) for prompt in prompts]
            if any(not prompt for prompt in normalized_prompts):
                raise ValueError("视频提示词包含空内容")
            for index, prompt in zip(missing_video_indexes, normalized_prompts):
                scenes[index]["video_prompt"] = prompt
            remaining_errors.pop("video_prompts", None)
        except Exception as exc:
            remaining_errors["video_prompts"] = f"视频提示词生成失败：{exc}"
    else:
        remaining_errors.pop("video_prompts", None)

    return scenes, remaining_errors


def render_content_input(morpheus_video_studio=None):
    """Render content input section (left column) with batch support"""
    _apply_selected_content_defaults()

    with st.container(border=True):
        st.markdown(f"**{tr('section.content_input')}**")
        
        # ====================================================================
        # Step 1: Batch mode toggle (highest priority)
        # ====================================================================
        batch_mode = st.checkbox(
            tr("batch.mode_label"),
            value=False,
            help=tr("batch.mode_help")
        )
        
        if not batch_mode:
            # ================================================================
            # Single task mode (original logic, unchanged)
            # ================================================================
            # Processing mode selection
            mode = st.radio(
                "Processing Mode",
                ["generate", "fixed"],
                horizontal=True,
                format_func=lambda x: tr(f"mode.{x}"),
                label_visibility="collapsed",
                key="quick_create_mode",
            )

            input_source = st.radio(
                "内容来源",
                ["手动输入", "上传文档"],
                horizontal=True,
                key="quick_create_input_source",
            )
            effective_mode = "document" if input_source == "上传文档" else mode
            
            # Text input (unified for both modes)
            text_placeholder = tr("input.topic_placeholder") if mode == "generate" else tr("input.content_placeholder")
            text_height = 120 if mode == "generate" else 200
            text_help = tr("input.text_help_generate") if mode == "generate" else tr("input.text_help_fixed")

            document_title = ""
            extracted_text = ""
            if input_source == "上传文档":
                uploaded_doc = st.file_uploader(
                    "上传 PDF / Word / PPT / Excel / TXT",
                    type=["pdf", "docx", "doc", "pptx", "xlsx", "txt", "md", "markdown", "csv", "json", "rtf"],
                    key="quick_create_document_upload",
                    help="会提取文档正文作为创作素材，后续视频画面仍由右侧素材设置决定。",
                )
                if uploaded_doc:
                    upload_dir = Path("temp/quick_create_docs") / st.session_state.get(
                        "quick_create_doc_upload_id", uuid.uuid4().hex[:12]
                    )
                    st.session_state.quick_create_doc_upload_id = upload_dir.name
                    upload_dir.mkdir(parents=True, exist_ok=True)
                    doc_path = upload_dir / uploaded_doc.name
                    doc_path.write_bytes(uploaded_doc.getbuffer())

                    try:
                        from morpheus_video_studio.utils.document_text import (
                            extract_text_from_document,
                        )

                        extracted_text = extract_text_from_document(doc_path)
                        document_title = doc_path.stem
                        st.success(f"已提取文档文本：{len(extracted_text)} 字")
                        with st.expander("查看提取内容", expanded=False):
                            st.text_area(
                                "文档文本",
                                value=extracted_text,
                                height=240,
                                key="quick_create_document_text_preview",
                            )
                    except Exception as exc:
                        st.error(f"文档解析失败：{exc}")
            
            content_recipe = "general"
            if effective_mode == "generate":
                from morpheus_video_studio.prompts.content_recipes import list_content_recipes

                recipe_options = list_content_recipes()
                recipe_ids = [item["id"] for item in recipe_options]
                recipe_labels = {item["id"]: item["label"] for item in recipe_options}
                recipe_descriptions = {item["id"]: item["description"] for item in recipe_options}
                content_recipe = st.selectbox(
                    "内容栏目",
                    recipe_ids,
                    format_func=lambda value: recipe_labels[value],
                    help="选择最接近的内容题材，AI 会采用相应的叙事结构；具体主题仍由你自由填写。",
                    key="quick_create_content_recipe",
                )
                st.caption(recipe_descriptions[content_recipe])

            text = st.text_area(
                tr("input.text"),
                value=extracted_text if input_source == "上传文档" else "",
                placeholder=(
                    "上传文档后会自动填入提取内容，AI 会基于这些资料生成视频文案。"
                    if input_source == "上传文档"
                    else text_placeholder
                ),
                height=220 if input_source == "上传文档" else text_height,
                help=text_help,
                key=f"quick_create_text_input_{input_source}"
            )
            
            # Split mode selector (only show in fixed mode)
            clip_duration_hint = float(st.session_state.get("quick_video_clip_duration", 6) or 6)
            tts_speed_hint = float(st.session_state.get("tts_speed") or 1.0)
            planning = estimate_scene_plan(
                text,
                target_scene_seconds=clip_duration_hint,
                tts_speed=tts_speed_hint,
                min_scenes=1,
                max_scenes=30,
            ) if text.strip() else None

            if effective_mode == "fixed":
                split_mode_options = {
                    "auto": "自动切分（推荐）",
                    "paragraph": tr("split.mode_paragraph"),
                    "line": tr("split.mode_line"),
                    "sentence": tr("split.mode_sentence"),
                }
                split_mode = st.selectbox(
                    tr("split.mode_label"),
                    options=list(split_mode_options.keys()),
                    format_func=lambda x: split_mode_options[x],
                    index=0,
                    help="自动模式会优先按段落/换行切分；如果只有一大段，会再按句子智能合并成多个分镜。",
                )
                if planning:
                    st.info(
                        f"按当前文案估算：旁白约 {planning['estimated_duration_seconds']:.1f} 秒，"
                        f"建议至少 {planning['recommended_scenes']} 个分镜。"
                    )
            else:
                split_mode = "paragraph"  # Default for generate mode (not used)
            
            # Title input (optional for both modes)
            title = st.text_input(
                tr("input.title"),
                value=document_title if input_source == "上传文档" else "",
                placeholder=tr("input.title_placeholder"),
                help=tr("input.title_help"),
                key=f"quick_create_title_input_{input_source}"
            )
            
            # Number of scenes (only show in generate mode)
            if effective_mode in ("generate", "document"):
                auto_scene_count = False
                if effective_mode == "document":
                    auto_scene_count = st.checkbox(
                        "按文档长度自动估算分镜数",
                        value=True,
                        key="quick_create_auto_scene_count",
                        help="根据已经提取的完整文档估算旁白时长和分镜数量。",
                    )
                n_scenes = st.slider(
                    tr("video.frames"),
                    min_value=3,
                    max_value=30,
                    value=5,
                    help=tr("video.frames_help"),
                    label_visibility="collapsed",
                    key="quick_create_n_scenes",
                )
                effective_n_scenes = resolve_effective_scene_count(
                    effective_mode,
                    n_scenes,
                    planning if auto_scene_count else None,
                )
                if effective_mode == "document" and auto_scene_count and planning:
                    st.info(
                        f"按当前文档预估：旁白约 {planning['estimated_duration_seconds']:.1f} 秒，"
                        f"本次将自动使用 {effective_n_scenes} 个分镜。"
                    )
                else:
                    st.caption(f"本次将按 {effective_n_scenes} 个目标分镜生成完整文案。")
            else:
                # Fixed mode: n_scenes is ignored, set default value
                effective_n_scenes = planning["recommended_scenes"] if planning else 5
                n_scenes = effective_n_scenes
                st.info(tr("video.frames_fixed_mode_hint"))

            st.session_state["quick_create_effective_n_scenes"] = int(effective_n_scenes)

            scene_drafts: list[dict[str, object]] = []
            ai_script_draft = None
            if effective_mode in ("generate", "document"):
                action_col, clear_col = st.columns([1, 1])
                with action_col:
                    if st.button("先生成分镜草稿", key="quick_create_generate_draft", use_container_width=True):
                        draft_status = st.status(
                            _scene_draft_stage_label("narration"),
                            expanded=True,
                        )
                        try:
                            def update_draft_stage(stage: str) -> None:
                                draft_status.update(
                                    label=_scene_draft_stage_label(stage),
                                    state="running",
                                )

                            result = _generate_quick_create_scene_drafts(
                                morpheus_video_studio,
                                text=text,
                                mode=effective_mode,
                                n_scenes=effective_n_scenes,
                                content_recipe=content_recipe,
                                target_scene_seconds=clip_duration_hint,
                                progress_callback=update_draft_stage,
                            )
                            completion_label, completion_state = (
                                _scene_draft_completion_status(result.errors)
                            )
                            draft_status.update(
                                label=completion_label,
                                state=completion_state,
                                expanded=False,
                            )
                            scene_drafts = normalize_scene_drafts(
                                [scene.to_dict() for scene in result.scenes]
                            )
                            for key in list(st.session_state):
                                if key.startswith("quick_scene_"):
                                    st.session_state.pop(key, None)
                            for scene in scene_drafts:
                                index = int(scene["index"])
                                st.session_state[f"quick_scene_{index}_narration"] = scene["narration"]
                                st.session_state[f"quick_scene_{index}_image_prompt"] = scene["image_prompt"]
                                st.session_state[f"quick_scene_{index}_video_prompt"] = scene["video_prompt"]
                            st.session_state["quick_create_scene_drafts"] = scene_drafts
                            st.session_state["quick_create_scene_draft_errors"] = dict(result.errors)
                            st.session_state["quick_create_ai_script_draft"] = scene_drafts_to_script(
                                scene_drafts
                            )
                            st.session_state["quick_create_ai_script_source_text"] = text
                            st.session_state["quick_create_ai_script_source_mode"] = effective_mode
                            st.session_state["quick_create_ai_script_source_scenes"] = effective_n_scenes
                            st.session_state["quick_create_ai_script_source_recipe"] = (
                                resolve_content_recipe(text, content_recipe)
                            )
                            st.success("分镜草稿已生成；旁白和画面提示词可以分别修改。")
                        except Exception as exc:
                            draft_status.update(
                                label="分镜草稿生成失败",
                                state="error",
                            )
                            st.error(f"分镜草稿生成失败：{exc}")
                            logger.exception(exc)
                with clear_col:
                    if st.button("清空草稿", key="quick_create_clear_draft", use_container_width=True):
                        _clear_quick_create_draft()
                        st.rerun()

                scene_drafts = normalize_scene_drafts(
                    st.session_state.get("quick_create_scene_drafts")
                )
                if scene_drafts:
                    scene_drafts = normalize_scene_drafts(
                        [
                            {
                                "index": scene["index"],
                                "narration": st.session_state.get(
                                    f"quick_scene_{scene['index']}_narration",
                                    scene["narration"],
                                ),
                                "image_prompt": st.session_state.get(
                                    f"quick_scene_{scene['index']}_image_prompt",
                                    scene["image_prompt"],
                                ),
                                "video_prompt": st.session_state.get(
                                    f"quick_scene_{scene['index']}_video_prompt",
                                    scene["video_prompt"],
                                ),
                            }
                            for scene in scene_drafts
                        ]
                    )
                    st.session_state["quick_create_scene_drafts"] = scene_drafts
                    ai_script_draft = scene_drafts_to_script(scene_drafts)
                    st.session_state["quick_create_ai_script_draft"] = ai_script_draft

                    effective_recipe = resolve_content_recipe(text, content_recipe)
                    if _draft_is_stale(
                        text,
                        effective_mode,
                        effective_n_scenes,
                        effective_recipe,
                    ):
                        st.warning("你已经改过主题、内容或分镜数，当前草稿可能已过期，建议重新生成。")

                    scene_errors = dict(
                        st.session_state.get("quick_create_scene_draft_errors") or {}
                    )
                    missing_prompt_types = _missing_scene_prompt_types(scene_drafts)
                    scene_errors = {
                        key: value
                        for key, value in scene_errors.items()
                        if key in missing_prompt_types
                    }
                    st.session_state["quick_create_scene_draft_errors"] = scene_errors
                    for error in scene_errors.values():
                        st.warning(error)
                    if missing_prompt_types and st.button(
                        "重试缺失的画面提示词",
                        key="quick_create_retry_scene_prompts",
                        use_container_width=True,
                    ):
                        try:
                            min_words, max_words = resolve_narration_length_bounds(
                                clip_duration_hint
                            )
                            with st.spinner("正在重新生成缺失的画面提示词..."):
                                scene_drafts, scene_errors = _retry_missing_scene_prompts(
                                    morpheus_video_studio,
                                    scene_drafts,
                                    scene_errors,
                                    min_words=min_words,
                                    max_words=max_words,
                                    visual_rules=get_recipe_visual_rules(effective_recipe),
                                )
                            for scene in scene_drafts:
                                index = int(scene["index"])
                                st.session_state[f"quick_scene_{index}_narration"] = scene["narration"]
                                st.session_state[f"quick_scene_{index}_image_prompt"] = scene["image_prompt"]
                                st.session_state[f"quick_scene_{index}_video_prompt"] = scene["video_prompt"]
                            st.session_state["quick_create_scene_drafts"] = scene_drafts
                            st.session_state["quick_create_scene_draft_errors"] = scene_errors
                            ai_script_draft = scene_drafts_to_script(scene_drafts)
                            st.session_state["quick_create_ai_script_draft"] = ai_script_draft
                            if scene_errors:
                                for error in scene_errors.values():
                                    st.warning(error)
                            else:
                                st.success("缺失的画面提示词已重新生成。")
                        except Exception as exc:
                            st.error(f"画面提示词重试失败：{exc}")
                            logger.exception(exc)

                    edited_scene_drafts = []
                    for scene in scene_drafts:
                        index = int(scene["index"])
                        narration_key = f"quick_scene_{index}_narration"
                        image_prompt_key = f"quick_scene_{index}_image_prompt"
                        video_prompt_key = f"quick_scene_{index}_video_prompt"
                        if narration_key not in st.session_state:
                            st.session_state[narration_key] = scene["narration"]
                        if image_prompt_key not in st.session_state:
                            st.session_state[image_prompt_key] = scene["image_prompt"]
                        if video_prompt_key not in st.session_state:
                            st.session_state[video_prompt_key] = scene["video_prompt"]

                        with st.container(border=True):
                            st.markdown(f"**分镜 {index}**")
                            narration = st.text_area(
                                "旁白",
                                key=narration_key,
                                height=100,
                            )
                            with st.expander("画面提示词", expanded=False):
                                image_prompt = st.text_area(
                                    "图片提示词",
                                    key=image_prompt_key,
                                    height=100,
                                )
                                video_prompt = st.text_area(
                                    "视频提示词",
                                    key=video_prompt_key,
                                    height=100,
                                )
                        edited_scene_drafts.append(
                            {
                                "index": index,
                                "narration": narration,
                                "image_prompt": image_prompt,
                                "video_prompt": video_prompt,
                            }
                        )

                    scene_drafts = normalize_scene_drafts(edited_scene_drafts)
                    st.session_state["quick_create_scene_drafts"] = scene_drafts
                    ai_script_draft = scene_drafts_to_script(scene_drafts)
                    st.session_state["quick_create_ai_script_draft"] = ai_script_draft
                    draft_plan = estimate_scene_plan(
                        scene_drafts_to_script(scene_drafts),
                        target_scene_seconds=clip_duration_hint,
                        tts_speed=tts_speed_hint,
                        min_scenes=1,
                        max_scenes=30,
                    )
                    st.caption(
                        f"当前草稿预计旁白约 {draft_plan['estimated_duration_seconds']:.1f} 秒；"
                        f"目标为 {effective_n_scenes} 个分镜。"
                    )
                else:
                    ai_script_draft = st.session_state.get(
                        "quick_create_ai_script_draft"
                    )
            
            return {
                "batch_mode": False,
                "mode": effective_mode,
                "text": text,
                "title": title,
                "n_scenes": effective_n_scenes,
                "split_mode": split_mode,
                "scene_drafts": scene_drafts,
                "ai_script_draft": ai_script_draft,
                "content_recipe": content_recipe,
            }
        
        else:
            # ================================================================
            # Batch mode (simplified YAGNI version)
            # ================================================================
            st.markdown(f"**{tr('batch.section_title')}**")
            
            # Batch rules info
            st.info(f"""
**{tr('batch.rules_title')}**
- ✅ {tr('batch.rule_1')}
- ✅ {tr('batch.rule_2')}
- ✅ {tr('batch.rule_3')}
            """)
            
            # Batch topics input
            text_input = st.text_area(
                tr("batch.topics_label"),
                height=300,
                placeholder=tr("batch.topics_placeholder"),
                help=tr("batch.topics_help")
            )
            
            # Split topics by newline
            if text_input:
                # Simple split by newline, filter empty lines
                topics = [
                    line.strip() 
                    for line in text_input.strip().split('\n') 
                    if line.strip()
                ]
                
                if topics:
                    # Check count limit
                    if len(topics) > 100:
                        st.error(tr("batch.count_error", count=len(topics)))
                        topics = []
                    else:
                        st.success(tr("batch.count_success", count=len(topics)))
                        
                        # Preview topics list
                        with st.expander(tr("batch.preview_title"), expanded=False):
                            for i, topic in enumerate(topics, 1):
                                st.markdown(f"`{i}.` {topic}")
                else:
                    topics = []
            else:
                topics = []
            
            st.markdown("---")
            
            # Title prefix (optional)
            title_prefix = st.text_input(
                tr("batch.title_prefix_label"),
                placeholder=tr("batch.title_prefix_placeholder"),
                help=tr("batch.title_prefix_help")
            )
            
            # Number of scenes (unified for all videos)
            n_scenes = st.slider(
                tr("batch.n_scenes_label"),
                min_value=3,
                max_value=30,
                value=5,
                help=tr("batch.n_scenes_help")
            )
            st.caption(tr("batch.n_scenes_caption", n=n_scenes))
            
            # Config info
            st.info(f"📌 {tr('batch.config_info')}")
            
            return {
                "batch_mode": True,
                "topics": topics,
                "mode": "generate",  # Fixed to AI generate content
                "title_prefix": title_prefix,
                "n_scenes": n_scenes,
            }


def render_bgm_section(key_prefix=""):
    """Render BGM selection section"""
    with st.container(border=True):
        st.markdown(f"**{tr('section.bgm')}**")
        
        with st.expander(tr("help.feature_description"), expanded=False):
            st.markdown(f"**{tr('help.what')}**")
            st.markdown(tr("bgm.what"))
            st.markdown(f"**{tr('help.how')}**")
            st.markdown(tr("bgm.how"))
        
        # Dynamically scan bgm folder for music files (merged from bgm/ and data/bgm/)
        from morpheus_video_studio.utils.os_util import list_resource_files
        
        try:
            all_files = list_resource_files("bgm")
            # Filter to audio files only
            audio_extensions = ('.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg')
            bgm_files = sorted([f for f in all_files if f.lower().endswith(audio_extensions)])
        except Exception as e:
            st.warning(f"Failed to load BGM files: {e}")
            bgm_files = []
        
        # Add special "None" option
        bgm_options = [tr("bgm.none")] + bgm_files
        
        # Default to "default.mp3" if exists, otherwise first option
        default_index = 0
        if "default.mp3" in bgm_files:
            default_index = bgm_options.index("default.mp3")
        
        bgm_choice = st.selectbox(
            "BGM",
            bgm_options,
            index=default_index,
            label_visibility="collapsed",
            key=f"{key_prefix}bgm_selector"
        )
        
        # BGM volume slider (only show when BGM is selected)
        if bgm_choice != tr("bgm.none"):
            bgm_volume = st.slider(
                tr("bgm.volume"),
                min_value=0.0,
                max_value=0.5,
                value=0.2,
                step=0.01,
                format="%.2f",
                key=f"{key_prefix}bgm_volume_slider",
                help=tr("bgm.volume_help")
            )
        else:
            bgm_volume = 0.2  # Default value when no BGM selected
        
        # BGM preview button (only if BGM is not "None")
        if bgm_choice != tr("bgm.none"):
            if st.button(tr("bgm.preview"), key=f"{key_prefix}preview_bgm", use_container_width=True):
                from morpheus_video_studio.utils.os_util import get_resource_path, resource_exists
                try:
                    if resource_exists("bgm", bgm_choice):
                        bgm_file_path = get_resource_path("bgm", bgm_choice)
                        st.audio(bgm_file_path)
                    else:
                        st.error(tr("bgm.preview_failed", file=bgm_choice))
                except Exception as e:
                    st.error(f"{tr('bgm.preview_failed', file=bgm_choice)}: {e}")
        
        # Use full filename for bgm_path (including extension)
        bgm_path = None if bgm_choice == tr("bgm.none") else bgm_choice
    
    return {
        "bgm_path": bgm_path,
        "bgm_volume": bgm_volume
    }
