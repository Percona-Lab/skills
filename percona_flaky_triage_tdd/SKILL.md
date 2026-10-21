---
name: percona_flaky_triage_tdd
description: "Use for Percona flaky test triage. Investigate intermittent or sporadic test failures, prepare an approval-ready triage plan, drive the diagnostic workflow until the issue is classified (flaky, deterministic, environmental, or inconclusive), and prepare handoff or completion."
metadata:
  short-description: Intermittent failure triage workflow.
---

## Working Agreement

Use this skill when the defining problem is uncertainty: a test failure is intermittent or sporadic, recurrence patterns matter more than a single failing run, and the first job is narrowing hypotheses — not landing a code fix.

The workflow is diagnostic-first with up to three sequential approval gates: triage plan → remediation plan → final validation. Phase 2 (remediation plan) is entered only when evidence confirms `deterministic` or `flaky-test-fix`; the `flaky` classification skips Phase 2 since no remediation is needed. No reruns or instrumentation are proposed until the triage plan is Lad-reviewed and explicitly approved. If the issue is confirmed deterministic, hand off to `percona_mtr_remediation_tdd`.

This skill is for intermittent/sporadic failure triage — not the default fix workflow for deterministic regressions.

## Non-negotiables

1. **Scope**: Use this skill for intermittent or sporadic test failure triage — not for deterministic test regressions that are clearly caused by a code change.
2. **Approval gates**: No reruns or instrumentation (phase 1), no remediation proposal (phase 2 — only entered for `deterministic` or `flaky-test-fix`), no final validation or history update (phase 3) until the relevant plan is Lad-reviewed and explicitly approved by the engineer. The `flaky` classification skips Phase 2 entirely.
3. **Rerun before remediation**: Always confirm recurrence by following the rerun criteria defined in the approved `triage_plan.md` before proposing a fix or remediation plan. A single failing run is not sufficient evidence for a remediation proposal; the triage plan defines the recurrence threshold (e.g., minimum N runs, failure frequency).
4. **Plan before action**: Create triage artifacts first in `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/`.
5. **Read-only external systems**: Do not write/update external systems (Google Sheets, Notion, Jenkins) from this skill. Use local artifacts for record-keeping; engineer is responsible for syncing to external systems. This choice diverges from the StarUML model label ("AI executes validation and updates flaky-history notes"); the local `flaky_history_update.md` artifact is the engineer-facing record for external sync.
6. **Escalate on inconclusive evidence**: If reruns and instrumentation do not narrow the hypothesis set enough to justify a next step, if environment instability outside code/test scope is suspected, or if the issue remains inconclusive after `max_inconclusive_cycles` rerun/instrumentation rounds (see Workflow Parameters), stop and escalate. Track the cycle count in `decision.md` (`inconclusive_cycle_count`).
7. **Handoff on deterministic or environmental root cause**: If evidence confirms the failure is deterministic, hand off to `percona_mtr_remediation_tdd` only if the fix was not already implemented in phase 2 (step 7). If build, ASAN, or Valgrind fallout is the real blocker, hand off to `percona_asan_build_remediation_tdd`. If evidence points to customer-specific reproduction, hand off to `percona_customer_repro_tdd`.

## Workflow Parameters

These parameters can be overridden in `.ai_helper.md` under a `test_triage` section. Defaults:

| Parameter | Default | Description |
|---|---|---|
| `max_review_cycles` | `3` | Lad review rounds per approval gate before proceeding regardless. Resets at the start of each approval gate; does not reset during revision loops within a single gate. Engineer-requested revisions count against the limit. This parameter is unique to this skill — sibling skills do not use it. |
| `max_inconclusive_cycles` | `3` | Instrumentation/rerun cycles before escalating inconclusive hypothesis sets. A cycle is one round of reruns/instrumentation from the approved triage plan. The counter (tracked as `inconclusive_cycle_count` in `decision.md`) resets only if new evidence narrows the hypothesis set (even without full classification). Narrowing means at least one hypothesis transitions from `inconclusive` to `flaky`, `deterministic`, `environmental`, or `rejected`. Re-ranking hypotheses without eliminating at least one candidate (e.g., H1 moves from 40% to 60% likelihood) does **not** reset the counter. If the engineer explicitly requests additional cycles beyond the limit, this counts as an informal override — record the decision in `decision.md` notes and proceed. |
| `default_final_validation_runs` | `3` | Minimum consecutive passing runs to confirm stability in phase 3 |
| `default_recurrence_threshold` | `2 consecutive failures` | Minimum evidence to confirm recurrence before proposing remediation |

