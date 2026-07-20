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
Standard Video Generation Pipeline

Standard workflow for generating short videos from topic or fixed script.
This is the default pipeline for general-purpose video generation.
Refactored to use LinearVideoPipeline (Template Method Pattern).
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Literal, List
import asyncio
import shutil

from loguru import logger

from morpheus_video_studio.pipelines.linear import LinearVideoPipeline, PipelineContext
from morpheus_video_studio.models.progress import ProgressEvent
from morpheus_video_studio.models.storyboard import (
    Storyboard,
    StoryboardFrame,
    StoryboardConfig,
    ContentMetadata,
    VideoGenerationResult
)
from morpheus_video_studio.utils.content_generators import (
    generate_title,
    generate_narrations_from_topic,
    generate_narrations_from_content,
    split_narration_script,
    generate_image_prompts,
    generate_video_prompts,
)
from morpheus_video_studio.utils.os_util import (
    create_task_output_dir,
    get_task_final_video_path
)
from morpheus_video_studio.utils.template_util import get_template_type
from morpheus_video_studio.utils.prompt_helper import build_image_prompt
from morpheus_video_studio.utils.video_qa import inspect_final_video
from morpheus_video_studio.utils.subtitle_export import export_srt
from morpheus_video_studio.services.video import VideoService




