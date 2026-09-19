# Final Scene-Draft Fix Report

## Scope and environment

- Branch: `codex/quick-create-and-morpheus-rebrand`
- Worktree: `/Volumes/MACDATA/morpheus-video-studio-latest`
- Review base: `327eae83050283c47377283f73e168957b08842e`
- Implementation commits:
  - `6274125195e349c8cca0524cc16d8ba78e7bfc85` — original nine-finding fix
  - `6897ac6bcfc7582341b2fb8832af0bf5f491522f` — final specificity-gate refactor
  - `dfed9c6d350c9c52e01b8dee8ca90c2a44f14d5f` — batched strict semantic judge
- Test runtime: system Python 3.13.13 with pytest 9.0.3. The repository `.venv` does not contain pytest, so it was not used for verification.

## Finding-by-finding TDD record

| Finding | RED evidence | Fix | GREEN evidence |
| --- | --- | --- | --- |
| Important 1 — film-ranking narration accepted generic copy, then depended on finite semantic wordlists | Five new judge-contract regressions first failed: weather-only legacy copy and “追寻梦想” leaked through, a visible umbrella choice was rejected, no batch judge existed, and invalid judge output did not fail. Follow-up RED cases showed fenced JSON was accepted and an all-true verdict with non-empty issues failed open. | Remove every local plot/action/non-observable vocabulary and length-based semantic acceptance rule. Send both structured and legacy screen-ranking results through one batched, `temperature=0`, strict-JSON judge per generation attempt. Require all four booleans (`identifiable_character`, `external_situation`, `observable_action_or_conflict_with_object_or_result`, `event_supported_reason`) and consistent `issues`; invalid or negative verdicts use the existing single rewrite boundary and then fail explicitly. Screen-target classification remains local so non-screen rankings and document generation avoid the judge. | The six directed semantic/bad-response cases pass; the full narration test file reports `35 passed`, and all cases remain green in the focused and full suites. |
| Important 2 — retry depended on stale errors and overwrote edits | New regression cases initially produced 2 functional failures plus a missing-helper import failure; a later blank-generation case also failed. | Derive retryable stages from actual empty fields, regenerate only missing indexes, preserve non-empty user edits, discard stale stage errors, and keep the error when regeneration returns blank content. | Retry and missing-field tests pass in the 98-test focused suite. |
| Important 3 — excess narration count was silently truncated | Five focused failures exposed unsupported `strict_count`, missing scene-generator handoff, and an intro-plus-N response that was not rejected. | Add opt-in `strict_count` to topic/document narration generators and enable it in both scene-draft paths, preserving legacy truncation for other callers. | The initial strict-count group reached `17 passed`; all cases remain green in the focused and full suites. |
| Important 4 — an empty original topic blocked a reusable draft | Three new single/batch regressions failed before input resolution. | Resolve structured scene narration first, then fall back to the legacy AI-script draft, before validating the original input. Batch mode still requires a non-empty topic when no reusable draft exists. | Four reusable-draft/input-validation cases pass, including structured, legacy, batch, and no-draft behavior. |
| Important 5 — recipe changes did not stale or clear a draft | Two recipe-state regressions failed. | Persist the resolved effective recipe with the draft, compare it in `_draft_is_stale`, and clear it with all other draft source metadata. | Recipe state and clearing cases pass in the focused suite. |
| Important 6 — content recipe was lost at video-generation handoff | Single and batch tests failed with two missing `content_recipe` keys. | Forward `content_recipe` in both single-generation parameters and batch shared configuration. | Both handoff assertions pass. |
| Important 7 — `None`/blank visual prompts were treated as usable text | Seven normalization/stage cases failed for `None`, empty, and whitespace image/video values; one retry case then exposed blank regenerated output. | Normalize `None` to empty text, reject aligned outputs containing any blank entry, isolate the failing visual stage, and reject blank retry results. | Eight normalization, image/video stage, and retry cases pass. |
| Minor 1 — progress UI did not expose real stages or partial failure | Two callback regressions failed, then stage-label and partial-completion helpers were introduced from failing imports/assertions. | Emit `narration`, `image_prompts`, and `video_prompts` callbacks; forward them through quick-create; render exact stage labels; report partial visual failure as an error state rather than successful completion. | Generator callback, forwarding, labels, and partial-completion tests all pass. |
| Minor 2 — trailing whitespace in two design specs | The review identified one trailing-whitespace line in each spec. | Remove the two trailing spaces without changing prose. | `git diff --check 327eae83050283c47377283f73e168957b08842e` exits 0 with no output. |