## Required Tooling

Use these tools when available. If unavailable, ask the engineer for exported evidence and continue with local artifacts.

### Serena
- Activate project first.
- Use repository navigation and memories for context and continuity.

### Lad
- `system_design_review`
- `code_review`

### Kindly (Public Context)
- `web_search`
- `get_content`

### Jenkins (Read-only)
- `query_items`
- `get_item`
- `get_build`
- `get_build_console_output`
- `get_build_test_report`
- `get_build_parameters`
- `get_running_builds`

### Google Sheets (Read-only)
- `sheets_get_metadata`
- `sheets_get_values`
- `sheets_batch_get_values`

### Notion (Read-only)
- `notion-search`
- `notion-fetch`

## `.ai_helper.md` Contract

Before external fetches, read repository-root `.ai_helper.md`.
It is the authoritative source for **infrastructure pointers** (server URLs, workspace IDs, repository identity) used by this skill. Infrastructure pointers are set up once and don't change between invocations.

Per-invocation context comes from the engineer's prompt — do not expect it in `.ai_helper.md`. When the engineer invokes this skill, the prompt should include:
- The failing test name or suite (e.g., `mtr --suite=rpl --test-case=repl_replication`)
- The target branch or environment (e.g., `ps-8.0`)
- Any known flaky history link or reference

Expected sections/keys in `.ai_helper.md`:
- `jenkins` (optional): `base_url`
- `google_sheets` (optional): `spreadsheet_id_or_url`, `sheet_name`, `ranges`
- `notion` (optional): `workspace_or_search_scope`, `page_ids_or_urls`

Behavior on missing/incomplete `.ai_helper.md`:
- Do not guess endpoints or test identifiers.
- Notify engineer about missing fields.
- Continue with local evidence and available configured sources.

## Test Triage Artifact Set

### Phase 1 — Triage Plan (before any reruns or instrumentation)

For each triage run, create:
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/triage_plan.md`
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/hypotheses.md` — required fields: hypothesis ID, hypothesis text, classification (`flaky`, `flaky-test-fix`, `deterministic`, `environmental`, `inconclusive`), supporting evidence references, rerun/instrumentation plan. Hypothesis IDs are stable — assign in step 3 and do not renumber during the run.
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/evidence.md` — required minimum fields per entry: test identifier, source name, date fetched, relevant snippet, and hypothesis ID label (e.g., `H1-supports`, `H2-refutes`). In step 2, evidence entries may use provisional/temporary hypothesis labels if stable IDs have not yet been assigned — update them to stable IDs in step 3 when hypotheses are formally built. If sources conflict, note the conflict and explain which source was given priority and why.
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/decision.md`

### Phase 2 — Remediation Plan (if recurrence is confirmed and a fix is warranted)