class StandardPipeline(LinearVideoPipeline):
    """
    Standard video generation pipeline
    
    Workflow:
    1. Generate/determine title
    2. Generate narrations (from topic or split fixed script)
    3. Generate image prompts for each narration
    4. For each frame:
       - Generate audio (TTS)
       - Generate image
       - Compose frame with template
       - Create video segment
    5. Concatenate all segments
    6. Add BGM (optional)
    
    Supports two modes:
    - "generate": LLM generates narrations from topic
    - "fixed": Use provided script as-is (each line = one narration)
    """
    
    # ==================== Lifecycle Methods ====================

    async def setup_environment(self, ctx: PipelineContext):
        """Step 1: Setup task directory and environment."""
        text = ctx.input_text
        mode = ctx.params.get("mode", "generate")
        
        logger.info(f"🚀 Starting StandardPipeline in '{mode}' mode")
        logger.info(f"   Text length: {len(text)} chars")

        # Resume: reuse a prior interrupted task's dir and reload its storyboard,
        # so already-finished frame segments are kept and only the missing tail
        # is regenerated (frame_processor skips frames whose segment exists).
        resume_task_id = ctx.params.get("resume_task_id")
        if resume_task_id:
            storyboard = await self.core.persistence.load_storyboard(resume_task_id)
            if storyboard is not None:
                ctx.task_id = resume_task_id
                ctx.task_dir = str(Path(get_task_final_video_path(resume_task_id)).parent)
                ctx.storyboard = storyboard
                ctx.config = storyboard.config
                ctx.narrations = [f.narration for f in storyboard.frames]
                ctx.title = storyboard.title
                ctx.resumed = True
                ctx.final_video_path = get_task_final_video_path(resume_task_id)
                logger.info(f"⏪ Resuming task {resume_task_id} ({len(storyboard.frames)} frames)")
                return
            logger.warning(f"Resume requested but storyboard {resume_task_id} not found; starting fresh")

        # Create isolated task directory
        task_dir, task_id = create_task_output_dir()
        ctx.task_id = task_id
        ctx.task_dir = task_dir

        logger.info(f"📁 Task directory created: {task_dir}")
        logger.info(f"   Task ID: {task_id}")
        
        # Determine final video path
        output_path = ctx.params.get("output_path")
        if output_path is None:
            ctx.final_video_path = get_task_final_video_path(task_id)
        else:
            # We will copy to this path in finalize/post_production
            # For internal processing, we still use the task dir path? 
            # Actually StandardPipeline logic used get_task_final_video_path as the target for concat
            # and then copied. Let's stick to that.
            ctx.final_video_path = get_task_final_video_path(task_id)
            logger.info(f"   Will copy final video to: {output_path}")

    async def generate_content(self, ctx: PipelineContext):
        """Step 2: Generate or process script/narrations."""
        if ctx.resumed:
            return
        mode = ctx.params.get("mode", "generate")
        text = ctx.input_text
        n_scenes = ctx.params.get("n_scenes", 5)
        min_words = ctx.params.get("min_narration_words", 5)
        max_words = ctx.params.get("max_narration_words", 20)
        
        if mode == "generate":
            self._report_progress(ctx.progress_callback, "generating_narrations", 0.05)
            ctx.narrations = await generate_narrations_from_topic(
                self.llm,
                content_recipe=ctx.params.get("content_recipe"),
                topic=text,
                n_scenes=n_scenes,
                min_words=min_words,
                max_words=max_words
            )
            logger.info(f"✅ Generated {len(ctx.narrations)} narrations")
        elif mode == "document":
            self._report_progress(ctx.progress_callback, "generating_narrations", 0.05)
            ctx.narrations = await generate_narrations_from_content(
                self.llm,
                content=text,
                n_scenes=n_scenes,
                min_words=min_words,
                max_words=max_words
            )
            logger.info(f"✅ Generated {len(ctx.narrations)} narrations from document")
        else:  # fixed
            self._report_progress(ctx.progress_callback, "splitting_script", 0.05)
            split_mode = ctx.params.get("split_mode", "paragraph")
            ctx.narrations = await split_narration_script(
                text,
                split_mode=split_mode,
                target_segments=n_scenes,
                max_chars_per_segment=max(24, int(max_words * 3)),
            )
            logger.info(f"✅ Split script into {len(ctx.narrations)} segments (mode={split_mode})")
            logger.info(f"   Target scene count for splitting: {n_scenes}")

    async def determine_title(self, ctx: PipelineContext):
        """Step 3: Determine or generate video title."""
        if ctx.resumed:
            return
        # Note: Swapped order with generate_content in base class call, 
        # but in StandardPipeline original code, title was determined BEFORE narrations.
        # However, LinearVideoPipeline defines generate_content BEFORE determine_title.
        # This is fine as they are independent in StandardPipeline logic.
        
        title = ctx.params.get("title")
        mode = ctx.params.get("mode", "generate")
        text = ctx.input_text
        
        if title:
            ctx.title = title
            logger.info(f"   Title: '{title}' (user-specified)")
        else:
            self._report_progress(ctx.progress_callback, "generating_title", 0.01)
            if mode == "generate":
                ctx.title = await generate_title(self.llm, text, strategy="auto")
                logger.info(f"   Title: '{ctx.title}' (auto-generated)")
            elif mode == "document":
                ctx.title = await generate_title(self.llm, text, strategy="llm")
                logger.info(f"   Title: '{ctx.title}' (document-generated)")
            else:  # fixed
                ctx.title = await generate_title(self.llm, text, strategy="llm")
                logger.info(f"   Title: '{ctx.title}' (LLM-generated)")

    async def plan_visuals(self, ctx: PipelineContext):
        """Step 4: Generate image prompts or visual descriptions."""
        if ctx.resumed:
            return
        media_workflow = ctx.params.get("media_workflow") or ""
        media_strategy = ctx.params.get("media_strategy", "")

        # Detect template type to determine if media generation is needed
        frame_template = (
            ctx.params.get("frame_template")
            or self.core.config.get("template", {}).get("default_template")
            or "1080x1920/default.html"
        )
        
        template_name = Path(frame_template).name
        template_type = get_template_type(template_name)
        template_requires_media = (template_type in ["image", "video"])
        
        if template_type == "image":
            logger.info(f"📸 Template requires image generation")
        elif template_type == "video":
            logger.info(f"🎬 Template requires video generation")
        else:  # static
            logger.info(f"⚡ Static template - skipping media generation pipeline")
            logger.info(f"   💡 Benefits: Faster generation + Lower cost + No ComfyUI dependency")
        
        # Stock video modes should stay semantic-first. Converting narrations
        # into static illustration prompts before searching stock footage
        # degrades relevance.
        if template_requires_media:
            if (
                media_workflow.startswith("stock/")
                or media_strategy in {"stock_turbo", "stock_first"}
            ):
                ctx.image_prompts = [
                    f"{ctx.title}. {narration}".strip(". ")
                    for narration in ctx.narrations
                ]
                logger.info("🎬 Stock video mode - using title/narrations as stock material queries")
                return

            self._report_progress(ctx.progress_callback, "generating_image_prompts", 0.15)
            
            prompt_prefix = ctx.params.get("prompt_prefix")
            min_words = ctx.params.get("min_image_prompt_words", 30)
            max_words = ctx.params.get("max_image_prompt_words", 60)
            
            # Override prompt_prefix if provided
            original_prefix = None
            if prompt_prefix is not None:
                image_config = self.core.config.get("comfyui", {}).get("image", {})
                original_prefix = image_config.get("prompt_prefix")
                image_config["prompt_prefix"] = prompt_prefix
                logger.info(f"Using custom prompt_prefix: '{prompt_prefix}'")
            
            try:
                # Create progress callback wrapper for image prompt generation
                def image_prompt_progress(completed: int, total: int, message: str):
                    batch_progress = completed / total if total > 0 else 0
                    overall_progress = 0.15 + (batch_progress * 0.15)
                    self._report_progress(
                        ctx.progress_callback,
                        "generating_image_prompts",
                        overall_progress,
                        extra_info=message
                    )
                
                # Video workflows need motion-oriented prompts; image workflows
                # still use static image prompts.
                if template_type == "video":
                    base_image_prompts = await generate_video_prompts(
                        self.llm,
                        narrations=ctx.narrations,
                        min_words=min_words,
                        max_words=max_words,
                        progress_callback=image_prompt_progress,
                    )
                else:
                    base_image_prompts = await generate_image_prompts(
                        self.llm,
                        narrations=ctx.narrations,
                        min_words=min_words,
                        max_words=max_words,
                        progress_callback=image_prompt_progress,
                    )
                
                # Apply prompt prefix
                media_config_name = "video" if template_type == "video" else "image"
                media_config = self.core.config.get("comfyui", {}).get(media_config_name, {})
                prompt_prefix_to_use = prompt_prefix if prompt_prefix is not None else media_config.get("prompt_prefix", "")
                
                ctx.image_prompts = []
                for base_prompt in base_image_prompts:
                    final_prompt = build_image_prompt(base_prompt, prompt_prefix_to_use)
                    ctx.image_prompts.append(final_prompt)
                
            finally:
                # Restore original prompt_prefix
                if original_prefix is not None:
                    image_config["prompt_prefix"] = original_prefix
            
            logger.info(f"✅ Generated {len(ctx.image_prompts)} image prompts")
        else:
            # Static template - skip image prompt generation entirely
            ctx.image_prompts = [None] * len(ctx.narrations)
            logger.info(f"⚡ Skipped image prompt generation (static template)")
            logger.info(f"   💡 Savings: {len(ctx.narrations)} LLM calls + {len(ctx.narrations)} media generations")

    async def initialize_storyboard(self, ctx: PipelineContext):
        """Step 5: Create Storyboard object and frames."""
        if ctx.resumed:
            return
        # === Handle TTS parameter compatibility ===
        tts_inference_mode = ctx.params.get("tts_inference_mode")
        tts_voice = ctx.params.get("tts_voice")
        voice_id = ctx.params.get("voice_id")
        tts_workflow = ctx.params.get("tts_workflow")
        
        final_voice_id = None
        final_tts_workflow = tts_workflow
        
        if tts_inference_mode:
            # New API from web UI
            if tts_inference_mode == "local":
                final_voice_id = tts_voice or "zh-CN-YunjianNeural"
                final_tts_workflow = None
                logger.debug(f"TTS Mode: local (voice={final_voice_id})")
            elif tts_inference_mode == "omnivoice":
                final_voice_id = tts_voice or "default"
                final_tts_workflow = None
                logger.debug(f"TTS Mode: omnivoice (voice={final_voice_id})")
            elif tts_inference_mode == "comfyui":
                final_voice_id = None
                logger.debug(f"TTS Mode: comfyui (workflow={final_tts_workflow})")
        else:
            # Old API
            final_voice_id = voice_id or tts_voice or "zh-CN-YunjianNeural"
            logger.debug(f"TTS Mode: legacy (voice_id={final_voice_id}, workflow={final_tts_workflow})")
            
        # Create config
        ctx.config = StoryboardConfig(
            task_id=ctx.task_id,
            n_storyboard=len(ctx.narrations), # Use actual length
            min_narration_words=ctx.params.get("min_narration_words", 5),
            max_narration_words=ctx.params.get("max_narration_words", 20),
            min_image_prompt_words=ctx.params.get("min_image_prompt_words", 30),
            max_image_prompt_words=ctx.params.get("max_image_prompt_words", 60),
            video_fps=ctx.params.get("video_fps", 30),
            min_segment_duration=float(ctx.params.get("min_segment_duration", 0.0)),
            scene_trailing_silence=float(ctx.params.get("scene_trailing_silence", 0.0)),
            shot_min_seconds=float(ctx.params.get("shot_min_seconds", 2.4)),
            shot_max_seconds=float(ctx.params.get("shot_max_seconds", 4.2)),
            shot_max_count=int(ctx.params.get("shot_max_count", 3)),
            shot_hard_max_hold_seconds=(
                float(ctx.params["shot_hard_max_hold_seconds"])
                if ctx.params.get("shot_hard_max_hold_seconds") is not None
                else None
            ),
            tts_inference_mode=tts_inference_mode or "local",
            voice_id=final_voice_id,
            tts_workflow=final_tts_workflow,
            tts_speed=ctx.params.get("tts_speed", 1.2),
            tts_instruct=ctx.params.get("tts_instruct"),
            ref_audio=ctx.params.get("ref_audio"),
            media_width=ctx.params.get("media_width"),
            media_height=ctx.params.get("media_height"),
            media_workflow=(
                ctx.params.get("media_workflow")
                or (
                    self.core.config.get("comfyui", {}).get("video", {}).get("default_workflow")
                    if get_template_type(Path(
                        ctx.params.get("frame_template")
                        or self.core.config.get("template", {}).get("default_template")
                        or "1080x1920/default.html"
                    ).name) == "video"
                    else None
                )
            ),
            frame_template=(
                ctx.params.get("frame_template")
                or self.core.config.get("template", {}).get("default_template")
                or "1080x1920/default.html"
            ),
            template_params=ctx.params.get("template_params"),
            stock_selection_mode=ctx.params.get("stock_selection_mode", "sequential"),
            image_motion_mode=ctx.params.get("image_motion_mode", "float"),
            image_motion_choices=ctx.params.get("image_motion_choices", ["float"]),
            subtitle_customization_enabled=ctx.params.get("subtitle_customization_enabled", False),
            subtitle_enabled=ctx.params.get("subtitle_enabled", True),
            subtitle_font=ctx.params.get("subtitle_font", "Microsoft YaHei"),
            subtitle_position=ctx.params.get("subtitle_position", "bottom"),
            subtitle_color=ctx.params.get("subtitle_color", "#FFFFFF"),
            subtitle_size=ctx.params.get("subtitle_size", 60),
            subtitle_stroke_color=ctx.params.get("subtitle_stroke_color", "#000000"),
            subtitle_stroke_width=ctx.params.get("subtitle_stroke_width", 1.5),
        )
        
        # Create storyboard
        ctx.storyboard = Storyboard(
            title=ctx.title,
            config=ctx.config,
            content_metadata=ctx.params.get("content_metadata"),
            created_at=datetime.now()
        )
        
        # Create frames
        for i, (narration, image_prompt) in enumerate(zip(ctx.narrations, ctx.image_prompts)):
            frame = StoryboardFrame(
                index=i,
                narration=narration,
                image_prompt=image_prompt,
                created_at=datetime.now()
            )
            ctx.storyboard.frames.append(frame)

        # Persist the storyboard before producing assets, so an interrupted run
        # can be resumed (reload this storyboard, reuse finished frame segments).
        try:
            await self.core.persistence.save_storyboard(ctx.task_id, ctx.storyboard)
        except Exception as exc:
            logger.warning(f"Early storyboard persist failed (resume disabled for this run): {exc}")

    async def produce_assets(self, ctx: PipelineContext):
        """Step 6: Generate audio, images, and render frames (Core processing)."""
        storyboard = ctx.storyboard
        config = ctx.config
        
        is_cloud_workflow = False
        if is_cloud_workflow:
            logger.info("Using parallel processing for cloud workflows")
            
            semaphore = asyncio.Semaphore(1)
            completed_count = 0
            
            async def process_frame_with_semaphore(i: int, frame: StoryboardFrame):
                nonlocal completed_count
                async with semaphore:
                    base_progress = 0.2
                    frame_range = 0.6
                    per_frame_progress = frame_range / len(storyboard.frames)
                    
                    # Create frame-specific progress callback
                    def frame_progress_callback(event: ProgressEvent):
                        overall_progress = base_progress + (per_frame_progress * completed_count) + (per_frame_progress * event.progress)
                        if ctx.progress_callback:
                            adjusted_event = ProgressEvent(
                                event_type=event.event_type,
                                progress=overall_progress,
                                frame_current=i+1,
                                frame_total=len(storyboard.frames),
                                step=event.step,
                                action=event.action
                            )
                            ctx.progress_callback(adjusted_event)
                    
                    # Report frame start
                    self._report_progress(
                        ctx.progress_callback,
                        "processing_frame",
                        base_progress + (per_frame_progress * completed_count),
                        frame_current=i+1,
                        frame_total=len(storyboard.frames)
                    )
                    
                    processed_frame = await self.core.frame_processor(
                        frame=frame,
                        storyboard=storyboard,
                        config=config,
                        total_frames=len(storyboard.frames),
                        progress_callback=frame_progress_callback
                    )
                    
                    completed_count += 1
                    logger.info(f"✅ Frame {i+1} completed ({processed_frame.duration:.2f}s) [{completed_count}/{len(storyboard.frames)}]")
                    return i, processed_frame
            
            # Create all tasks and execute in parallel
            tasks = [process_frame_with_semaphore(i, frame) for i, frame in enumerate(storyboard.frames)]
            results = await asyncio.gather(*tasks)
            
            # Update frames in order and calculate total duration
            for idx, processed_frame in sorted(results, key=lambda x: x[0]):
                storyboard.frames[idx] = processed_frame
                storyboard.total_duration += processed_frame.duration
            
            logger.info(f"✅ All frames processed in parallel (total duration: {storyboard.total_duration:.2f}s)")
        else:
            # Serial processing for non-Selfhost workflows
            logger.info("⚙️ Using serial processing (non-Selfhost workflow)")
            
            for i, frame in enumerate(storyboard.frames):
                base_progress = 0.2
                frame_range = 0.6
                per_frame_progress = frame_range / len(storyboard.frames)
                
                # Create frame-specific progress callback
                def frame_progress_callback(event: ProgressEvent):
                    overall_progress = base_progress + (per_frame_progress * i) + (per_frame_progress * event.progress)
                    if ctx.progress_callback:
                        adjusted_event = ProgressEvent(
                            event_type=event.event_type,
                            progress=overall_progress,
                            frame_current=event.frame_current,
                            frame_total=event.frame_total,
                            step=event.step,
                            action=event.action
                        )
                        ctx.progress_callback(adjusted_event)
                
                # Report frame start
                self._report_progress(
                    ctx.progress_callback,
                    "processing_frame",
                    base_progress + (per_frame_progress * i),
                    frame_current=i+1,
                    frame_total=len(storyboard.frames)
                )
                
                processed_frame = await self.core.frame_processor(
                    frame=frame,
                    storyboard=storyboard,
                    config=config,
                    total_frames=len(storyboard.frames),
                    progress_callback=frame_progress_callback
                )
                storyboard.total_duration += processed_frame.duration
                logger.info(f"✅ Frame {i+1} completed ({processed_frame.duration:.2f}s)")

    async def post_production(self, ctx: PipelineContext):
        """Step 7: Concatenate videos and add BGM."""
        self._report_progress(ctx.progress_callback, "concatenating", 0.85)
        
        storyboard = ctx.storyboard
        segment_paths = [frame.video_segment_path for frame in storyboard.frames]
        
        video_service = VideoService()
        
        final_video_path = video_service.concat_videos(
            videos=segment_paths,
            output=ctx.final_video_path,
            audio_tracks=[frame.audio_path for frame in storyboard.frames],
            transition=ctx.params.get("transition_mode", "none"),
            transition_choices=ctx.params.get("transition_choices"),
            transition_duration=ctx.params.get("transition_duration", 0.5),
            bgm_path=ctx.params.get("bgm_path"),
            bgm_volume=ctx.params.get("bgm_volume", 0.2),
            bgm_mode=ctx.params.get("bgm_mode", "loop")
        )
        
        storyboard.final_video_path = final_video_path
        storyboard.completed_at = datetime.now()

        # Copy to user-specified path if provided
        user_specified_output = ctx.params.get("output_path")
        if user_specified_output:
            Path(user_specified_output).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_video_path, user_specified_output)
            logger.info(f"📹 Final video copied to: {user_specified_output}")
            ctx.final_video_path = user_specified_output

        # SRT subtitles next to the final video, for manual platform uploads
        try:
            srt_path = str(Path(ctx.final_video_path).with_suffix(".srt"))
            export_srt(
                [(frame.narration, frame.duration) for frame in storyboard.frames],
                srt_path,
            )
            logger.info(f"📝 Subtitles exported: {srt_path}")
        except Exception as exc:
            logger.warning(f"SRT 字幕导出失败（不影响交付）: {exc}")

        # QA gate: warn loudly on broken output (never blocks delivery)
        self._report_progress(ctx.progress_callback, "quality_check", 0.95)
        try:
            qa_report = await asyncio.to_thread(
                inspect_final_video,
                ctx.final_video_path,
                expected_duration_seconds=storyboard.total_duration,
            )
            ctx.qa_warnings = list(qa_report.warnings)
        except Exception as exc:
            logger.warning(f"成片自检未能完成（不影响交付）: {exc}")
            ctx.qa_warnings = []
            storyboard.final_video_path = user_specified_output
        
        logger.success(f"🎬 Video generation completed: {ctx.final_video_path}")

    async def finalize(self, ctx: PipelineContext) -> VideoGenerationResult:
        """Step 8: Create result object and persist metadata."""
        self._report_progress(ctx.progress_callback, "completed", 1.0)
        
        video_path_obj = Path(ctx.final_video_path)
        file_size = video_path_obj.stat().st_size
        
        result = VideoGenerationResult(
            video_path=ctx.final_video_path,
            storyboard=ctx.storyboard,
            duration=ctx.storyboard.total_duration,
            file_size=file_size,
            qa_warnings=list(getattr(ctx, "qa_warnings", []) or []),
        )
        
        ctx.result = result
        
        logger.info(f"✅ Generated video: {ctx.final_video_path}")
        logger.info(f"   Duration: {ctx.storyboard.total_duration:.2f}s")
        logger.info(f"   Size: {file_size / (1024*1024):.2f} MB")
        logger.info(f"   Frames: {len(ctx.storyboard.frames)}")
        
        # Persist metadata
        await self._persist_task_data(ctx)
        
        return result

    async def _persist_task_data(self, ctx: PipelineContext):
        """
        Persist task metadata and storyboard to filesystem
        """
        try:
            storyboard = ctx.storyboard
            result = ctx.result
            task_id = storyboard.config.task_id
            
            if not task_id:
                logger.warning("No task_id in storyboard, skipping persistence")
                return
            
            # Build metadata
            input_with_title = ctx.params.copy()
            input_with_title["text"] = ctx.input_text # Ensure text is included
            if not input_with_title.get("title"):
                input_with_title["title"] = storyboard.title
            
            metadata = {
                "task_id": task_id,
                "created_at": storyboard.created_at.isoformat() if storyboard.created_at else None,
                "completed_at": storyboard.completed_at.isoformat() if storyboard.completed_at else None,
                "status": "completed",
                
                "input": input_with_title,
                
                "result": {
                    "video_path": result.video_path,
                    "duration": result.duration,
                    "file_size": result.file_size,
                    "n_frames": len(storyboard.frames)
                },
                
                "config": {
                    "llm_model": self.core.config.get("llm", {}).get("model", "unknown"),
                    "llm_base_url": self.core.config.get("llm", {}).get("base_url", "unknown"),
                    "comfyui_url": self.core.config.get("comfyui", {}).get("comfyui_url", "unknown"),
                    "selfhost_enabled": bool(self.core.config.get("comfyui", {}).get("selfhost_api_key")),
                }
            }
            
            # Save metadata
            await self.core.persistence.save_task_metadata(task_id, metadata)
            logger.info(f"💾 Saved task metadata: {task_id}")
            
            # Save storyboard
            await self.core.persistence.save_storyboard(task_id, storyboard)
            logger.info(f"💾 Saved storyboard: {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to persist task data: {e}")
            # Don't raise - persistence failure shouldn't break video generation
