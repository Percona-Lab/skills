---
name: percona_gca_sync_tdd
description: "Use for Percona GCA (Greatest Common Ancestor) cross-branch synchronization. Map missing commits across Percona's branch set, prepare reviewed sync and verification plans, execute approved cherry-picks and null-merges, and confirm cross-branch parity."
metadata:
  short-description: Cross-branch GCA synchronization workflow.
---

## Working Agreement

Use this skill when the problem is cross-branch divergence inside the Percona branch set: identifying commits that exist on some branches but are missing from others, planning the right sync action, and confirming parity after execution.

The workflow is plan-first with three sequential approval gates: missing-commit map → verification plan → parity plan. One target branch is processed per invocation, using the other branches as reference context. No cherry-picks, null-merges, or parity updates are executed without explicit engineer approval.

This skill is for GCA synchronization — not for general upstream merge conflict interpretation. If a sync action hits a file-level conflict, hand off to `percona_conflict_resolution_tdd` and return here to continue.

## Non-negotiables

1. **Scope**: Use this skill for GCA cross-branch synchronization — mapping missing commits, planning sync actions, verifying application, and confirming parity. Do not use it for general upstream merge conflicts or feature delivery.
2. **One branch at a time**: Each invocation targets a single branch. The other branches in the set are used as reference context only.
3. **Three-phase approval gate**: No sync action is executed until the relevant plan (missing-commit map, verification plan, parity plan) is Lad-reviewed and explicitly approved by the engineer. Each gate is a separate human approval checkpoint; the Lad review loop within each gate is distinct from the gate itself.
4. **Approved scope only**: Cherry-picks, null-merges, and parity updates are limited strictly to what the engineer approved. Do not add commits outside the approved scope.
5. **Plan before action**: Create all artifacts first in `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/`.
6. **Read-only external systems**: Do not write/update Google Sheets, Notion, or Jenkins from this skill. Use local artifacts for sync records; engineer is responsible for syncing to external systems. This choice diverges from the StarUML model label ("AI updates sync notes"); the local `gca_sync_status.md` artifact is the engineer-facing record for external sync.
7. **Handoff-and-return on conflict**: If a cherry-pick or null-merge hits a file-level conflict, set `status = requires_handoff` and hand off to `percona_conflict_resolution_tdd`. After the conflict is resolved, re-invoke this skill: resume at step 6 by checking remaining approved sync scope, then continue execution. Do not re-execute completed actions.
8. **Escalate on ambiguity**: If divergence cannot be explained cleanly from available history, or parity cannot be defined for engineer approval, stop and escalate.

## Workflow Parameters

These parameters can be overridden in `.ai_helper.md` under a `gca_sync` section. Defaults:

| Parameter | Default | Description |
|---|---|---|
| `max_review_cycles` | `3` | Lad review rounds per approval gate. Resets at the start of each gate; does not reset during revision loops within a single gate. Engineer-requested revisions count against the limit. After this many cycles without approval, summarize the current state and ask the engineer for a definitive decision. |
| `branch_set` | `[ps-8.0, ps-8.4, ps-9.x]` | Percona's three active release branches as a YAML list. Engineer may specify a subset. |
| `target_branch` | engineer's choice | The branch to process in this invocation. Set once per run folder and not changed within the same run. |

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

### GitHub (Read-only)
- `search_code`
- `get_file_contents`
- `list_commits`
- `get_commit`

### Google Sheets (Read-only)
- `sheets_get_metadata`
- `sheets_get_values`
- `sheets_batch_get_values`

### Notion (Read-only)
- `notion-search`
- `notion-fetch`

### Jenkins (Read-only, for post-sync verification)
- `query_items`
- `get_item`
- `get_build`
- `get_build_console_output`
- `get_build_test_report`
- `get_build_parameters`

## `.ai_helper.md` Contract

`.ai_helper.md` is for infrastructure pointers (server URLs, workspace IDs, repository identity) set up once. Per-invocation context (branch set, target branch) comes from the engineer's prompt.

Before external fetches, read repository-root `.ai_helper.md`.
It is the authoritative source for environment-specific pointers used by this skill.