Add:
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/remediation_plan.md`

### Phase 3 — Validation and History Update (after remediation or classification)

Add:
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/final_validation_plan.md` — for post-fix: N consecutive passing runs; for `flaky` (no fix): risk assessment, failure frequency, impact on CI reliability, recommended monitoring.
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/validation_report.md` — classification, outcomes of all validation runs, pass/fail counts, evidence, risk assessment (for `flaky`).
- `.test_triage/<YYYYMMDDTHHMMSSZ>_<short_context>/flaky_history_update.md` — classification-specific fields for external sync (see step 8 for per-classification field list).

Use UTC timestamp format `YYYYMMDDTHHMMSSZ` and snake_case `short_context`.
If the run folder already exists, append `_01`, `_02`, and so on until unique.

## Workflow (Step-by-step)

### 1) Initialize context and access

- Activate Serena if available.
- **Read artifact history context**: see `tdd` Step 1. (List subfolders from all 9 artifact folders, skip any that do not exist, sort by name descending, keep the top 300 in session context. Read folder contents reactively — only when a folder name seems relevant to the current problem.)
- Read `.ai_helper.md` for test identifier, target environment, flaky history reference, and optional external source pointers.
- If `.ai_helper.md` is incomplete, notify engineer and continue with available context.

### 2) Gather recurrence evidence

- Collect the failing test signal and run context (test name, suite, run environment, failure signature from logs or Jenkins console output).
- Collect recurrence evidence in this order (numbered by source priority — newer evidence overrides older; current run > recent Jenkins history > Sheets/Notion historical records):
  1. **Jenkins recurrence history** — last N runs of the failing test/job; failure frequency, error patterns, and build environment variations. Use `get_build`, `get_build_test_report`, `query_items`. Use `get_running_builds` only for monitoring live rerun status, not historical recurrence.
  2. **Google Sheets flaky history** — prior records for the same test; known flaky patterns, prior investigation notes, and resolution history.
  3. **Local git history** — recent commits touching the failing test or the code it exercises; identify if a recent change correlates with the failure onset.
  4. **Notion test-infra docs** — internal notes on flaky test patterns, known environmental issues, or prior triage sessions for the same test.
  5. **Kindly upstream context** — public bug tracker entries, release notes, or similar flaky patterns reported upstream for the same component.
- If a referenced external system (Jenkins, Sheets, Notion) is unavailable or returns an error, retry once. If the retry fails, append `[DEGRADED: <source>] — <reason>` to the relevant evidence entry in `evidence.md` and proceed with available local/git evidence. Do not block the triage on unavailable sources.
- Record evidence (Jenkins snippets, Sheets rows, git log, Notion excerpts, Kindly references) in `evidence.md` using the minimum fields defined in the Test Triage Artifact Set section: test identifier, source name, date fetched, relevant snippet, and hypothesis ID label (e.g., `H1-supports`, `H2-refutes`). If sources conflict, apply the default source priority (current run > recent Jenkins > Sheets > git > Notion > Kindly). If the engineer has explicitly specified a different priority, follow the engineer's priority and note it in `decision.md`.

### 3) Build hypotheses and triage plan

- Based on the evidence, identify candidate hypotheses for the failure. Assign stable hypothesis IDs (e.g., `H-timing`, `H-race-condition`, `H-env-resource`) before evidence collection begins — these IDs must not be renumbered during the run.
  - **flaky**: test fails due to test-environment timing, resource contention, or resource race conditions; root cause is not in product code or test code. No fix is needed — Phase 2 is skipped, Phase 3 documents the risk assessment.
  - **flaky-test-fix**: test fails due to a race condition or bug in the test logic itself (e.g., missing timeout, unsafe assertion, non-deterministic ordering). Root cause is in the test code, not the product code. The fix is in scope for Phase 2 remediation within this skill.
  - **deterministic**: test fails consistently due to a code change or regression in product code; fix-first workflow applies. Root cause is in product code.
  - **environmental**: test fails due to infrastructure or build environment issues; outside code/test scope. Escalation to the engineer is the terminal action — no downstream skill applies. Do not classify as `environmental` if the issue can be addressed by a code or test fix; use `deterministic` or `flaky-test-fix` instead.
  - **inconclusive**: evidence is insufficient to classify; further instrumentation required
- Rank hypotheses by likelihood given the evidence. Flag the highest-priority hypothesis for targeted rerun.
- Create `.test_triage/<run>/`.
- Write `triage_plan.md`, `hypotheses.md`, `evidence.md`, `decision.md`.
- In `triage_plan.md`, define:
  - the target rerun(s) to confirm or refute each ranked hypothesis (e.g., N consecutive runs, instrumentation flags, environment variations)
  - evidence required to promote each hypothesis to confirmed
  - open questions and decision criteria for classification
- In `hypotheses.md`, record:
  - each ranked hypothesis and its classification (`flaky`, `flaky-test-fix`, `deterministic`, `environmental`, `inconclusive`)
  - evidence supporting or refuting each hypothesis
  - rerun/instrumentation plan for each hypothesis
- In `decision.md`, record:
  - `status` (`draft`, `triage_approved`, `remediation_approved`, `completed`, `escalated`, `rejected`, `paused`, `awaiting_final_approval`, or `requires_retrigger` — where `rejected`, `escalated`, and `requires_retrigger` are terminal states (the workflow stops until re-invoked); `paused` signals a workflow interrupted by engineer unavailability — on re-invocation, read `decision.md` to identify the active phase and resume at the corresponding gate; `awaiting_final_approval` is set when entering Phase 3 pending engineer approval)
  - `approver` — name or GitHub handle of the engineer who provided explicit approval
  - `phase` — which phase the workflow is in (1: triage, 2: remediation, 3: validation)
  - `hypothesis_summary` — ranked list of candidate hypotheses and their current status
  - `inconclusive_cycle_count` — number of rerun/instrumentation rounds completed while the hypothesis set remains inconclusive (default `0`; incremented each step-6 round without narrowing; resets when new evidence narrows the hypothesis set)
  - `notes`

### 4) Review triage plan with Lad

- Run Lad `system_design_review` on planning artifacts (`triage_plan.md`, `hypotheses.md`, `evidence.md`).
- Apply worthwhile feedback until no material issues remain. Maximum `max_review_cycles` (default `3` per gate) review rounds per approval gate before proceeding regardless; note any remaining Lad flags in `decision.md` notes. A single cycle is one Lad review + one round of revisions (whether triggered by Lad or by the engineer). Engineer-requested revisions without an intervening Lad review also count as a cycle.
- If Lad flags an issue and the engineer disagrees, engineer approval takes precedence; document the disagreement in `decision.md` notes and proceed if the engineer confirms.

### 5) Phase 1 — Engineer approves triage plan

- Present reviewed `triage_plan.md` and `hypotheses.md`.
- Ask for explicit approval before running any reruns or instrumentation.
- If changes are requested, revise artifacts and repeat step 4. After `max_review_cycles` revision rounds without approval, summarize the current state, open issues, and remaining options and ask the engineer for a definitive decision.
- If the engineer declines to approve the plan, set `status = rejected` in `decision.md` and exit.
- If the engineer becomes unavailable mid-gate and explicitly requests a pause, set `status = paused` in `decision.md`. On re-invocation, resume at the same gate with all prior approvals preserved.
- On approval, set `status = triage_approved`, `phase = 1` in `decision.md` and proceed to step 6.

### 6) Execute approved reruns and instrumentation

- Run the approved reruns and instrumentation from the triage plan.
- If a rerun itself fails due to an unrecoverable Jenkins or infrastructure error (e.g., auth failure, job no longer exists), set `status: requires_retrigger` in `decision.md`, record the error in `evidence.md`, and stop — the workflow should be re-invoked once the system is restored. On re-invocation: all prior evidence and approvals are preserved; resume at Step 6 rerun execution. Confirm the triage plan is still current (branch, test ID) before proceeding; do not re-collect evidence or re-seek approval.
- Use `get_running_builds` to monitor live status while reruns are in progress. If a rerun hangs or stalls (treat as stalled if it exceeds 2x the expected runtime for that test), record the observation in `evidence.md` and count it as environmental evidence — do not wait indefinitely.
- Collect and record new evidence from each rerun in `evidence.md` (append new entries; do not discard prior evidence). If rerun results contradict prior evidence, note the conflict in `evidence.md` with both sources and an explanation of which source was given priority and why.
- If a rerun fails on a different test, assertion, or error signature than the original triage target, record this as a new or existing evidence entry. Do not conflate it with the original failure signal unless the same root cause is credibly implicated by both. This may indicate a second independent issue — note it separately and flag it for the engineer.
- After executing the approved reruns:
  - If evidence confirms the failure is **deterministic** or **flaky-test-fix**: set `status = awaiting_final_approval` in `decision.md`; classify the hypothesis as `deterministic` or `flaky-test-fix` in `hypotheses.md`; set `phase = 2` in `decision.md`; confirm `hypotheses.md` reflects the updated classification before proceeding to step 7. For `flaky-test-fix`, note that the Phase 2 fix targets the test file (not product code) — the engineer is approving a test-code change.
  - If evidence confirms the failure is **environmental**: set `status = escalated` in `decision.md`; classify the hypothesis as `environmental` in `hypotheses.md`; proceed to step 9 for terminal escalation to the engineer. Phase remains `1` (triage) since the workflow was still in Phase 1 when the issue was classified.
  - If evidence confirms the failure is **flaky**: set `status = awaiting_final_approval` in `decision.md`; classify the hypothesis as `flaky` in `hypotheses.md`; set `phase = 3` in `decision.md`; proceed to step 8 to prepare the final validation and history update. Phase `2` is skipped since no remediation is needed.
  - If evidence remains **inconclusive**: update `hypotheses.md` with new evidence; increment `inconclusive_cycle_count` in `decision.md`; assess whether additional reruns are warranted (check against `max_inconclusive_cycles`, default `3`). Narrowing means at least one hypothesis transitions from `inconclusive` to `flaky`, `deterministic`, `environmental`, or `rejected` — re-ranking without eliminating a candidate does not reset the counter. If the hypothesis set cannot be narrowed after this many cycles, set `status = escalated` in `decision.md` and stop — present the evidence and open questions to the engineer for a decision (step 9). If the engineer explicitly wants to continue beyond the cycle limit, record the decision in `decision.md` notes, leave `inconclusive_cycle_count` unchanged (do not reset), and proceed with another rerun round.

### 7) Phase 2 — Prepare and execute remediation (if deterministic or flaky-test-fix)

- Only enter this step if step 6 classified the issue as `deterministic` or `flaky-test-fix`. Pure `flaky` (no test fix needed) and `environmental` classifications skip to step 8 or step 9 respectively.
- Prepare `remediation_plan.md` with these required fields:
  - `root_cause_hypothesis` — the suspected code change or regression causing the deterministic failure
  - `proposed_fix` — the fix or revert approach. For `flaky-test-fix` classifications, the fix target is the test file (not product code); rollback is `git checkout <test-file>` rather than a product revert.
  - `validation_rerun_plan` — how to verify the fix resolves the issue
  - `rollback_plan` — what to do if the fix introduces new failures (e.g., `git revert <sha>` for deterministic; for `flaky-test-fix`, `git checkout <sha>` or `git restore <test-file>` to a known-good commit)
- Run Lad `system_design_review` on `remediation_plan.md`, `hypotheses.md`, and `evidence.md`. The Lad review must confirm the remediation plan is consistent with the approved hypotheses and evidence — if the plan contradicts a hypothesis that was already refuted, that is a material issue.
- Apply worthwhile feedback until no material issues remain. After `max_review_cycles` review rounds without resolving material issues, note the remaining flags in `decision.md` and present to the engineer for a decision on how to proceed.
- Present to engineer for explicit approval (Phase 2 gate).
- On approval, set `status = remediation_approved`, `phase = 2` in `decision.md`.
- Before implementing the fix, verify the triage target is still valid: confirm the branch, test, and failure signature have not changed since Phase 1 approval. If the branch was rebased or the test was deleted/renamed, set `status = escalated` in `decision.md` and escalate to step 9.
- Implement the approved fix or revert.
- Run the failing test to validate the fix.
- If the fix passes validation: update `decision.md` with `status = awaiting_final_approval`, `phase = 3`; proceed to step 8.
- If the validation run itself fails due to an unrecoverable infrastructure error (not a test failure): set `status = requires_retrigger` in `decision.md`, record the error in `evidence.md`, and stop — re-invoke once infrastructure is restored (same protocol as step 6 `requires_retrigger`).
- If the fix fails validation (test still fails): record failure in `evidence.md`; set `status = escalated` in `decision.md` and escalate to step 9.

### 8) Phase 3 — Final validation and history update

- This phase is always entered — whether from step 7 (fix validated) or directly from step 6 for `flaky` classifications — because the Phase 3 gate is a separate confirmation step to verify overall stability post-fix or to formally document an unfixed flaky test with a risk assessment. For `flaky` classifications where no fix was applied, the `final_validation_plan.md` should document the risk assessment of leaving the flakiness in the codebase (e.g., failure frequency, impact on CI reliability, recommended monitoring).
- Prepare `final_validation_plan.md`:
  - Define the final validation run(s) (e.g., N consecutive passing runs to confirm stability)
  - Define the flaky-history record to update (what fields, what format, what external system the engineer will sync to)
- Run Lad `system_design_review` on `final_validation_plan.md`.
- Apply worthwhile feedback. After `max_review_cycles` review rounds, note remaining flags in `decision.md` and present to engineer.
- Present to engineer for explicit approval (Phase 3 gate).
- If the engineer declines to approve the plan, set `status = rejected` in `decision.md` and stop.
- On approval, set `status = completed` in `decision.md`. (Do not write a `status` field into `final_validation_plan.md` — status lives only in `decision.md`.)
- Execute final validation runs.
- If any final validation run fails: record the failure in `validation_report.md`, set `status = escalated` in `decision.md`, and proceed to step 9 for engineer decision (do not mark the workflow as completed).
- Write `validation_report.md` with: classification (`flaky`, `flaky-test-fix`, `deterministic`, `environmental`, or `inconclusive`), outcomes of all validation runs, pass/fail counts, evidence, and risk assessment (for `flaky` classifications where no fix was applied).
- Write `flaky_history_update.md` as a local artifact summarizing the classification, evidence, and the history-record fields the engineer should copy to the external flaky-history system. The `environmental` classification does not produce this artifact — there is no external flaky-history entry for infrastructure issues. For all other classifications, include these fields for Sheets or Notion sync:
  - **For `flaky`**: test identifier, classification = `flaky`, failure frequency from Jenkins (the primary finding), risk assessment (e.g., estimated CI blockage impact), recommended monitoring, date of triage.
  - **For `flaky-test-fix` / `deterministic`**: test identifier, classification, failure frequency from Jenkins, root cause hypothesis, recommended action, date of triage, instrumentation findings.
  - **For `inconclusive`**: test identifier, classification = `inconclusive`, evidence summary, open questions, date of triage.
  This artifact is read-only for external systems — the engineer is responsible for the actual sync.

### 9) Handoff or escalate

- If `status = requires_retrigger` in `decision.md`:
  - Present the infrastructure error recorded in `evidence.md` and the current classification (if any).
  - Inform the engineer that the workflow requires re-invocation once the infrastructure is restored. Do not attempt handoff — the workflow must be resumed from step 6.
  - Request engineer direction: retry now (if infrastructure is restored) or pause.
- If `status = escalated` and `phase = 1` and the issue was classified as `environmental`: present `hypotheses.md` with environmental evidence, note that no downstream skill applies to infrastructure issues, and request engineer direction on how to proceed (e.g., resolving the infrastructure issue and re-invoking, or documenting and closing).
- If the workflow completed with a classification:
  - Present the completed `hypotheses.md` (with final classifications), `validation_report.md` (if applicable), and `flaky_history_update.md` (if applicable).
  - If the issue is deterministic and the fix was not already implemented in phase 2, hand off to `percona_mtr_remediation_tdd`.
  - If build, ASAN, or Valgrind issues surface, hand off to `percona_asan_build_remediation_tdd`.
  - If evidence points to customer-specific reproduction, hand off to `percona_customer_repro_tdd`.
  - If multiple handoff targets apply, present all applicable ones to the engineer for priority ordering. Verify each target exists in `solution/skills/` before presenting it; if a target is unavailable or is the current skill, exclude it and notify the engineer.
  - If no handoff is needed and the issue is classified, confirm completion to the engineer.
- If the workflow reached an inconclusive or escalated state:
  - Update `decision.md` with `status = escalated` if not already set.
  - Present: `hypotheses.md` with current evidence, `evidence.md` with all gathered data, open questions, and a specific "Ask" for the engineer. A good Ask is structured as: "To proceed, I need: [1] <specific instrumentation or access>, [2] <confirmation on approach A vs B>, [3] <any additional context>."
  - Request explicit engineer direction.

## Handoff Rules

- If the failure is confirmed `environmental` (infrastructure or build environment issue outside code/test scope), there is no downstream skill — escalation to the engineer is the terminal action.
- If the failure is confirmed deterministic and the root cause is a code change or regression, `percona_mtr_remediation_tdd` is a potential handoff for the fix workflow.
- If build, ASAN, or Valgrind fallout becomes the primary blocker, `percona_asan_build_remediation_tdd` is a potential handoff.
- If evidence points to customer-specific reproduction rather than CI flakiness, `percona_customer_repro_tdd` is a potential handoff.
- Multiple handoff targets may apply simultaneously; present all applicable ones to the engineer for priority ordering.
- If the handoff target skill is not found in `solution/skills/` or is the current skill itself, notify the engineer and pause escalation until a valid target is available.

## Workflow Outputs

Expected outputs:
- Lad-reviewed and engineer-approved triage plan with ranked hypotheses.
- Evidence trail recording all sources, reruns, and instrumentation results.
- Explicit classification of the issue (`flaky`, `deterministic`, `environmental`, or `inconclusive`).
- Completed `flaky_history_update.md` ready for engineer to sync to external systems.
- Clear downstream handoff package when needed.

## Workflow Activity Diagram (PlantUML)

```plantuml
@startuml
start

