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

"""Ken Burns / drift motion presets for image- and video-backed segments."""

import hashlib
import os
import random
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Literal, Optional

import ffmpeg
from loguru import logger


class MotionPresetMixin:
    """Deterministic motion preset selection and application."""

    def _apply_video_motion(
        self,
        stream,
        width: int,
        height: int,
        source_id: str,
        motion_mode: str = "none",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ):
        """Apply a subtle camera move to video clips so effect settings also affect video media."""
        preset = self._pick_video_motion_preset(
            source_id,
            motion_mode=motion_mode,
            motion_choices=motion_choices,
            motion_seed=motion_seed,
        )
        if preset["scale"] <= 1.0:
            return stream

        scaled_width = max(2, int(width * preset["scale"]) // 2 * 2)
        scaled_height = max(2, int(height * preset["scale"]) // 2 * 2)

        return (
            stream
            .filter("scale", scaled_width, scaled_height)
            .filter(
                "crop",
                width,
                height,
                preset["x_expr"],
                preset["y_expr"],
            )
        )

    def _pick_video_motion_preset(
        self,
        source_id: str,
        motion_mode: str = "none",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ) -> dict:
        """Resolve video motion presets using the same mode names as image motion."""
        valid_modes = {"none", "gentle", "float", "cinematic"}
        filtered_choices = [item for item in (motion_choices or []) if item in valid_modes and item != "none"]
        if motion_mode == "random" and filtered_choices:
            seed_source = f"{source_id}|video|{motion_seed}|{'|'.join(filtered_choices)}"
            seed = int(hashlib.md5(seed_source.encode("utf-8")).hexdigest()[:8], 16)
            motion_mode = filtered_choices[seed % len(filtered_choices)]
        elif motion_mode == "sequence" and filtered_choices:
            motion_mode = filtered_choices[motion_seed % len(filtered_choices)]
        elif motion_mode not in valid_modes:
            motion_mode = "float"

        if motion_mode == "none":
            return {
                "name": "static",
                "scale": 1.0,
                "x_expr": "(in_w-out_w)/2",
                "y_expr": "(in_h-out_h)/2",
            }

        range_x = "(in_w-out_w)"
        range_y = "(in_h-out_h)"
        presets_by_mode = {
            "gentle": [
                {
                    "name": "gentle-drift",
                    "scale": 1.05,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.10*sin(t/3.4)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.08*cos(t/3.9)",
                },
                {
                    "name": "gentle-rise",
                    "scale": 1.06,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.08*cos(t/3.2)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.12*sin(t/4.1)",
                },
            ],
            "float": [
                {
                    "name": "float-wide",
                    "scale": 1.10,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.18*sin(t/2.8)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.12*cos(t/3.3)",
                },
                {
                    "name": "float-diagonal",
                    "scale": 1.11,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.16*cos(t/2.5)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.14*sin(t/3.0)",
                },
            ],
            "cinematic": [
                {
                    "name": "cinematic-push",
                    "scale": 1.14,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.22*sin(t/2.4)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.16*cos(t/2.9)",
                },
                {
                    "name": "cinematic-sweep",
                    "scale": 1.16,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.24*cos(t/2.2)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.18*sin(t/2.7)",
                },
            ],
        }
        presets = presets_by_mode.get(motion_mode, presets_by_mode["float"])
        seed = int(hashlib.md5(f"{source_id}|video-motion".encode("utf-8")).hexdigest()[:8], 16)
        return presets[(seed + motion_seed) % len(presets)]
    

    def _pick_image_motion_preset(
        self,
        image_path: str,
        motion_mode: str = "float",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ) -> dict:
        """
        Deterministically vary Ken Burns motion so image segments feel alive.
        """
        valid_modes = {"none", "gentle", "float", "cinematic"}
        filtered_choices = [item for item in (motion_choices or []) if item in valid_modes and item != "none"]
        if motion_mode == "random" and filtered_choices:
            seed_source = f"{image_path}|{motion_seed}|{'|'.join(filtered_choices)}"
            seed = int(hashlib.md5(seed_source.encode("utf-8")).hexdigest()[:8], 16)
            motion_mode = filtered_choices[seed % len(filtered_choices)]
        elif motion_mode == "sequence" and filtered_choices:
            motion_mode = filtered_choices[motion_seed % len(filtered_choices)]
        elif motion_mode not in valid_modes:
            motion_mode = "float"

        if motion_mode == "none":
            return {
                "name": "static",
                "zoom_expr": "1",
                "x_expr": "iw/2-(iw/zoom/2)",
                "y_expr": "ih/2-(ih/zoom/2)",
            }

        seed = int(hashlib.md5(image_path.encode("utf-8")).hexdigest()[:8], 16)
        if motion_mode == "gentle":
            presets = [
                {
                    "name": "gentle-zoom-in",
                    "zoom_expr": "min(zoom+0.0012,1.16)",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
                {
                    "name": "gentle-drift-right",
                    "zoom_expr": "min(zoom+0.0011,1.14)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.12*sin(on/42)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.05*cos(on/54)",
                },
                {
                    "name": "gentle-drift-up",
                    "zoom_expr": "min(zoom+0.0011,1.14)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.05*sin(on/50)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.12*cos(on/40)",
                },
                {
                    "name": "gentle-zoom-out",
                    "zoom_expr": "if(eq(on,1),1.16,max(zoom-0.0010,1.03))",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
            ]
        elif motion_mode == "cinematic":
            presets = [
                {
                    "name": "cinematic-zoom-in",
                    "zoom_expr": "min(zoom+0.0018,1.28)",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
                {
                    "name": "cinematic-drift-right",
                    "zoom_expr": "min(zoom+0.0016,1.24)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.22*sin(on/32)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.08*cos(on/44)",
                },
                {
                    "name": "cinematic-drift-up",
                    "zoom_expr": "min(zoom+0.0016,1.24)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.08*sin(on/46)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.22*cos(on/30)",
                },
                {
                    "name": "cinematic-zoom-out",
                    "zoom_expr": "if(eq(on,1),1.26,max(zoom-0.0014,1.04))",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
            ]
        else:
            presets = [
                {
                    "name": "float-zoom-in",
                    "zoom_expr": "min(zoom+0.0014,1.20)",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
                {
                    "name": "float-drift-right",
                    "zoom_expr": "min(zoom+0.0013,1.19)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.18*sin(on/34)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.07*cos(on/46)",
                },
                {
                    "name": "float-drift-up",
                    "zoom_expr": "min(zoom+0.0013,1.19)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.07*sin(on/44)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.18*cos(on/34)",
                },
                {
                    "name": "float-zoom-out",
                    "zoom_expr": "if(eq(on,1),1.20,max(zoom-0.0012,1.04))",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
            ]
        return presets[seed % len(presets)]
    
