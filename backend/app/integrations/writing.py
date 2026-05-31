from __future__ import annotations

import re

from pydantic import BaseModel


class WritingRequest(BaseModel):
    mode: str = "video_script"
    text: str
    tone: str = "clean"


class WritingResult(BaseModel):
    ok: bool
    mode: str
    text: str


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+", cleaned)
    return [part.strip(" ，,") for part in parts if part.strip(" ，,")]


def _fallback_subject(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    return compact[:24] or "未命名短视频"


def polish_text(text: str, tone: str = "clean") -> str:
    sentences = _sentences(text)
    if not sentences:
        return ""
    if tone == "novel":
        prefix = "夜色像一层薄雾，悄悄压低了所有喧闹。"
        suffix = "直到最后一刻，真正的答案才从细节里浮出来。"
    elif tone == "viral":
        prefix = "先别急着划走，这件事真正反常的地方在后面。"
        suffix = "把这条线索记住，你会重新理解整个故事。"
    else:
        prefix = ""
        suffix = ""

    body = " ".join(sentences)
    body = body.replace("非常", "格外").replace("很多", "许多").replace("然后", "随后")
    return " ".join(item for item in [prefix, body, suffix] if item)


def novel_outline(text: str) -> str:
    subject = _fallback_subject(text)
    beats = _sentences(text)[:4]
    while len(beats) < 4:
        beats.append(subject)
    return "\n".join(
        [
            f"标题：{subject}",
            f"开场：主角在一个看似平静的场景里遇到异常，{beats[0]}",
            f"推进：线索不断收紧，人物关系出现裂缝，{beats[1]}",
            f"反转：真正的冲突不是外部事件，而是主角一直回避的选择，{beats[2]}",
            f"结尾：留下一个清晰但有余味的画面，{beats[3]}",
        ]
    )


def video_script(text: str) -> str:
    sentences = _sentences(text)
    if not sentences:
        subject = _fallback_subject(text)
        sentences = [
            f"{subject}正在发生一个值得注意的变化。",
            "表面看起来很普通，但关键细节藏在选择里。",
            "当节奏被拉开，真正重要的东西开始显现。",
            "最后，把注意力放回行动本身。",
        ]
    if len(sentences) == 1:
        subject = sentences[0]
        sentences = [
            f"{subject}，这不是一个遥远的话题。",
            "它每天都藏在我们的判断、选择和习惯里。",
            "真正拉开差距的，往往不是一次爆发，而是持续积累。",
            "从今天开始，把一个小动作坚持下去。",
        ]

    return "\n".join(f"{index + 1}. {line}" for index, line in enumerate(sentences[:6]))


def run_writing_tool(payload: WritingRequest) -> WritingResult:
    if payload.mode == "polish":
        text = polish_text(payload.text, payload.tone)
    elif payload.mode == "novel_outline":
        text = novel_outline(payload.text)
    else:
        text = video_script(payload.text)
    return WritingResult(ok=bool(text), mode=payload.mode, text=text)