:Activate Serena project;
if (Serena activation succeeds?) then (yes)
  :Proceed with Serena-enabled workflow;
else (no)
  :Continue without Serena;
  :State why activation failed;
endif

:Read .ai_helper.md;
if (.ai_helper.md complete?) then (yes)
  :Proceed with configured sources;
else (no)
  :Notify engineer about missing fields;
  :Continue with available local/context sources;
endif

:Gather recurrence evidence;
:1) Jenkins recurrence history;
:2) Google Sheets flaky history;
:3) Local git history;
:4) Notion test-infra docs;
:5) Kindly upstream context;

:Create .test_triage/<run>/;
:Write triage_plan.md + hypotheses.md + evidence.md + decision.md;

repeat
  :Run Lad system_design_review on triage artifacts;
  :Apply useful plan feedback;
repeat while (More useful plan feedback?) is (yes)

:Present reviewed triage plan to engineer;
if (Engineer requests changes?) then (yes)
  :Update plan artifacts;
  repeat
    :Run Lad system_design_review on updated plan artifacts;
    :Apply useful plan feedback;
  repeat while (More useful plan feedback?) is (yes)
endif
repeat while (Engineer approves triage plan?) is (no)

:Set status = triage_approved, phase = 1 in decision.md;

:Execute approved reruns and instrumentation;
:Confirm recurrence — follow triage_plan.md recurrence threshold;

