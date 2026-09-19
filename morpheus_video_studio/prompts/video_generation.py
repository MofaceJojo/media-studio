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
Video prompt generation template

For generating video prompts from narrations.
"""

import json
from typing import List

from morpheus_video_studio.utils.visual_prompt_policy import build_visual_rules


VIDEO_PROMPT_GENERATION_PROMPT = """# Role Definition
You are a professional video creative designer, skilled at creating dynamic, grounded video generation prompts for video scripts, transforming narrative content into vivid video scenes.

# Core Task
Based on the existing video script, create corresponding **English** video generation prompts for each storyboard's "narration content", ensuring video scenes perfectly match the narrative content and enhance audience understanding and memory through dynamic visuals.

**Important: The input contains {narrations_count} narrations. You must generate one corresponding video prompt for each narration, totaling {narrations_count} video prompts.**

# Input Content
{narrations_json}

# Output Requirements

## Video Prompt Specifications
- Language: **Must use English** (for AI video generation models)
- Description structure: scene + observable action + camera movement + concrete evidence
- Description length: Ensure clear, complete, and creative descriptions (recommended 50-100 English words)
- Dynamic elements: Emphasize actions, movements, changes, and other dynamic effects

## Visual Creative Requirements
- Each video must accurately reflect the specific content and emotion of the corresponding narration
- Highlight visual dynamics: character actions, object movements, camera movements, scene transitions, etc.
- Use the objects, environments, and observable evidence supplied by the narration
- Avoid filler scenes unrelated to the narration
- Enhance expressiveness through camera language (push, pull, pan, tilt) and editing rhythm

## Key English Vocabulary Reference
- Actions: moving, running, flowing, transforming, growing, falling
- Camera: camera pan, zoom in, zoom out, tracking shot, aerial view
- Transitions: transition, fade in, fade out, dissolve
- Atmosphere: dynamic, energetic, peaceful, dramatic, mysterious
- Lighting: lighting changes, shadows moving, sunlight streaming

## Video and Copy Coordination Principles
- Videos should serve the copy, becoming a visual extension of the copy content
- Avoid visual elements unrelated to or contradicting the copy content
- Choose dynamic presentation methods that best enhance the persuasiveness of the copy
- Ensure the audience can quickly understand the core viewpoint of the copy through video dynamics

## Creative Guidance
1. **Phenomenon Description Copy**: Show the specific setting or object named by the narration
2. **Cause Analysis Copy**: Show the observable cause and result named by the narration
3. **Impact Argumentation Copy**: Show the stated consequence or evidence
4. **In-depth Discussion Copy**: Stay with concrete facts instead of filler
5. **Conclusion Inspiration Copy**: Keep the named subject and setting clear

## Video-Specific Considerations
- Emphasize dynamics: Each video should include obvious actions or movements
- Camera language: Appropriately use camera techniques such as push, pull, pan, tilt to enhance expressiveness
- Duration consideration: Videos should be a coherent dynamic process, not static images
- Fluidity: Pay attention to the fluidity and naturalness of actions

# Output Format
Strictly output in the following JSON format, **video prompts must be in English**:

```json
{{
  "video_prompts": [
    "[detailed English video prompt with dynamic elements and camera movements]",
    "[detailed English video prompt with dynamic elements and camera movements]"
  ]
}}
```

# Important Reminders
1. Only output JSON format content, do not add any explanations
2. Ensure JSON format is strictly correct and can be directly parsed by the program
3. Input is {{"narrations": [narration array]}} format, output is {{"video_prompts": [video prompt array]}} format
4. **The output video_prompts array must contain exactly {narrations_count} elements, corresponding one-to-one with the input narrations array**
5. **Video prompts must use English** (for AI video generation models)
6. Video prompts must accurately reflect the specific content and emotion of the corresponding narration
7. Each video must emphasize dynamics and sense of movement, avoid static descriptions
8. Appropriately use camera language to enhance expressiveness
9. Ensure video scenes can enhance the persuasiveness of the copy and audience understanding

Now, please create {narrations_count} corresponding **English** video prompts for the above {narrations_count} narrations. Only output JSON, no other content.
"""


def build_video_prompt_prompt(
    narrations: List[str],
    min_words: int,
    max_words: int,
    visual_rules: str = "",
) -> str:
    """
    Build video prompt generation prompt
    
    Args:
        narrations: List of narrations
        min_words: Minimum word count
        max_words: Maximum word count
    
    Returns:
        Formatted prompt for LLM
    
    Example:
        >>> build_video_prompt_prompt(narrations, 50, 100)
    """
    narrations_json = json.dumps(
        {"narrations": narrations},
        ensure_ascii=False,
        indent=2
    )
    
    return f"\n{build_visual_rules(visual_rules)}\n" + VIDEO_PROMPT_GENERATION_PROMPT.format(
        narrations_json=narrations_json,
        narrations_count=len(narrations),
        min_words=min_words,
        max_words=max_words
    )