The film-copy regressions include the additional self-review/audit classes found after the first implementation: clause-prefix bypasses, generic subjects, passive generic subjects, descriptor-only titles, ordinal titles, unnamed titles, valid open-vocabulary actions, abstract action objects, structured-response compatibility, and screen-keyword collisions in tool rankings. The final implementation has no finite plot/action/non-observable vocabulary and no string-length shortcut for semantic acceptance. Its remaining regular expression classifies whether a topic is a screen ranking; it does not decide whether the generated plot is observable or specific.

## Final verification

- Focused regression suite:
  `python -m pytest -q tests/test_narration_length_retry.py tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_content_input_scene_count.py tests/test_scene_draft_pipeline.py`
  → `98 passed in 0.35s`.
- Full suite: `python -m pytest -q` → `191 passed, 12 warnings in 10.24s`.
- Compilation: `python -m compileall -q morpheus_video_studio web tests` → exit 0.
- Lint on the Python files changed by the final follow-up implementation commit: `git diff --name-only dfed9c6d350c9c52e01b8dee8ca90c2a44f14d5f^..dfed9c6d350c9c52e01b8dee8ca90c2a44f14d5f -- '*.py' | xargs python -m ruff check` → `All checks passed!`.
- A broader base-to-HEAD Ruff scan also includes earlier branch work outside this final-fix commit. It reports 17 pre-existing lint/deleted-path findings in those earlier files; they were not modified as part of this review fix.
- Exact base-to-worktree whitespace validation: `git diff --check 327eae83050283c47377283f73e168957b08842e` → exit 0, no output.

## Self-review and scope safeguards

- The original staged implementation set contained exactly the intended ten files. The structural follow-up contained exactly three files; the latest semantic-judge follow-up contained exactly two files: the content generator and narration regression tests.
- No browser or browser-tab operation was performed; the finalized tabs were not touched.
- Ignored temporary test files were not deleted or modified.
- Existing untracked user artifacts `sdd/task-2-report.md`, `sdd/task-5-browser-evidence.txt`, and `sdd/task-5-report.md` were neither staged nor edited.
- No push, pull request, merge, reset, or destructive cleanup was performed.

## LLM call counts

- A successful screen-ranking generation adds one LLM call: the single batched semantic judge.
- If the first generated result or first judge response fails, the bounded rewrite path uses four calls total: initial generation, first judge, one rewrite generation, and second judge. This is three extra calls beyond the initial generation, with no further retry.
- Non-screen rankings and document generation add no judge calls.

## Remaining doubts and limitations

- Both structured and legacy screen-ranking responses now use the same semantic judge, which adds one normal-path LLM call, latency, and model nondeterminism.
- The judge assesses whether each narration contains a specific observable event and supported reason; it does not verify factual plot truth against an external source.
- An invalid first judge response causes one content rewrite and a second judge, rather than re-judging the unchanged content; this preserves the required existing one-rewrite boundary.
- The 12 full-suite warnings are existing Pydantic v2 deprecation warnings in API models and schemas; they are outside this review-fix scope.
- The earlier branch changes are not globally Ruff-clean, as noted above; only the Python files in the final-fix implementation commit were required and verified clean here.
- Verification used the system Python environment because the checked-in worktree `.venv` lacks pytest. Dependency differences between that environment and a future project-managed test environment remain possible.
