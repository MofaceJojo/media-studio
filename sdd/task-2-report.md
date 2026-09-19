# Task 2 Report — Film/TV Explanation Prompt Guardrails

## Status

Completed and committed as `c5b43b9` (`fix: require plot-specific screen narration`).

## Changed files

- `morpheus_video_studio/prompts/content_recipes.py`
- `morpheus_video_studio/utils/content_generators.py`
- `tests/test_content_recipes.py`
- `tests/test_narration_length_retry.py`

## RED evidence

Command:

```bash
pytest -q tests/test_content_recipes.py tests/test_narration_length_retry.py
```

Result before implementation: `2 failed, 14 passed`.

- The ranking prompt lacked the required concrete-film terms.
- A structurally valid but abstract film-ranking item did not trigger a retry.

## GREEN evidence

Commands:

```bash
pytest -q tests/test_content_recipes.py tests/test_narration_length_retry.py
ruff check morpheus_video_studio/prompts/content_recipes.py morpheus_video_studio/utils/content_generators.py tests/test_content_recipes.py tests/test_narration_length_retry.py
git diff --check
```

Results: focused tests `16 passed`; Ruff reported `All checks passed!`; whitespace check exited successfully.

## Summary

The ranking recipe now explicitly requires concrete characters, actions, conflict, a key scene, and the selection reason for film/animation rankings. It explicitly forbids replacing plot explanation with abstract emotion or life lessons.

For `ranking` generation only, film/TV/animation topics now reject structured detail that has at least two configured abstract-emotion terms and no configured action/event marker. The retry prompt identifies the missing concrete evidence, and the retry result is checked again before it is accepted.

## Self-review and concern

The detector is intentionally conservative: it is only called for `content_recipe="ranking"` and screen-content topic markers, so other creative recipes are unaffected. Its topic classification is lexical (including `集`), and its concrete-event recognition intentionally uses the exact terms required by the brief; uncommon wording may therefore trigger a retry even when a human would consider the explanation specific. This is recoverable because it asks the model to rewrite once rather than rejecting the initial request outright.

## Follow-up: narrow screen-topic detection

Status: completed and committed as `f41607d` (`fix: narrow screen ranking topic detection`).

### RED evidence

Command:

```bash
pytest -q tests/test_content_recipes.py tests/test_narration_length_retry.py
```

Result before the follow-up implementation: `1 failed, 16 passed`. The new `推荐10个资料收集工具` ranking test made two LLM calls because the bare `集` inside `收集` was treated as a screen-content marker.

### GREEN evidence

Commands:

```bash
pytest -q tests/test_content_recipes.py tests/test_narration_length_retry.py
ruff check morpheus_video_studio/prompts/content_recipes.py morpheus_video_studio/utils/content_generators.py tests/test_content_recipes.py tests/test_narration_length_retry.py
git diff --check
```

Results: focused tests `17 passed`; Ruff reported `All checks passed!`; whitespace check exited successfully.

### Summary and self-review

Removed bare `集` from the screen-topic keywords and added an explicit episode pattern for Arabic or Chinese numerals directly followed by `集`. The existing `《蜡笔小新》最温暖的1集` regression remains covered, while `推荐10个资料收集工具` now avoids the screen-copy retry. The marker is intentionally narrow; an episode topic without either a screen/IP keyword or a number-plus-`集` expression will not receive the film-specific guardrail.
