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
Content generation utility functions

Pure/stateless functions for generating content using LLM.
These functions are reusable across different pipelines.
"""

import json
import math
import re
from typing import List, Literal, Optional

from loguru import logger

from morpheus_video_studio.utils.visual_prompt_policy import sanitize_visual_prompt

# Human-referencing terms that make local SD1.5 render distorted people.
# Used as a hard scrub on image prompts when a recipe forbids human figures —
# the LLM instruction isn't always obeyed, so this is the last line of defence.
_HUMAN_TERMS = re.compile(
    r"\b(person|people|human|man|woman|men|women|male|female|boy|girl|child|children|"
    r"elderly|old man|old woman|patient|doctor|physician|figure|portrait|hand|hands|"
    r"face|faces|body|worker|farmer|practitioner|monk|scholar)\b",
    re.IGNORECASE,
)
_HUMAN_TERMS_CN = re.compile(
    r"人物|人体|人影|人脸|医生|大夫|患者|病人|老人|妇女|男人|女人|孩子|手部|双手|"
    r"农民|药师|采药人|老中医|人[，。、]"
)
_SCREEN_RANKING_TOPIC_TERMS = ("影视", "电影", "电视剧", "剧集", "动画", "动漫", "番剧")
_SCREEN_RANKING_EPISODE_PATTERN = re.compile(r"(?:\d+|[一二三四五六七八九十百千万两]+)集")
_SCREEN_RANKING_WORK_PATTERN = re.compile(
    r"(?:\d+|[一二三四五六七八九十百千万两]+)\s*(?:部|季|话)"
)
_SCREEN_RANKING_CATEGORY_TARGET_PATTERN = re.compile(
    rf"(?:{'|'.join(map(re.escape, _SCREEN_RANKING_TOPIC_TERMS))})"
    r"(?:盘点|排行(?:榜)?|榜单|推荐)$|"
    r"(?:盘点|排行(?:榜)?|榜单|推荐).{0,12}"
    rf"(?:{'|'.join(map(re.escape, _SCREEN_RANKING_TOPIC_TERMS))})$"
)
_SCREEN_RANKING_FIELDS = (
    "narration",
    "item_name",
    "character",
    "situation",
    "action_or_conflict",
    "selection_reason",
)
_SCREEN_JUDGE_BOOLEAN_FIELDS = (
    "identifiable_character",
    "external_situation",
    "observable_action_or_conflict_with_object_or_result",
    "event_supported_reason",
)


def scrub_human_terms(prompt: str) -> str:
    """Strip human references from an image prompt (both EN and CN).

    Belt-and-braces for the no-human recipes: even when the LLM leaks a person
    into the prompt, this removes it before it reaches ComfyUI. Cleans up the
    dangling punctuation/connectors left behind.
    """
    if not prompt:
        return prompt
    prompt = _HUMAN_TERMS_CN.sub("", prompt)
    prompt = _HUMAN_TERMS.sub("", prompt)
    prompt = re.sub(r"\b(a|an|the|of|with|and|by)\s+(,|\.|and|with)", r"\2", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"\s*,\s*,+", ", ", prompt)
    prompt = re.sub(r"\s{2,}", " ", prompt)
    return prompt.strip(" ,，、").strip()


def clean_narration(text: str) -> str:
    """Normalize one narration segment into a single spoken line.

    A segment is one continuous sentence, so it must not carry line breaks.
    Free LLMs leak two kinds that end up printed on the subtitle as the raw
    characters '\\n': real newlines/tabs, and the literal backslash-n / -t / -r
    sequences produced when a model double-escapes its JSON. Collapse both to
    spaces and squeeze whitespace.
    """
    if not text:
        return ""
    text = re.sub(r"\\[nrt]", " ", text)      # literal backslash-n / -r / -t
    text = re.sub(r"[\n\r\t]+", " ", text)     # real control chars
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _spoken_unit_count(text: str) -> int:
    """Count Chinese characters for CJK copy, otherwise count words."""
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text or ""))
    if cjk_count:
        return cjk_count
    return len(re.findall(r"\b\w+\b", text or "", flags=re.UNICODE))


def _has_short_narration(narrations: List[str], min_words: int) -> bool:
    return any(_spoken_unit_count(item) < min_words for item in narrations)


def _ranking_narrations_are_structured(narrations: List[str]) -> bool:
    for index, narration in enumerate(narrations, start=1):
        prefix = f"第{index}项："
        if not narration.startswith(prefix) or "｜" not in narration[len(prefix):]:
            return False
        name, detail = narration[len(prefix):].split("｜", 1)
        if len(name.strip()) < 2 or len(detail.strip()) < 4:
            return False
    return True


def _is_screen_ranking_topic(topic: str) -> bool:
    return bool(
        _SCREEN_RANKING_EPISODE_PATTERN.search(topic)
        or _SCREEN_RANKING_WORK_PATTERN.search(topic)
        or _SCREEN_RANKING_CATEGORY_TARGET_PATTERN.search(topic.strip())
    )


def _build_screen_ranking_judge_prompt(
    narrations: List[str],
    evidence_items: list[dict[str, str]] | None,
) -> str:
    items = []
    for index, narration in enumerate(narrations, start=1):
        item: dict[str, object] = {"index": index, "narration": narration}
        if evidence_items is not None and index <= len(evidence_items):
            item["structured_evidence"] = {
                field: evidence_items[index - 1][field]
                for field in _SCREEN_RANKING_FIELDS
                if field != "narration"
            }
        items.append(item)

    payload = json.dumps({"items": items}, ensure_ascii=False, indent=2)
    return f"""# 影视盘点语义判定

