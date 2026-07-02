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
Content generation API schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Narration Generation
# ============================================================================

class NarrationGenerateRequest(BaseModel):
    """Narration generation request"""
    text: str = Field(..., description="Source text to generate narrations from")
    n_scenes: int = Field(5, ge=1, le=20, description="Number of scenes")
    min_words: int = Field(5, ge=1, le=100, description="Minimum words per narration")
    max_words: int = Field(20, ge=1, le=200, description="Maximum words per narration")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Atomic Habits is about making small changes that lead to remarkable results.",
                "n_scenes": 5,
                "min_words": 5,
                "max_words": 20
            }
        }


class NarrationGenerateResponse(BaseModel):
    """Narration generation response"""
    success: bool = True
    message: str = "Success"
    narrations: List[str] = Field(..., description="Generated narrations")


# ============================================================================
# Image Prompt Generation
# ============================================================================

class ImagePromptGenerateRequest(BaseModel):
    """Image prompt generation request"""
    narrations: List[str] = Field(..., description="List of narrations")
    min_words: int = Field(30, ge=10, le=100, description="Minimum words per prompt")
    max_words: int = Field(60, ge=10, le=200, description="Maximum words per prompt")
    
    class Config:
        json_schema_extra = {
            "example": {
                "narrations": [
                    "Small habits compound over time",
                    "Focus on systems, not goals"
                ],
                "min_words": 30,
                "max_words": 60
            }
        }


class ImagePromptGenerateResponse(BaseModel):
    """Image prompt generation response"""
    success: bool = True
    message: str = "Success"
    image_prompts: List[str] = Field(..., description="Generated image prompts")


# ============================================================================
# Seedance Script Generation
# ============================================================================

class SeedanceAssetReference(BaseModel):
    """Seedance multimodal asset reference"""
    type: str = Field("image", description="Asset type: image, video, or audio")
    label: str = Field(..., description="Human-readable asset label or path")
    role: str = Field("reference material", description="Intended role in Seedance prompt")
    reference: Optional[str] = Field(None, description="Optional explicit @ reference")


class SeedanceScriptGenerateRequest(BaseModel):
    """Seedance script generation request"""
    brief: str = Field(..., description="Creative brief or source concept")
    duration_seconds: int = Field(10, ge=4, le=15, description="Seedance video duration")
    assets: List[SeedanceAssetReference] = Field(default_factory=list, description="Optional assets")
    language: str = Field("auto", description="Output language hint")
    scenario: str = Field("general", description="Scenario hint")
    aspect_ratio: str = Field("9:16", description="Target aspect ratio")

    class Config:
        json_schema_extra = {
            "example": {
                "brief": "为一款冷萃咖啡生成 10 秒竖屏广告",
                "duration_seconds": 10,
                "assets": [
                    {"type": "image", "label": "coffee bottle hero image", "role": "product appearance"}
                ],
                "language": "zh",
                "scenario": "ecommerce_ad",
                "aspect_ratio": "9:16",
            }
        }


class SeedanceScriptGenerateResponse(BaseModel):
    """Seedance script generation response"""
    success: bool = True
    message: str = "Success"
    script: dict = Field(..., description="Generated Seedance-ready script payload")


# ============================================================================
# Title Generation
# ============================================================================

class TitleGenerateRequest(BaseModel):
    """Title generation request"""
    text: str = Field(..., description="Source text")
    style: Optional[str] = Field(None, description="Title style (e.g., 'engaging', 'formal')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Atomic Habits is about making small changes that lead to remarkable results.",
                "style": "engaging"
            }
        }


class TitleGenerateResponse(BaseModel):
    """Title generation response"""
    success: bool = True
    message: str = "Success"
    title: str = Field(..., description="Generated title")