if (Rerun infrastructure failure?) then (yes)
  :Set status = requires_retrigger in decision.md;
  :Record error in evidence.md;
  :Stop — re-invoke when system restored;
  stop
else (no)
endif

if (Issue classified as flaky (no test-fix needed)?) then (yes)
  :Set status = awaiting_final_approval, phase = 3 in decision.md;
  :Classify as flaky in hypotheses.md;
  :**Skip Phase 2** — no remediation needed;
  -> Prepare final_validation_plan.md;
else (no)
endif

if (Issue classified as deterministic?) then (yes)
  :Set status = awaiting_final_approval, phase = 2 in decision.md;
  :Classify as deterministic in hypotheses.md;
  -> Phase 2 — prepare remediation;
else (no)
endif

if (Issue classified as flaky-test-fix?) then (yes)
  :Set status = awaiting_final_approval, phase = 2 in decision.md;
  :Classify as flaky-test-fix in hypotheses.md;
  -> Phase 2 — prepare remediation;
else (no)
endif

if (Issue classified as environmental?) then (yes)
  :Set status = escalated in decision.md;
  :Classify as environmental in hypotheses.md;
  -> Step 9 — handoff/escalation;
else (no)
endif

if (Issue remains inconclusive?) then (yes)
  :Update hypotheses.md with new evidence;
  :Increment inconclusive_cycle_count in decision.md;
  if (max_inconclusive_cycles reached?) then (yes)
    :Set status = escalated in decision.md;
    :Escalate to engineer;
    stop
  else (no)
    :Escalate to engineer for direction;
    note right: Engineer may request additional rerun round;
    stop
  endif