Expected sections/keys:
- `jenkins` (optional): `base_url`
- `google_sheets` (optional): `spreadsheet_id_or_url`, `sheet_name`, `ranges`
- `notion` (optional): `workspace_or_search_scope`, `page_ids_or_urls`
- `github` (optional): `owner`, `repo`

Per-invocation context (supplied in the engineer's prompt, not in `.ai_helper.md`):
- `branch_set`: comma-separated list of branches (e.g., `ps-8.0,ps-8.4,ps-9.x`)
- `target_branch`: the branch to process in this invocation
- `github.ref`: the git ref or branch to start from

Behavior on missing/incomplete `.ai_helper.md`:
- Do not guess branch sets or target branches.
- Notify engineer about missing fields.
- Continue with available context and ask the engineer to confirm the scope.

## GCA Sync Artifact Set

### Phase 1 — Missing-Commit Map (before any sync actions)

For each sync run, create:
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/missing_commit_map.md`
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/evidence.md`
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/decision.md`

### Phase 2 — Verification Plan and Execution Report (after sync action approval)

Add:
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/verification_plan.md`
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/execution_report.md`

### Phase 3 — Parity Plan and Reports (after verification approval)

Add:
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/parity_plan.md`
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/verification_report.md`
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/parity_execution_report.md`
- `.gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/gca_sync_status.md`

Use UTC timestamp format `YYYYMMDDTHHMMSSZ`, the `<commit_hash>` from `git rev-parse --short=12` of the first commit in the missing-commit map, and snake_case `short_context`.
If the run folder already exists, append `_01`, `_02`, and so on until unique.

## Workflow (Step-by-step)

### 1) Initialize context and access

- Activate Serena if available.
- **Read artifact history context**: see `tdd` Step 1. (List subfolders from all 9 artifact folders, skip any that do not exist, sort by name descending, keep the top 300 in session context. Read folder contents reactively — only when a folder name seems relevant to the current problem.)
- Read `.ai_helper.md` for branch set, target branch, tracking sheet reference, and optional external source pointers.
- If `.ai_helper.md` is incomplete, notify engineer and confirm the branch scope before proceeding.
- Identify the target branch for this invocation. Confirm with the engineer if not already specified.
- Set `status = draft` and `phase = 0` in `decision.md`.

### 2) Map cross-branch divergence

- Compare commit ancestry across the branch set to identify three categories of divergence:
  1. **Missing cherry-picks**: commits present in one branch but absent from another, identifiable by equivalent commit message/SHA family
  2. **Null-merge parity gaps**: branches that received null-merges from an upstream that others did not. Detect using `git log --merges --first-parent` and cross-reference with upstream branch tags to identify gaps.
  3. **Semantic drift candidates**: commits with similar subject but different content across branches
- Use git log, git branch, git merge-base, and GitHub commit history as primary sources.
- To establish commit equivalence across branches, use: (1) commit subject line match, (2) author + author-date match, (3) diff content similarity. Cross-reference with Percona's commit equivalence records if available (e.g., tracking sheet).
- Consult the innovation-branch tracking sheet and merge tracking sheet for prior sync context.
- Record each identified divergence in `missing_commit_map.md` with: commit SHA, subject, author, date, affected branches, proposed sync action (cherry-pick / null-merge / skip / manual), and rationale.

### 3) Build missing-commit map and sync plan

- Based on the divergence analysis, create `missing_commit_map.md` with:
  - The target branch and reference branches
  - Each missing commit entry (SHA, subject, author, date, affected branches, proposed action, rationale)
  - A rank-ordered sync priority (e.g., critical security fixes before cosmetic changes)
  - Open questions and decision criteria for the engineer
- Create `evidence.md` with git log snippets, merge-base output, and SHA equivalence comparisons supporting each map entry. Required minimum fields per entry: commit SHA, source branch, date fetched, relevant snippet, divergence category label (e.g., `D1-missing-cherry-pick`, `D2-null-merge-gap`).
- In `decision.md`, record:
  - `status` (`draft`, `map_approved`, `verification_approved`, `parity_approved`, `completed`, `escalated`, `rejected`, `paused`, `requires_handoff`, `requires_retrigger`) — `rejected` and `escalated` are terminal states; `paused` signals engineer unavailability — on re-invocation, read `decision.md` to identify the active phase and resume at the corresponding gate; `requires_handoff` is set when a sync action hits a file-level conflict and the skill hands off to `percona_conflict_resolution_tdd`; `requires_retrigger` is set when an infrastructure error prevents sync execution — the workflow resumes from step 6 on re-invocation; `map_approved`, `verification_approved`, and `parity_approved` are per-gate approval indicators
  - `approver` — name or GitHub handle of the engineer who provided explicit approval
  - `phase` — which phase the workflow is in (0: pre-map, 1: map, 2: verification, 3: parity). `phase` is a gate counter: it increments to `1` on map gate approval, `2` on verification gate approval, `3` on parity gate approval. A phase value indicates the highest gate the engineer has approved entry to. (`phase = 2` means the engineer has approved the map gate and the verification gate is in progress.)
  - `branch_set` — the branches in scope for this run
  - `target_branch` — the branch being synchronized in this run
  - `divergence_summary` — count of missing commits, null-merge gaps, and semantic drift candidates
  - `notes`

### 4) Review missing-commit map with Lad

- Run Lad `system_design_review` on `missing_commit_map.md`, `evidence.md`, and `decision.md`.
- Apply worthwhile feedback until no material issues remain. Maximum `max_review_cycles` (default `3` per gate) review rounds per approval gate; after this many cycles without approval, summarize the current state, open issues, and remaining options and ask the engineer for a definitive decision. A single cycle is one Lad review + one round of revisions (whether triggered by Lad or by the engineer). Engineer-requested revisions without an intervening Lad review also count as a cycle.
- If Lad flags an issue and the engineer disagrees, engineer approval takes precedence; document the disagreement in `decision.md` notes and proceed if the engineer confirms.

### 5) Phase 1 — Engineer approves missing-commit map

- Present reviewed `missing_commit_map.md` and `evidence.md`.
- Ask for explicit approval before executing any sync actions.
- If changes are requested, revise artifacts and repeat step 4. After `max_review_cycles` revision rounds without approval, summarize the current state, open issues, and remaining options and ask the engineer for a definitive decision.
- If the engineer declines to approve, set `status = rejected` in `decision.md` and exit.
- If the engineer becomes unavailable mid-gate and explicitly requests a pause, set `status = paused` in `decision.md`. On re-invocation, resume at the same gate with all prior approvals preserved.
- On approval, set `status = map_approved`, `phase = 1` in `decision.md` and proceed to step 6.

### 6) Execute approved sync actions

- Execute only the cherry-picks and null-merges approved in the missing-commit map.
- If a sync action hits a file-level conflict:
  - Verify `percona_conflict_resolution_tdd` exists in `solution/skills/` before attempting handoff. If unavailable, set `status = escalated` and notify the engineer.
  - Set `status = requires_handoff` in `decision.md`.
  - Record the conflict details in `evidence.md`.
  - Hand off to `percona_conflict_resolution_tdd` for that conflict.
  - After the conflict is resolved and the skill is re-invoked: skip directly to checking remaining approved sync scope — do not re-enter the conflict/infrastructure conditionals. Verify the target branch state is consistent, and continue executing the remaining approved sync actions. Do not re-execute already-completed actions.
- If a sync action fails due to an unrecoverable infrastructure error (e.g., git push rejected, auth failure), set `status = requires_retrigger` in `decision.md`, record the error in `evidence.md`, and stop — re-invoke once the system is restored. Prior approvals are preserved; resume at step 6.
- Record each executed sync action in `execution_report.md`: action type, target commit, result, any conflicts encountered.
- After all approved sync actions are executed or after returning from a conflict handoff:
  - If sync scope is complete (all approved actions executed): set `status = map_approved` in `decision.md`; proceed to step 7.
  - If sync scope is incomplete (handoff or infrastructure error): stop; the workflow will be re-invoked or will continue from the handoff return.

### 7) Phase 2 — Prepare and execute verification

- Only enter this step after all approved sync actions are executed or after returning from a conflict-resolution handoff.
- Prepare `verification_plan.md` defining how to verify each sync action was applied correctly:
  - Per-action verification (cherry-pick applied: confirm commit SHA present in target branch log; null-merge confirmed: verify `git merge-base <target_branch> <upstream_ref>` matches the expected null-merge base tag)
  - Read-only verification if the sync scope warrants it: check existing build status or prior Jenkins run results for the target branch (do not trigger new jobs from this skill)
  - Evidence required to confirm each action is applied and correct
- Run Lad `system_design_review` on `verification_plan.md` and `execution_report.md`.
- Apply worthwhile feedback. After `max_review_cycles` review rounds without resolving material issues, note remaining flags in `decision.md` and present to the engineer.
- Present to engineer for explicit approval (Phase 2 gate).
- On approval, set `status = verification_approved`, `phase = 2` in `decision.md`.
- Execute approved verification (git log confirmation, consult existing build results for the target branch).
- Write `verification_report.md` with: per-action verification outcomes, build/test results, pass/fail summary, and any residual divergence that requires manual review.
- If verification reveals an inconsistency (sync action was not applied correctly): set `status = escalated` in `decision.md`; present the inconsistency and escalate to step 9.
- If verification confirms all sync actions were applied correctly: set `status = verification_approved`, `phase = 3` in `decision.md`; proceed to step 8. Phase = 3 indicates the verification gate passed and parity work is next.

### 8) Phase 3 — Prepare and execute parity updates

- Prepare `parity_plan.md` defining how to confirm cross-branch semantic equivalence after sync:
  - Cross-branch diff review for the synchronized commits
  - Identification of any residual delta (commits that cannot be mechanically synced and require manual decision)
  - Recommended actions for each residual delta (cherry-pick, skip, or escalate to engineer)
- Run Lad `system_design_review` on `parity_plan.md` and `verification_report.md`.
- Apply worthwhile feedback. After `max_review_cycles` review rounds, note remaining flags in `decision.md` and present to engineer.
- Present to engineer for explicit approval (Phase 3 gate).
- On approval, set `status = parity_approved`, `phase = 3` in `decision.md`.
- Execute approved parity actions (if any mechanical parity updates are within scope and approved).
- Write `parity_execution_report.md` with: parity actions executed, residual deltas identified, engineer-decision items.
- Write `gca_sync_status.md` as a local artifact summarizing the sync outcome: target branch, commits synchronized, verification result, residual deltas, date. This is the record the engineer uses to sync to external tracking systems.
- Set `status = completed` in `decision.md`.
- Present the completed artifacts to the engineer and confirm completion.

### 9) Handoff or escalate

- If the workflow reached an inconclusive or escalated state:
  - Update `decision.md` with `status = escalated` if not already set.
  - Present `missing_commit_map.md` (with current state), `evidence.md`, `execution_report.md` (if applicable), and the specific open questions.
  - A good Ask is structured as: "To proceed, I need: [1] <decision on residual delta>, [2] <confirmation on approach A vs B>, [3] <any additional context>."
  - Request explicit engineer direction.
- If the workflow completed (`status = completed`):
  - Present `gca_sync_status.md`, `verification_report.md`, and `parity_execution_report.md`.
  - If residual deltas require manual decisions, present them to the engineer for priority ordering.
  - Confirm completion to the engineer.

## Handoff Rules

- If a cherry-pick or null-merge hits a file-level conflict: hand off to `percona_conflict_resolution_tdd`. After the conflict is resolved, return to step 6 to continue the remaining approved sync scope.
- If verification surfaces deterministic failing tests: hand off to `percona_mtr_remediation_tdd`. After the fix is understood, return here to assess whether the sync state requires updating.
- If verification surfaces build or sanitizer fallout: hand off to `percona_asan_build_remediation_tdd`.
- If parity updates require fresh implementation work beyond the approved mechanical sync scope: fall back to the baseline `tdd` skill for that implementation task.
- If multiple handoff targets apply, present all applicable ones to the engineer for priority ordering. Verify each target exists in `solution/skills/` before presenting it; if a target is unavailable or is the current skill, exclude it and notify the engineer.

## Workflow Outputs

Expected outputs:
- Lad-reviewed and engineer-approved missing-commit map with sync priorities.
- Execution report tracing all sync actions taken.
- Verification report confirming correct application of each sync action.
- Parity execution report with residual delta closure.
- Completed `gca_sync_status.md` ready for engineer to sync to external tracking systems.

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
  :Confirm branch scope with engineer;
endif

:Set status = draft, phase = 0 in decision.md;
:Identify target branch for this invocation;

:Map cross-branch divergence;
:Compare commit ancestry across branch set;
:Identify missing cherry-picks, null-merge gaps, semantic drift;

:Create .gca_sync/<YYYYMMDDTHHMMSSZ>_<commit_hash>_<short_context>/;
:Write missing_commit_map.md + evidence.md + decision.md;

repeat
  :Run Lad system_design_review on map artifacts;
  :Apply useful plan feedback;
repeat while (More useful plan feedback?) is (yes)

:Present reviewed missing_commit_map.md to engineer;
if (Engineer requests changes?) then (yes)
  :Update map artifacts;
  repeat
    :Run Lad system_design_review on updated artifacts;
    :Apply useful plan feedback;
  repeat while (More useful plan feedback?) is (yes)
endif
repeat while (Engineer approves missing-commit map?) is (no)

:Set status = map_approved, phase = 1 in decision.md;

:Execute approved cherry-picks and null-merges;

if (Sync action hits file-level conflict?) then (yes)
  :Check percona_conflict_resolution_tdd exists in solution/skills/;
  :Set status = requires_handoff in decision.md;
  :Record conflict in evidence.md;
  :Hand off to percona_conflict_resolution_tdd;
  :**On return: skip to check remaining sync scope**;
  note right: Do not re-enter conflict/infra conditionals;
else (no)
endif

if (Sync action fails due to infrastructure error?) then (yes)
  :Set status = requires_retrigger in decision.md;
  :Record error in evidence.md;
  :Stop — re-invoke when system restored;
  stop
else (no)
endif

:Write execution_report.md;
if (All approved sync actions executed?) then (no)
  :Stop — re-invoke or continue from handoff return;
  stop
else (yes)
endif

:Set status = map_approved in decision.md;

:Prepare verification_plan.md;
:Run Lad system_design_review on verification_plan.md + execution_report.md;
:Present to engineer for Phase 2 approval;

if (Engineer approves verification plan?) then (no)
  :Set status = rejected in decision.md;
  stop
else (yes)
endif

:Set status = verification_approved, phase = 2 in decision.md;
:Execute approved verification;

:Write verification_report.md;

if (Verification reveals inconsistency?) then (yes)
  :Set status = escalated in decision.md;
  :Present inconsistency to engineer;
  :Stop — escalate;
  stop
else (no)
endif

:Set status = verification_approved, phase = 3 in decision.md;

:Prepare parity_plan.md;
:Run Lad system_design_review on parity_plan.md + verification_report.md;
:Present to engineer for Phase 3 approval;

if (Engineer approves parity plan?) then (no)
  :Set status = rejected in decision.md;
  stop
else (yes)
endif

:Set status = parity_approved, phase = 3 in decision.md;
:Execute approved parity actions;

:Write parity_execution_report.md;
:Write gca_sync_status.md;
:Set status = completed in decision.md;

:Present completed artifacts to engineer;
:Confirm completion;
stop
@enduml
```

## Usage Examples

```text
Map the missing commits across the selected GCA branch set, prepare a reviewed sync plan, and execute only the approved sync actions. Follow $percona_gca_sync_tdd.
```

```text
Prepare the verification plan and parity-check plan for the current GCA checkpoint, then execute only the approved verification and parity actions. Follow $percona_gca_sync_tdd.
```

## Serena memories (when supported)

Store useful GCA sync knowledge for future tasks:
- commit equivalence heuristics across Percona branches (how to identify the same logical commit in different branch contexts),
- null-merge parity patterns and detection methods,
- common residual delta categories and how they were resolved,
- Jenkins verification job mappings per branch.
