"""Generate validated, grounded image/video prompt pairs in one LLM call."""

import json

from morpheus_video_studio.models.visual_scene_plan import VisualFact, VisualScenePlan
from morpheus_video_studio.utils.visual_prompt_policy import build_visual_rules


_PLAN_FIELDS = {
    "index",
    "subject",
    "location",
    "action",
    "outcome",
    "evidence",
}
_FACT_FIELDS = ("subject", "location", "action", "outcome", "evidence")
_JUDGE_FIELDS = {
    "index",
    "faithful_translation",
    "english_only",
    "no_added_details",
    "issues",
}


def _build_visual_scene_plan_prompt(narrations: list[str], visual_rules: str) -> str:
    payload = json.dumps({"narrations": narrations}, ensure_ascii=False, indent=2)
    return f"""# Grounded visual-scene planning

{build_visual_rules(visual_rules)}

Create exactly one plan for every narration below. For each fact, return a `source` exact non-empty substring copied from the matching narration and an `english` translation. Subject must have both values. Location, action, outcome, and evidence must either have both values or have both values as empty strings. Do not add named entities or return image/video prompt prose; Python builds the final prompts only from these translations and fixed safe clauses.

Input:
{payload}

Output only strict JSON with this exact shape. The plans count and each 1-based index must exactly match the input order. Every plan must contain exactly: index, subject, location, action, outcome, evidence. Each fact must contain exactly source and english.
{{"plans":[{{"index":1,"subject":{{"source":"","english":""}},"location":{{"source":"","english":""}},"action":{{"source":"","english":""}},"outcome":{{"source":"","english":""}},"evidence":{{"source":"","english":""}}}}]}}
"""


def _parse_visual_scene_plans(response: str, narrations: list[str]) -> list[VisualScenePlan]:
    if not isinstance(response, str) or not response.strip():
        raise ValueError("response is blank")
    payload = json.loads(response)
    if not isinstance(payload, dict) or set(payload) != {"plans"}:
        raise ValueError("root object must contain only plans")
    items = payload["plans"]
    expected_count = len(narrations)
    if not isinstance(items, list) or len(items) != expected_count:
        actual = len(items) if isinstance(items, list) else "non-list"
        raise ValueError(f"plan count mismatch: expected {expected_count}, got {actual}")

    plans: list[VisualScenePlan] = []
    for expected_index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or set(item) != _PLAN_FIELDS:
            raise ValueError(f"plan {expected_index} has missing or extra fields")
        if type(item["index"]) is not int or item["index"] != expected_index:
            raise ValueError(f"plan {expected_index} has invalid index")
        facts: dict[str, VisualFact] = {}
        for field in _FACT_FIELDS:
            value = item[field]
            if not isinstance(value, dict) or set(value) != {"source", "english"}:
                raise ValueError(f"plan {expected_index} has invalid {field} pair")
            facts[field] = VisualFact(**value)
        plan = VisualScenePlan(**facts)
        plan.validate_narration_facts(narrations[expected_index - 1])
        plan.build_prompts()
        plans.append(plan)
    return plans


def _build_translation_judge_prompt(
    narrations: list[str], plans: list[VisualScenePlan]
) -> str:
    items = []
    for index, (narration, plan) in enumerate(zip(narrations, plans), start=1):
        facts = {
            field: {
                "source": getattr(plan, field).source,
                "english": getattr(plan, field).english,
            }
            for field in _FACT_FIELDS
        }
        items.append({"index": index, "narration": narration, "facts": facts})
    payload = json.dumps({"plans": items}, ensure_ascii=False, indent=2)
    return f"""# Bilingual visual-fact fidelity judge

Review each narration and its visual fact source/English pairs. A translation is acceptable only when it faithfully translates its exact source, contains English only, and adds no details absent from the source. Do not judge style or prompt wording.

Input:
{payload}

Output only strict JSON. The plans count and 1-based indexes must match input exactly. Each plan must contain exactly index, faithful_translation, english_only, no_added_details, issues. All accepted booleans must be true and issues must be an empty string array.
{{"plans":[{{"index":1,"faithful_translation":true,"english_only":true,"no_added_details":true,"issues":[]}}]}}
"""


def _validate_translation_judge_response(response: str, expected_count: int) -> None:
    if not isinstance(response, str) or not response.strip():
        raise ValueError("translation judge response is blank")
    payload = json.loads(response)
    if not isinstance(payload, dict) or set(payload) != {"plans"}:
        raise ValueError("translation judge root must contain only plans")
    items = payload["plans"]
    if not isinstance(items, list) or len(items) != expected_count:
        actual = len(items) if isinstance(items, list) else "non-list"
        raise ValueError(
            f"translation judge plan count mismatch: expected {expected_count}, got {actual}"
        )
    for expected_index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or set(item) != _JUDGE_FIELDS:
            raise ValueError(f"translation judge plan {expected_index} has invalid fields")
        if type(item["index"]) is not int or item["index"] != expected_index:
            raise ValueError(f"translation judge plan {expected_index} has invalid index")
        if any(
            type(item[field]) is not bool
            for field in ("faithful_translation", "english_only", "no_added_details")
        ):
            raise ValueError(f"translation judge plan {expected_index} has invalid booleans")
        issues = item["issues"]
        if not isinstance(issues, list) or any(
            not isinstance(issue, str) or not issue.strip() for issue in issues
        ):
            raise ValueError(f"translation judge plan {expected_index} has invalid issues")
        if not all(
            item[field]
            for field in ("faithful_translation", "english_only", "no_added_details")
        ) or issues:
            raise ValueError(f"translation judge rejected plan {expected_index}")


async def _judge_translation_fidelity(
    llm_service, narrations: list[str], plans: list[VisualScenePlan]
) -> None:
    response = await llm_service(
        prompt=_build_translation_judge_prompt(narrations, plans),
        temperature=0,
        max_tokens=4096,
    )
    _validate_translation_judge_response(response, len(plans))


async def generate_visual_scene_plans(
    llm_service,
    narrations: list[str],
    visual_rules: str = "",
) -> list[VisualScenePlan]:
    """Ask for aligned visual plans, retrying malformed or unsupported results."""
    if (
        not isinstance(narrations, list)
        or not narrations
        or any(not isinstance(narration, str) or not narration.strip() for narration in narrations)
    ):
        raise ValueError("visual-plan error: narrations must not be blank")
    normalized_narrations = [narration.strip() for narration in narrations]

    prompt = _build_visual_scene_plan_prompt(normalized_narrations, visual_rules)
    last_error: Exception | None = None
    for _attempt in range(3):
        try:
            response = await llm_service(prompt=prompt, temperature=0.4, max_tokens=8192)
            plans = _parse_visual_scene_plans(response, normalized_narrations)
            await _judge_translation_fidelity(llm_service, normalized_narrations, plans)
            return plans
        except Exception as exc:
            last_error = exc
    raise ValueError(f"visual-plan error after 3 attempts: {last_error}") from last_error