else (no)
endif

:Prepare remediation_plan.md;
:Run Lad system_design_review on remediation_plan.md;
:Present to engineer for Phase 2 approval;

if (Engineer approves remediation plan?) then (no)
  :Set status = rejected in decision.md;
  stop
else (yes)
endif

:Set status = remediation_approved, phase = 2 in decision.md;
:Implement approved fix or revert;
:Run failing test to validate fix;

if (Fix passes validation?) then (no)
  :Record failure in evidence.md;
  :Set status = escalated in decision.md;
  :Escalate to engineer;
  stop
else (yes)
endif

:Set status = awaiting_final_approval, phase = 3 in decision.md;

:Prepare final_validation_plan.md;
:Run Lad system_design_review on final_validation_plan.md;
:Present to engineer for Phase 3 approval;

if (Engineer approves final validation plan?) then (no)
  :Set status = rejected in decision.md;
  stop
else (yes)
endif

:Set status = completed in decision.md;
:Execute final validation runs;

if (All final validation runs pass?) then (no)
  :Record failure in validation_report.md;
  :Set status = escalated in decision.md;
  -> Step 9 — handoff/escalation;
else (yes)
endif

:Write validation_report.md;
:Write flaky_history_update.md;

:Present completed artifacts to engineer;
:Check all downstream conditions;
note right: check handoff targets exist in solution/skills/ and are not self;

if (Any handoff needed?) then (yes)
  :Verify handoff target exists and is not current skill;
  if (Handoff target valid?) then (yes)
    :Present all applicable handoffs to engineer;
    :Engineer decides priority order;
    stop
  else (no)
    :Notify engineer — handoff target not available;
    :Pause until target is available;
    stop
  endif
else (no)
endif

:Confirm completion to engineer;
stop
@enduml
```

## Usage Examples

```text
Investigate the current intermittent test failure, prepare a reviewed triage plan with ranked hypotheses, and continue until the issue is classified as flaky, deterministic, environmental, or inconclusive. Follow $percona_flaky_triage_tdd.
```

```text
Use Jenkins recurrence history and prior flaky-history notes to determine whether this test is flaky or a real regression, then prepare the next approved workflow step — rerun, remediation, or classification. Follow $percona_flaky_triage_tdd.
```

## Serena memories (when supported)

Store useful flaky-triage knowledge for future tasks:
- recurring flaky test signatures and their root causes,
- rerun strategies that reliably distinguish flaky from deterministic,
- instrumentation techniques that narrow hypotheses fastest,
- classification patterns for environmental vs. code-related failures.