你是严格的短视频分镜语义审查器。一次性审查下面全部条目，只依据提供的旁白和结构字段判断，不检索资料，也不判断剧情是否真实。

每一项必须分别给出以下四个布尔值：
- identifiable_character：出现可识别的具体人物，而不是“某人、主角、有人”或单纯代词。
- external_situation：交代人物所处的外部情境、限制、地点或事件前提；只有天气、景色或情绪氛围不构成完整剧情事件。
- observable_action_or_conflict_with_object_or_result：写出镜头可以直接呈现的行动或冲突，并明确行动对象、对手或可见结果。
- event_supported_reason：入选理由由上述具体行动、冲突或结果直接支撑，而不是抽象赞美或主题感悟。

判定边界：
- “小新选择把唯一的雨伞递给风间”包含可观察动作、对象和结果，“选择”在这里不应导致拒绝。
- “小新追寻梦想的方向”“寻找内心的成长”是抽象目标，不是镜头可见的具体事件。
- “雨夜里的街道格外寂静”只有天气与氛围，不包含人物行动或剧情冲突。

输入：
{payload}

只输出严格 JSON，不得包含 Markdown 或说明文字。items 数量和 index 必须与输入完全一致。每项只允许以下字段：index、identifiable_character、external_situation、observable_action_or_conflict_with_object_or_result、event_supported_reason、issues。issues 必须是字符串数组；任一布尔值为 false 时必须说明原因，全部为 true 时输出空数组。

输出示例：
{{"items":[{{"index":1,"identifiable_character":true,"external_situation":true,"observable_action_or_conflict_with_object_or_result":true,"event_supported_reason":true,"issues":[]}}]}}
"""


def _parse_screen_ranking_judge_response(
    response: str,
    expected_count: int,
) -> tuple[bool, list[str]]:
    if not isinstance(response, str) or not response.strip():
        raise ValueError("空响应")
    result = json.loads(response)
    if not isinstance(result, dict) or set(result) != {"items"}:
        raise ValueError("根对象必须且只能包含 items")
    items = result["items"]
    if not isinstance(items, list) or len(items) != expected_count:
        raise ValueError(
            f"items 数量不匹配：需要 {expected_count} 条，实际 "
            f"{len(items) if isinstance(items, list) else '非数组'}"
        )

    expected_fields = {"index", *_SCREEN_JUDGE_BOOLEAN_FIELDS, "issues"}
    accepted = True
    collected_issues: list[str] = []
    for expected_index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise ValueError(f"第 {expected_index} 项字段不完整或包含额外字段")
        if type(item["index"]) is not int or item["index"] != expected_index:
            raise ValueError(f"第 {expected_index} 项 index 无效")
        if any(type(item[field]) is not bool for field in _SCREEN_JUDGE_BOOLEAN_FIELDS):
            raise ValueError(f"第 {expected_index} 项布尔字段类型无效")
        issues = item["issues"]
        if not isinstance(issues, list) or any(
            not isinstance(issue, str) or not issue.strip() for issue in issues
        ):
            raise ValueError(f"第 {expected_index} 项 issues 必须是字符串数组")

        item_accepted = all(item[field] for field in _SCREEN_JUDGE_BOOLEAN_FIELDS)
        if not item_accepted and not issues:
            raise ValueError(f"第 {expected_index} 项未通过但没有 issues")
        if item_accepted and issues:
            raise ValueError(f"第 {expected_index} 项已通过但 issues 不为空")
        accepted = accepted and item_accepted
        collected_issues.extend(
            f"第{expected_index}项：{issue.strip()}" for issue in issues
        )
    return accepted, collected_issues


async def _judge_screen_ranking_narrations(
    llm_service,
    narrations: List[str],
    evidence_items: list[dict[str, str]] | None,
) -> tuple[bool, list[str], bool]:
    prompt = _build_screen_ranking_judge_prompt(narrations, evidence_items)
    try:
        response = await llm_service(
            prompt=prompt,
            temperature=0,
            max_tokens=3000,
        )
        accepted, issues = _parse_screen_ranking_judge_response(
            response, len(narrations)
        )
    except Exception as exc:
        logger.warning(f"Screen-ranking semantic judge response invalid: {exc}")
        return False, [str(exc)], True
    return accepted, issues, False


def _parse_topic_narration_result(
    result: dict,
    *,
    allow_structured_screen_ranking: bool,
    response_label: str,
) -> tuple[List[str], list[dict[str, str]] | None]:
    if "narrations" not in result:
        raise ValueError(
            f"Invalid {response_label}response format: missing 'narrations' key"
        )
    raw_narrations = result["narrations"]
    if not isinstance(raw_narrations, list):
        raise ValueError(
            f"Invalid {response_label}response format: 'narrations' must be an array"
        )
    if all(isinstance(item, str) for item in raw_narrations):
        return [clean_narration(item) for item in raw_narrations], None
    if not allow_structured_screen_ranking or not all(
        isinstance(item, dict) for item in raw_narrations
    ):
        raise ValueError(
            f"Invalid {response_label}response format: narration items have mixed or unsupported types"
        )

    evidence_items: list[dict[str, str]] = []
    for item in raw_narrations:
        normalized: dict[str, str] = {}
        for field in _SCREEN_RANKING_FIELDS:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Invalid {response_label}response format: missing screen-ranking field '{field}'"
                )
            normalized[field] = clean_narration(value)
        evidence_items.append(normalized)

    return [item["narration"] for item in evidence_items], evidence_items


async def generate_title(
    llm_service,
    content: str,
    strategy: Literal["auto", "direct", "llm"] = "auto",
    max_length: int = 15
) -> str:
    """
    Generate title from content
    
    Args:
        llm_service: LLM service instance
        content: Source content (topic or script)
        strategy: Generation strategy
            - "auto": Auto-decide based on content length (default)
            - "direct": Use content directly (truncated if needed)
            - "llm": Always use LLM to generate title
        max_length: Maximum title length (default: 15)
    
    Returns:
        Generated title
    """
    if strategy == "direct":
        content = content.strip()
        return content[:max_length] if len(content) > max_length else content
    
    if strategy == "auto":
        if len(content.strip()) <= 15:
            return content.strip()
        # Fall through to LLM
    
    # Use LLM to generate title
    from morpheus_video_studio.prompts import build_title_generation_prompt
    
    # Pass max_length to prompt so LLM knows the character limit
    prompt = build_title_generation_prompt(content, max_length=max_length)
    response = await llm_service(prompt, temperature=0.7, max_tokens=50)
    
    # Clean up response
    title = response.strip()
    
    # Remove quotes if present
    if title.startswith('"') and title.endswith('"'):
        title = title[1:-1]
    if title.startswith("'") and title.endswith("'"):
        title = title[1:-1]
    
    # Remove trailing punctuation
    title = title.rstrip('.,!?;:\'"')

    # Language guard: free LLMs sometimes ignore the "match the input
    # language" instruction and return an English title for Chinese content
    # (the "We need to" bug). If the content is Chinese but the title has no
    # Chinese at all, the title is wrong — fall back to the content itself.
    def _has_cjk(text: str) -> bool:
        return any('一' <= ch <= '鿿' for ch in text)

    if _has_cjk(content) and not _has_cjk(title):
        fallback = content.strip().split("\n")[0].strip()
        title = fallback[:max_length].rstrip('.,!?;:\'"，。！？、')
        logger.warning(f"Title language mismatch, fell back to content: '{title}'")
        return title

    # Safety: if still over limit, truncate smartly
    if len(title) > max_length:
        # Try to truncate at word boundary
        truncated = title[:max_length]
        last_space = truncated.rfind(' ')
        
        # Only use word boundary if it's not too far back (at least 60% of max_length)
        if last_space > max_length * 0.6:
            title = truncated[:last_space]
        else:
            title = truncated
        
        # Remove any trailing punctuation after truncation
        title = title.rstrip('.,!?;:\'"')
    
    logger.debug(f"Generated title: '{title}' (length: {len(title)})")
    return title


async def generate_narrations_from_topic(
    llm_service,
    topic: str,
    n_scenes: int = 5,
    min_words: int = 5,
    max_words: int = 20,
    content_recipe: Optional[str] = None,
    strict_count: bool = False,
) -> List[str]:
    """
    Generate narrations from topic using LLM
    
    Args:
        llm_service: LLM service instance
        topic: Topic/theme to generate narrations from
        n_scenes: Number of narrations to generate
        min_words: Minimum narration length
        max_words: Maximum narration length
        strict_count: Reject excess results instead of preserving legacy truncation
    
    Returns:
        List of narration texts
    """
    from morpheus_video_studio.prompts import build_topic_narration_prompt
    from morpheus_video_studio.prompts.content_recipes import get_recipe_block

    logger.info(
        f"Generating {n_scenes} narrations from topic: {topic}"
        + (f" (recipe: {content_recipe})" if content_recipe else "")
    )
    screen_ranking = content_recipe == "ranking" and _is_screen_ranking_topic(topic)

    prompt = build_topic_narration_prompt(
        topic=topic,
        n_storyboard=n_scenes,
        min_words=min_words,
        max_words=max_words,
        recipe_block=get_recipe_block(content_recipe),
        structured_screen_ranking=screen_ranking,
    )
    
    response = await llm_service(
        prompt=prompt,
        temperature=0.8,
        max_tokens=6000
    )
    
    logger.debug(f"LLM response: {response[:200]}...")
    
    # Parse JSON
    result = _parse_json(response)
    
    narrations, screen_evidence = _parse_topic_narration_result(
        result,
        allow_structured_screen_ranking=screen_ranking,
        response_label="",
    )
    screen_judge_accepted = True
    screen_judge_issues: list[str] = []
    screen_judge_invalid = False
    if screen_ranking:
        (
            screen_judge_accepted,
            screen_judge_issues,
            screen_judge_invalid,
        ) = await _judge_screen_ranking_narrations(
            llm_service, narrations, screen_evidence
        )

    too_short = _has_short_narration(narrations, min_words)
    ranking_unstructured = (
        content_recipe == "ranking" and not _ranking_narrations_are_structured(narrations)
    )
    if too_short or ranking_unstructured or not screen_judge_accepted:
        problems = []
        if too_short:
            problems.append("部分文案过短")
        if ranking_unstructured:
            problems.append("盘点文案缺少明确条目、名称或具体介绍")
        if screen_judge_invalid:
            problems.append("影视盘点语义校验响应无效")
        elif not screen_judge_accepted:
            problems.append("影视盘点缺少可观察的具体人物、情境、行动或入选依据")
        problems.extend(screen_judge_issues)
        problem_text = "，".join(problems)
        logger.warning(f"Generated narration needs rewrite: {problem_text}")
        retry_prompt = (
            f"{prompt}\n\n"
            f"上一次返回存在问题：{problem_text}。请全部重新写一遍，每段都要补充具体情节、细节或解释，"
            f"中文每段不得少于 {min_words} 个汉字，并仍按上面的 JSON 格式输出 {n_scenes} 段 narrations。"
        )
        retry_response = await llm_service(
            prompt=retry_prompt,
            temperature=0.7,
            max_tokens=6000,
        )
        retry_result = _parse_json(retry_response)
        narrations, screen_evidence = _parse_topic_narration_result(
            retry_result,
            allow_structured_screen_ranking=screen_ranking,
            response_label="retry ",
        )
        screen_judge_accepted = True
        screen_judge_issues = []
        screen_judge_invalid = False
        if screen_ranking:
            (
                screen_judge_accepted,
                screen_judge_issues,
                screen_judge_invalid,
            ) = await _judge_screen_ranking_narrations(
                llm_service, narrations, screen_evidence
            )
        if _has_short_narration(narrations, min_words):
            raise ValueError(f"AI 文案仍然过短：每段至少需要 {min_words} 个汉字")
        if content_recipe == "ranking" and not _ranking_narrations_are_structured(narrations):
            raise ValueError("AI 盘点文案仍缺少逐项名称和具体介绍")
        if screen_judge_invalid:
            issue_text = "；".join(screen_judge_issues)
            raise ValueError(f"影视盘点语义校验响应无效：{issue_text}")
        if not screen_judge_accepted:
            issue_text = "；".join(screen_judge_issues)
            raise ValueError(f"AI 影视盘点文案语义校验仍未通过：{issue_text}")

    # Validate count
    if len(narrations) > n_scenes:
        if strict_count:
            raise ValueError(
                f"旁白数量不匹配：需要 {n_scenes} 条，实际 {len(narrations)} 条"
            )
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")
    
    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations


async def generate_narrations_from_content(
    llm_service,
    content: str,
    n_scenes: int = 5,
    min_words: int = 5,
    max_words: int = 20,
    strict_count: bool = False,
) -> List[str]:
    """
    Generate narrations from user-provided content using LLM
    
    Args:
        llm_service: LLM service instance
        content: User-provided content
        n_scenes: Number of narrations to generate
        min_words: Minimum narration length
        max_words: Maximum narration length
        strict_count: Reject excess results instead of preserving legacy truncation
    
    Returns:
        List of narration texts
    """
    from morpheus_video_studio.prompts import build_content_narration_prompt
    
    logger.info(f"Generating {n_scenes} narrations from content ({len(content)} chars)")
    
    prompt = build_content_narration_prompt(
        content=content,
        n_storyboard=n_scenes,
        min_words=min_words,
        max_words=max_words
    )
    
    response = await llm_service(
        prompt=prompt,
        temperature=0.8,
        max_tokens=6000
    )
    
    # Parse JSON
    result = _parse_json(response)
    
    if "narrations" not in result:
        raise ValueError("Invalid response format: missing 'narrations' key")
    
    narrations = [clean_narration(n) for n in result["narrations"]]

    # Validate count
    if len(narrations) > n_scenes:
        if strict_count:
            raise ValueError(
                f"旁白数量不匹配：需要 {n_scenes} 条，实际 {len(narrations)} 条"
            )
        logger.warning(f"Got {len(narrations)} narrations, taking first {n_scenes}")
        narrations = narrations[:n_scenes]
    elif len(narrations) < n_scenes:
        raise ValueError(f"Expected {n_scenes} narrations, got only {len(narrations)}")
    
    logger.info(f"Generated {len(narrations)} narrations successfully")
    return narrations


async def split_narration_script(
    script: str,
    split_mode: Literal["auto", "paragraph", "line", "sentence"] = "paragraph",
    target_segments: Optional[int] = None,
    max_chars_per_segment: Optional[int] = None,
) -> List[str]:
    """
    Split user-provided narration script into segments
    
    Args:
        script: Fixed narration script
        split_mode: Splitting strategy
            - "auto": Paragraph -> line -> smart sentence chunking
            - "paragraph": Split by double newline (\\n\\n), preserve single newlines within paragraphs
            - "line": Split by single newline (\\n), each line is a segment
            - "sentence": Split by sentence-ending punctuation (。.!?！？)
        target_segments: Preferred number of output segments for smart chunking
        max_chars_per_segment: Soft max characters per segment when auto-grouping sentences
    
    Returns:
        List of narration segments
    """
    logger.info(f"Splitting script (mode={split_mode}, length={len(script)} chars)")
    
    narrations = []
    cleaned_script = script.strip()

    if split_mode == "auto":
        paragraphs = _split_paragraphs(cleaned_script)
        if len(paragraphs) >= 2:
            narrations = paragraphs
            logger.info(f"✅ Split script into {len(narrations)} segments (auto->paragraph)")
        else:
            lines = _split_lines(cleaned_script)
            if len(lines) >= 2:
                narrations = lines
                logger.info(f"✅ Split script into {len(narrations)} segments (auto->line)")
            else:
                narrations = _smart_sentence_chunks(
                    cleaned_script,
                    target_segments=target_segments,
                    max_chars_per_segment=max_chars_per_segment,
                )
                logger.info(f"✅ Split script into {len(narrations)} segments (auto->sentence chunks)")

    elif split_mode == "paragraph":
        # Split by double newline (paragraph mode)
        # Preserve single newlines within paragraphs
        narrations = _split_paragraphs(cleaned_script)
        if len(narrations) <= 1 and len(cleaned_script) > max(80, int(max_chars_per_segment or 80)):
            narrations = _smart_sentence_chunks(
                cleaned_script,
                target_segments=target_segments,
                max_chars_per_segment=max_chars_per_segment,
            )
            logger.info(f"✅ Split script into {len(narrations)} segments (paragraph fallback -> sentence chunks)")
        else:
            logger.info(f"✅ Split script into {len(narrations)} segments (by paragraph)")
    
    elif split_mode == "line":
        # Split by single newline (original behavior)
        narrations = _split_lines(cleaned_script)
        logger.info(f"✅ Split script into {len(narrations)} segments (by line)")
    
    elif split_mode == "sentence":
        narrations = _split_sentences(cleaned_script)
        if target_segments and len(narrations) > max(int(target_segments) * 2, 8):
            narrations = _group_text_units(
                narrations,
                target_segments=target_segments,
                max_chars_per_segment=max_chars_per_segment,
            )
            logger.info(f"✅ Split script into {len(narrations)} segments (sentence grouped)")
        else:
            logger.info(f"✅ Split script into {len(narrations)} segments (by sentence)")
    
    else:
        # Fallback to line mode
        logger.warning(f"Unknown split_mode '{split_mode}', falling back to 'line'")
        narrations = _split_lines(cleaned_script)

    # Each segment is one spoken line — scrub any leftover literal \n / control
    # chars so they never surface on the subtitle.
    narrations = [clean_narration(n) for n in narrations if clean_narration(n)]

    # Log statistics
    if narrations:
        lengths = [len(s) for s in narrations]
        logger.info(f"   Min: {min(lengths)} chars, Max: {max(lengths)} chars, Avg: {sum(lengths)//len(lengths)} chars")

    return narrations


def estimate_spoken_duration_seconds(text: str, tts_speed: float = 1.0) -> float:
    """Roughly estimate spoken duration for mixed Chinese/English narration."""
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return 0.0

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    latin_words = len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", normalized))
    punctuation_pauses = len(re.findall(r"[，。！？；：,.!?;:、]", normalized))

    # Conservative pacing so planning does not under-estimate video length.
    seconds = (chinese_chars / 3.6) + (latin_words / 2.4) + (punctuation_pauses * 0.18)
    effective_speed = max(float(tts_speed or 1.0), 0.5)
    return max(seconds / effective_speed, 1.0)


def estimate_scene_plan(
    text: str,
    target_scene_seconds: float = 8.0,
    tts_speed: float = 1.0,
    min_scenes: int = 1,
    max_scenes: int = 30,
) -> dict:
    """Estimate total narration time and a reasonable scene count from text length."""
    total_seconds = estimate_spoken_duration_seconds(text, tts_speed=tts_speed)
    sentences = _split_sentences(text)
    sentence_count = len(sentences)
    target_scene_seconds = max(float(target_scene_seconds or 0), 2.0)

    recommended = max(1, math.ceil(total_seconds / target_scene_seconds))
    if sentence_count > 1:
        recommended = min(recommended, sentence_count)
    recommended = max(min_scenes if sentence_count >= min_scenes else 1, recommended)
    recommended = min(max_scenes, recommended)

    return {
        "estimated_duration_seconds": round(total_seconds, 1),
        "recommended_scenes": int(recommended),
        "sentence_count": sentence_count,
    }


def plan_visual_shots(
    total_duration_seconds: float,
    min_shot_seconds: float = 2.0,
    max_shot_seconds: float = 3.2,
    max_shots: int = 4,
    shot_count: Optional[int] = None,
    hard_max_hold_seconds: Optional[float] = None,
) -> dict:
    """Plan how many visual shots should cover one narration segment.

    hard_max_hold_seconds: when set, a single shot is never allowed to hold
    longer than this — the planner may exceed max_shots (up to an absolute
    ceiling of 8) so long narrations don't turn into near-static frames.
    """
    total_duration = round(max(float(total_duration_seconds or 0.0), 0.1), 3)
    min_shot_seconds = max(float(min_shot_seconds or 0.0), 0.8)
    max_shot_seconds = max(float(max_shot_seconds or 0.0), min_shot_seconds)
    max_shots = max(int(max_shots or 1), 1)
    preferred_shot_seconds = (min_shot_seconds + max_shot_seconds) / 2

    candidate_ceiling = max_shots
    if hard_max_hold_seconds is not None and shot_count is None:
        hard_max_hold = max(float(hard_max_hold_seconds), max_shot_seconds)
        required_shots = math.ceil(total_duration / hard_max_hold)
        candidate_ceiling = min(max(max_shots, required_shots), 8)

    if shot_count is not None:
        selected_count = max(1, min(int(shot_count), max_shots))
    else:
        best_score = None
        selected_count = 1
        for candidate in range(1, candidate_ceiling + 1):
            average = total_duration / candidate
            # Candidates that break the hard hold cap are disqualified unless
            # even the ceiling cannot satisfy it (then the ceiling wins below).
            if (
                hard_max_hold_seconds is not None
                and average > max(float(hard_max_hold_seconds), max_shot_seconds)
                and candidate < candidate_ceiling
            ):
                continue
            score = abs(average - preferred_shot_seconds)
            if average < min_shot_seconds:
                score += (min_shot_seconds - average) * 4.0
            if average > max_shot_seconds:
                score += (average - max_shot_seconds) * 2.0
            if candidate == 1 and total_duration >= min_shot_seconds * 1.6:
                score += 1.25
            # When two plans are similarly good, prefer fewer cuts for smoother pacing.
            score += candidate * 0.25
            if best_score is None or score < best_score:
                best_score = score
                selected_count = candidate

    shot_durations = _split_duration_evenly(total_duration, selected_count)
    return {
        "target_duration_seconds": total_duration,
        "shot_count": selected_count,
        "shot_durations": shot_durations,
    }


def build_shot_prompt_variants(base_prompt: Optional[str], shot_count: int) -> List[str]:
    """Create semantically aligned prompt variants for the same narration segment."""
    prompt = (base_prompt or "").strip()
    count = max(int(shot_count or 1), 1)
    if not prompt:
        return [""] * count

    variants = [
        prompt,
        f"{prompt}, alternate composition, medium shot, stronger subject focus, cinematic framing",
        f"{prompt}, close-up detail shot, emphasize expression or key object texture, cinematic lighting",
        f"{prompt}, environmental cutaway shot, supporting atmosphere, wider surrounding context, cinematic depth",
    ]

    if count <= len(variants):
        return variants[:count]

    extra_variants = []
    for idx in range(len(variants), count):
        extra_variants.append(
            f"{prompt}, alternate camera angle {idx + 1}, preserve subject identity, consistent scene continuity"
        )
    return variants + extra_variants


def _split_paragraphs(script: str) -> List[str]:
    paragraphs = re.split(r"\n\s*\n", script)
    return [para.strip() for para in paragraphs if para.strip()]


def _split_duration_evenly(total_duration: float, parts: int) -> List[float]:
    if parts <= 1:
        return [round(total_duration, 3)]

    base = round(total_duration / parts, 3)
    durations = [base] * (parts - 1)
    last = round(total_duration - sum(durations), 3)
    if last <= 0:
        return [round(total_duration / parts, 3) for _ in range(parts)]
    durations.append(last)
    return durations


def _split_lines(script: str) -> List[str]:
    return [line.strip() for line in script.split("\n") if line.strip()]


def _split_sentences(script: str) -> List[str]:
    normalized = re.sub(r"[ \t]+", " ", (script or "").strip())
    if not normalized:
        return []

    sentence_candidates = re.split(r"(?<=[。！？!?；;])\s*|(?<=[.])\s+(?=[A-Z0-9\"'])", normalized)
    sentences = [item.strip() for item in sentence_candidates if item and item.strip()]
    return sentences or [normalized]


def _smart_sentence_chunks(
    script: str,
    target_segments: Optional[int] = None,
    max_chars_per_segment: Optional[int] = None,
) -> List[str]:
    sentences = _split_sentences(script)
    if len(sentences) <= 1:
        return sentences or [script.strip()]
    return _group_text_units(
        sentences,
        target_segments=target_segments,
        max_chars_per_segment=max_chars_per_segment,
    )


def _group_text_units(
    units: List[str],
    target_segments: Optional[int] = None,
    max_chars_per_segment: Optional[int] = None,
) -> List[str]:
    if not units:
        return []

    target_segments = max(int(target_segments or 0), 1) if target_segments else None
    average_chars = math.ceil(sum(len(unit) for unit in units) / max(target_segments or len(units), 1))
    soft_limit = max(24, int(max_chars_per_segment or average_chars))
    target_chars = max(18, min(soft_limit, average_chars))

    grouped: List[str] = []
    current = ""
    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        separator = " " if current and re.search(r"[A-Za-z0-9]$", current) and re.match(r"^[A-Za-z0-9]", unit) else ""
        candidate = f"{current}{separator}{unit}" if current else unit

        should_break = False
        if current and len(candidate) > soft_limit and len(current) >= max(int(target_chars * 0.65), 12):
            should_break = True
        elif current and target_segments and len(grouped) + 1 < target_segments and len(current) >= target_chars:
            should_break = True

        if should_break:
            grouped.append(current.strip())
            current = unit
        else:
            current = candidate

    if current.strip():
        grouped.append(current.strip())

    return grouped or [unit for unit in units if unit.strip()]


async def generate_image_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
    visual_rules: str = ""
) -> List[str]:
    """
    Generate image prompts from narrations (with batching and retry)

    visual_rules: optional per-recipe画面规则 (e.g. no human figures) prepended
    to the LLM prompt — local SD1.5 mangles people, so knowledge channels steer
    imagery to herbs/objects/texts instead.
    
    Args:
        llm_service: LLM service instance
        narrations: List of narrations
        min_words: Min image prompt length
        max_words: Max image prompt length
        batch_size: Max narrations per batch (default: 10)
        max_retries: Max retry attempts per batch (default: 3)
        progress_callback: Optional callback(completed, total, message) for progress updates
    
    Returns:
        List of image prompts (base prompts, without prefix applied)
    """
    from morpheus_video_studio.prompts import build_image_prompt_prompt
    
    logger.info(f"Generating image prompts for {len(narrations)} narrations (batch_size={batch_size})")
    
    # Split narrations into batches
    batches = [narrations[i:i + batch_size] for i in range(0, len(narrations), batch_size)]
    logger.info(f"Split into {len(batches)} batches")
    
    all_prompts = []
    
    # Process each batch
    for batch_idx, batch_narrations in enumerate(batches, 1):
        logger.info(f"Processing batch {batch_idx}/{len(batches)} ({len(batch_narrations)} narrations)")
        
        # Retry logic for this batch
        for attempt in range(1, max_retries + 1):
            try:
                # Generate prompts for this batch
                prompt = build_image_prompt_prompt(
                    narrations=batch_narrations,
                    min_words=min_words,
                    max_words=max_words,
                    visual_rules=visual_rules
                )
                
                response = await llm_service(
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=8192
                )
                if response is None:
                    raise RuntimeError("LLM returned an empty response while generating image prompts")
                
                logger.debug(f"Batch {batch_idx} attempt {attempt}: LLM response length: {len(response)} chars")
                
                # Parse JSON
                result = _parse_json(response)
                
                if "image_prompts" not in result:
                    raise KeyError("Invalid response format: missing 'image_prompts'")
                
                batch_prompts = result["image_prompts"]
                
                # Validate count
                if len(batch_prompts) != len(batch_narrations):
                    error_msg = (
                        f"Batch {batch_idx} prompt count mismatch (attempt {attempt}/{max_retries}):\n"
                        f"  Expected: {len(batch_narrations)} prompts\n"
                        f"  Got: {len(batch_prompts)} prompts"
                    )
                    logger.warning(error_msg)
                    
                    if attempt < max_retries:
                        logger.info(f"Retrying batch {batch_idx}...")
                        continue
                    else:
                        raise ValueError(error_msg)
                
                # Success!
                logger.info(f"✅ Batch {batch_idx} completed successfully ({len(batch_prompts)} prompts)")
                all_prompts.extend(batch_prompts)
                
                # Report progress
                if progress_callback:
                    progress_callback(
                        len(all_prompts),
                        len(narrations),
                        f"Batch {batch_idx}/{len(batches)} completed"
                    )
                
                break
                
            except (json.JSONDecodeError, RuntimeError) as e:
                logger.error(f"Batch {batch_idx} failed (attempt {attempt}/{max_retries}): {e}")
                if attempt >= max_retries:
                    raise
                logger.info(f"Retrying batch {batch_idx}...")
    
    # Hard scrub: when the recipe forbids people, remove any human reference the
    # LLM leaked, so distorted figures can't reach ComfyUI even on a bad batch.
    if "严禁出现人物" in (visual_rules or ""):
        scrubbed = [scrub_human_terms(p) for p in all_prompts]
        removed = sum(1 for a, b in zip(all_prompts, scrubbed) if a != b)
        if removed:
            logger.warning(f"Scrubbed human references from {removed}/{len(all_prompts)} image prompts")
        all_prompts = scrubbed

    all_prompts = [sanitize_visual_prompt(prompt) for prompt in all_prompts]

    logger.info(f"✅ Generated {len(all_prompts)} image prompts")
    return all_prompts


async def generate_video_prompts(
    llm_service,
    narrations: List[str],
    min_words: int = 30,
    max_words: int = 60,
    batch_size: int = 10,
    max_retries: int = 3,
    progress_callback: Optional[callable] = None,
    visual_rules: str = "",
) -> List[str]:
    """
    Generate video prompts from narrations (with batching and retry)
    
    Args:
        llm_service: LLM service instance
        narrations: List of narrations
        min_words: Min video prompt length
        max_words: Max video prompt length
        batch_size: Max narrations per batch (default: 10)
        max_retries: Max retry attempts per batch (default: 3)
        progress_callback: Optional callback(completed, total, message) for progress updates
    
    Returns:
        List of video prompts (base prompts, without prefix applied)
    """
    from morpheus_video_studio.prompts.video_generation import build_video_prompt_prompt
    
    logger.info(f"Generating video prompts for {len(narrations)} narrations (batch_size={batch_size})")
    
    # Split narrations into batches
    batches = [narrations[i:i + batch_size] for i in range(0, len(narrations), batch_size)]
    logger.info(f"Split into {len(batches)} batches")
    
    all_prompts = []
    
    # Process each batch
    for batch_idx, batch_narrations in enumerate(batches, 1):
        logger.info(f"Processing batch {batch_idx}/{len(batches)} ({len(batch_narrations)} narrations)")
        
        # Retry logic for this batch
        for attempt in range(1, max_retries + 1):
            try:
                # Generate prompts for this batch
                prompt = build_video_prompt_prompt(
                    narrations=batch_narrations,
                    min_words=min_words,
                    max_words=max_words,
                    visual_rules=visual_rules,
                )
                
                response = await llm_service(
                    prompt=prompt,
                    temperature=0.7,
                    max_tokens=8192
                )
                if response is None:
                    raise RuntimeError("LLM returned an empty response while generating video prompts")
                
                logger.debug(f"Batch {batch_idx} attempt {attempt}: LLM response length: {len(response)} chars")
                
                # Parse JSON
                result = _parse_json(response)
                
                if "video_prompts" not in result:
                    raise KeyError("Invalid response format: missing 'video_prompts'")
                
                batch_prompts = result["video_prompts"]
                
                # Validate batch result
                if len(batch_prompts) != len(batch_narrations):
                    raise ValueError(
                        f"Prompt count mismatch: expected {len(batch_narrations)}, got {len(batch_prompts)}"
                    )
                
                # Success - add to all_prompts
                all_prompts.extend(batch_prompts)
                logger.info(f"✓ Batch {batch_idx} completed: {len(batch_prompts)} video prompts")
                
                # Report progress
                if progress_callback:
                    completed = len(all_prompts)
                    total = len(narrations)
                    progress_callback(completed, total, f"Batch {batch_idx}/{len(batches)} completed")
                
                break  # Success, move to next batch
            
            except Exception as e:
                logger.warning(f"✗ Batch {batch_idx} attempt {attempt} failed: {e}")
                if attempt >= max_retries:
                    raise
                logger.info(f"Retrying batch {batch_idx}...")
    
    all_prompts = [sanitize_visual_prompt(prompt) for prompt in all_prompts]
    logger.info(f"✅ Generated {len(all_prompts)} video prompts")
    return all_prompts


def _parse_json(text: str) -> dict:
    """
    Parse JSON from text, with fallback to extract JSON from markdown code blocks
    
    Args:
        text: Text containing JSON
        
    Returns:
        Parsed JSON dict
        
    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Try direct parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code block
    json_pattern = r'```(?:json)?\s*([\s\S]+?)\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find any JSON object in the text
    json_pattern = r'\{[^{}]*(?:"narrations"|"image_prompts"|"video_prompts"|"scenes")\s*:[\s\S]*\}'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    # If all fails, raise error
    raise json.JSONDecodeError("No valid JSON found", text, 0)
