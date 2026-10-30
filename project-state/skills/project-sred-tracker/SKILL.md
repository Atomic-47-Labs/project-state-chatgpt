---
name: project-sred-tracker
description: "Capture SR&ED work as it happens — 'log an uncertainty', 'record this experiment', 'we learned X', 'SR&ED note'. Records uncertainties, experiments, advancements and evidence for the T661."
metadata:
  map:
    tier: capability
    stage: keep
    requires: [memory]
    reads: [sred, log]
    writes: [sred]
    produces: [t661-narrative]
---

# Project SR&ED Tracker

> **When to use — full trigger description.** The frontmatter carries a short, trigger-first
> description so all of the suite's skills fit Claude Code's skill-listing budget (see
> docs/SKILL-SPEC.md, *Description budget*). The complete version, kept here:
>
> Continuous SR&ED work capture for Canadian T661 claims. Records technological uncertainties (TUs), experiments (EXs), technological advancements (ADVs), and contemporaneous evidence entries into sred/ substrate. Enforces TU→EX→ADV traceability. Runs gap analysis, weekly progress digests, quarterly completeness reviews, cost roll-ups, and the innovation-criteria interview. Active when the sred capability is enabled. Use whenever the user says 'record a technical uncertainty', 'log SR&ED work', 'add an experiment', 'capture an advancement', 'SR&ED evidence', 'what's our SR&ED status', 'weekly SR&ED update', 'SR&ED digest', 'quarterly SR&ED review', 'gap analysis', 'define innovation criteria', 'what counts as innovation here', 'is this SR&ED', 'evaluate this SR&ED opportunity', 'screen this for SR&ED', or any request to track or screen experimental development work for CRA.

## Purpose

Capture SR&ED-eligible work at the time it happens — not reconstructed at year-end. Every T661 claim is strengthened or weakened by the quality and timing of the underlying records. This skill is the substrate interface for all SR&ED entities in `project-state/sred/`.

The three entity types map directly to T661 sections:
- **Technological Uncertainties (TU)** → Section E [242]
- **Experiments / Work Streams (EX)** → Section F [244]
- **Technological Advancements (ADV)** → Section G [246]

Plus the **evidence log** (`sred/evidence-log.ndjson`) — the contemporaneous record that CRA may request in an audit.

**Design principle:** capture at the time of the work. A TU record created before the experiment is far more defensible than one backdated to match the T661. The evidence log is append-only and timestamped.

## Trigger phrases

- "record a technical uncertainty" / "we have an SR&ED uncertainty"
- "log SR&ED work" / "capture experiment" / "add a work stream"
- "we found an advancement" / "record a technological advancement"
- "SR&ED evidence entry" / "log this work for SR&ED"
- "what's our SR&ED status" / "quarterly SR&ED review"
- "SR&ED gap analysis" / "are we ready for the T661"
- "how much SR&ED work have we captured"
- "confirm the SR&ED evidence" / "go through the SR&ED inbox" / "reject that proposal"
- "update TU-02" / "correct the date on EX-01" / "mark EX-03 complete"
- "roll up SR&ED costs" / "reconcile the cost worksheet" / "move FY2026 to costing"
- Any milestone completion that involved experimental development

## Entity schemas

### Technological Uncertainty — `sred/uncertainties/TU-NN-<slug>.yaml`

```yaml
schema_version: 1
entity: "technological_uncertainty"
id: "TU-01"
slug: "tenant-isolation-enforcement"

# CRA Section E language
uncertainty_statement: |
  It was uncertain whether... [complete statement in CRA-preferred language]
standard_practice_gap: |
  No established method was identified for... [why existing tools/knowledge didn't apply]

# Classification
uncertainty_type: "software_engineering"  # or: materials, process, other
field_of_science: "2.02.09"               # CRA code

# Traceability
linked_experiments: []      # EX-NN IDs — populated as experiments are created
linked_milestones: []       # which project milestones involve this uncertainty

# Timing (critical for CRA)
identified_date: "YYYY-MM-DD"    # when the uncertainty was first documented — before work began
work_start_date: "YYYY-MM-DD"    # when experimental work started
work_end_date: ~                  # when resolved (or null if ongoing)
fiscal_year: "YYYY"

# Status
status: "active"    # active | resolved | removed
resolution: ~       # if resolved: brief statement of how uncertainty was resolved

# Meta
created_by: "<actor>"             # the person, per project-state "Who the actor is"
last_modified: "YYYY-MM-DDThh:mm:ssZ"
revisions: []       # written by update_record: {at, by, fields, reason, prior} — on EX and ADV too
```

### Experiment / Work Stream — `sred/experiments/EX-NN-<slug>.yaml`

```yaml
schema_version: 1
entity: "experiment"
id: "EX-01"
slug: "schema-policy-enforcement-trials"

# CRA Section F language
linked_tu: "TU-01"
hypothesis: |
  Whether [specific technical outcome] could be achieved by [approach] under [constraints].
method_and_trials: |
  [Describe what was done: implementations attempted, tests run, architectures tried.
   Include failures, iterations, and what changed between attempts.]
observations_and_results: |
  [What was observed: measured results, failure modes, unexpected constraints,
   non-obvious findings. If an initial assumption failed, say so explicitly.]
limitations: |
  [What remained unresolved or required further work]

# Evidence references (pointers to contemporaneous records)
evidence_records:
  - type: "code_commit"         # code_commit | meeting_note | test_output | email | design_doc | other
    reference: "TODO"           # commit hash, file path, meeting date, etc.
    date: "YYYY-MM-DD"
    description: "TODO"
  - type: "test_output"
    reference: "TODO"
    date: "YYYY-MM-DD"
    description: "TODO"

# Cost allocation basis (for cost-categorization.yaml)
people_involved:
  - name: "TODO"
    role: "TODO"
    eligible_days: 0    # approximate days of eligible work on this experiment

# Traceability
linked_advancements: []   # ADV-NN IDs — populated when ADVs are created
linked_milestones: []

# Timing
start_date: "YYYY-MM-DD"
end_date: ~
fiscal_year: "YYYY"

# Status
status: "in_progress"  # in_progress | complete | abandoned
abandonment_reason: ~  # if abandoned: why

# Meta
created_by: "<actor>"             # the person, per project-state "Who the actor is"
last_modified: "YYYY-MM-DDThh:mm:ssZ"
```

### Technological Advancement — `sred/advancements/ADV-NN-<slug>.yaml`

```yaml
schema_version: 1
entity: "technological_advancement"
id: "ADV-01"
slug: "cross-layer-authorization-knowledge"

# CRA Section G language
linked_tu: "TU-01"
linked_experiments: ["EX-01"]
advancement_statement: |
  The work established that... [knowledge gained, not product delivered]
knowledge_gained: |
  [More detailed description of what is now known that was not known before.
   Be proportionate: don't claim broader knowledge than the experiments support.]

# Proportionality check (internal — not filed)
proportionality_note: |
  [Internal note: does this advancement match the scope of the linked experiment's results?
   If the experiment was narrow, the advancement should be narrow too.]

# Timing
established_date: "YYYY-MM-DD"  # when the advancement was achieved / knowledge confirmed
fiscal_year: "YYYY"

# Meta
created_by: "<actor>"             # the person, per project-state "Who the actor is"
last_modified: "YYYY-MM-DDThh:mm:ssZ"
```

### Evidence Log Entry — appended to `sred/evidence-log.ndjson`

```json
{
  "date": "YYYY-MM-DD",
  "timestamp": "ISO8601",
  "entry_type": "experiment|test|failure|iteration|advancement|meeting|publication",
  "tu_id": "TU-01",
  "ex_id": "EX-01",
  "adv_id": null,
  "description": "Brief contemporaneous description of what was done/found",
  "people": ["Name"],
  "milestone_id": "M03",
  "record_type": "code_commit|meeting_note|test_output|email|design_doc",
  "record_reference": "commit abc123 / path/to/file / meeting YYYY-MM-DD",
  "logged_by": "name",
  "logged_at": "ISO8601"
}
```

## Operations

### `record_uncertainty(fields)` — also answers to `record_tu`

Create a new TU-NN record. `record_tu` is the same operation under its short name (the
app's SR&ED starter prompt uses it). Required fields:
- `uncertainty_statement` — in CRA-preferred language ("It was uncertain whether...")
- `standard_practice_gap` — why existing knowledge didn't resolve it
- `identified_date` — ideally before experimental work begins
- `field_of_science` — CRA code
- `linked_milestones` — which project milestones involve this uncertainty

Enforce: if `identified_date` is after any linked experiment's `start_date`, warn — this is a backdating risk.

### `record_experiment(fields)`

Create a new EX-NN record. Required fields:
- `linked_tu` — must reference an existing TU-NN
- `hypothesis` — what was being tested
- `method_and_trials` — what was done (ask for this if not provided)
- `observations_and_results` — what was found
- `evidence_records` — at least one

Enforce: if `observations_and_results` is empty or sounds like pure feature delivery, warn and ask for more detail. The result must include at least one of: failure, limitation, unexpected finding, iteration, refinement.

Automatically append an entry to `sred/evidence-log.ndjson`.

### `record_advancement(fields)`

Create a new ADV-NN record. Required fields:
- `linked_tu` — must reference an existing TU-NN
- `linked_experiments` — must include at least one EX-NN
- `advancement_statement` — in CRA-preferred language ("The work established that...")

Enforce:
- Advancement must be proportionate to the linked experiments' observed results
- Language must describe knowledge gained, not product delivered
- Flag any risky language from the pack profile's `risky_language_patterns` list

### `log_evidence(fields)`

Append one entry to `sred/evidence-log.ndjson`. This is the lightweight daily capture:
```
"log SR&ED work on EX-01 today — tested three token-handling approaches, two failed"
→ append evidence entry with today's date, description, EX-01 link
```

Minimal required fields: `date`, `tu_id` or `ex_id`, `description`, `people`.

**Evidence source tiers** (schema `evidence_source_tiers`): tier-1 records (commits,
test outputs, Jira issues/worklogs, Confluence page versions, repo-versioned design
docs) stand as primary evidence — cite the durable reference (issue key,
`<page-id>@<version>`). Tier-2 records (Slack, Google Docs, meeting notes, email)
corroborate only and MUST carry a verbatim `excerpt` plus permalink captured at log
time — the source may be edited or deleted later; the excerpt is what survives.
When an EX's evidence is entirely tier-2, say so at capture time and suggest a
tier-1 anchor (file the finding as a Jira comment, commit the note to the repo).

Evidence proposed by the harvester does not come through here; it waits in `sred/inbox/`
for `confirm_evidence` below.

### `update_record(id, changes, reason)`

Revise a TU, EX or ADV that is already on file: a back-filled TU sharpened once the
experiments land, a date corrected toward a server-timestamped source, an EX marked
complete, a statement narrowed for proportionality. Records are edited in place; the trail
lives on the record and in the activity log, so nothing about the revision is hidden.

1. Read the record. Refuse an `id` that does not exist, and refuse changes to `id`,
   `entity`, `created_by` or `schema_version`.
2. `reason` is required: one plain sentence in the user's words ("TU-02 restated after
   EX-03 showed the bottleneck is the merge, not the parse"). Do not write it for them.
3. Apply `changes` and append one entry to the record's `revisions:` list (create it if
   absent): `{at: <ISO8601>, by: <actor>, fields: [<changed field names>], reason, prior:
   {<field>: <old value>}}`. Keep `prior` for every changed field, so the record shows what
   it said before.
4. Re-run the checks the create operation runs. On a TU, moving `identified_date` later
   than a linked EX's `start_date`, or earlier at all, is a backdating question: show the
   old and new dates and the linked EX dates, and proceed only on the user's explicit yes.
   Never move `identified_date` earlier to tidy a chain; correct toward the source record
   or leave it.
5. Status changes use the same operation: a TU to `resolved` (with `resolution`) or
   `removed`, an EX to `complete` or `abandoned` (with `abandonment_reason`).
6. Emit `sred.tu.updated` / `sred.ex.updated` / `sred.adv.updated` with `{id, fields,
   reason}`. A TU reaching `resolved` also emits `sred.tu.resolved`; an EX reaching
   `complete` also emits `sred.ex.completed`. Then `render_dashboard()`.

Evidence-log entries are never edited: a correction to logged evidence is a new
`log_evidence` entry that says what it corrects (`corrects: <timestamp of the entry>`).

### `confirm_evidence(stub, decisions?)`

Promote a harvester proposal from `sred/inbox/` into the evidence log. This is the human
decision the harvester is never allowed to make: run it only on the user's say-so, one stub
(or one cluster) at a time, or over a list the user has gone through and approved.

1. Read the stub. Show the user what it says, its source, and the EX (or TU) it suggests.
   The link is the user's call: `suggested_ex` is a suggestion. A stub with no EX or TU to
   link to cannot be confirmed; offer `record_uncertainty` / `record_experiment` first, or
   leave it in the inbox.
2. **Single stub** (`{date, source: {surface, ref}, suggested_ex, tier?, description_draft,
   excerpt?, people}`): append ONE entry with `log_evidence`'s shape plus
   `entry_type: harvested`, `source: {surface, ref}`, `record_reference: <source.ref>`,
   `record_type` from the source, `date` = the source's own date (the date of the work,
   never today), `description` = `description_draft` as written or as the user edits it,
   and `excerpt` carried over. Tier-2 stubs without an `excerpt` cannot be confirmed:
   capture the verbatim excerpt and permalink first.
3. **Cluster stub** (`{suggested_ex, records: [...], window, corroboration}`): one
   decision, one entry per record. Each entry carries `corroborated_by:` listing the
   other records in the cluster (`{record_type, reference}`), and the cluster's earliest
   source timestamp is reported to the user. **Date corroboration:** if that earliest
   timestamp predates the linked TU's `identified_date` or EX's `start_date`, surface it —
   either the dates need correcting toward the (defensible, server-timestamped) source
   record, with `update_record`, or the work predates the declared uncertainty and the
   framing needs an honest look. Do not confirm past it silently.
4. Set `backfilled: true` on any entry whose `logged_at` is more than 7 days after its
   `date` (spec §4.4). Harvested evidence confirmed late is still back-filled.
5. If the confirmed entry evidences an EX, add its reference to that EX's
   `evidence_records` (type, reference, date, description), so the EX cites it.
6. Delete the stub from `sred/inbox/`. Emit `sred.evidence.logged` once per entry
   appended, with `{ex_id, tu_id, source}`. Then `render_dashboard()`.

`decisions` lets a user who has reviewed a batch confirm it in one go:
`[{stub, link: EX-NN, description?}]`. Every stub in the batch is still shown before it is
written; the batch saves typing, not judgment.

### `reject_evidence(stub, reason)`

The other answer to a proposal. Delete the stub and emit `sred.evidence.rejected` with
`{stub, source, reason}`, so the proposal/confirmation ratio the quarterly review reports
stays countable. A stub the user wants to keep thinking about stays in `sred/inbox/`
untouched (a `triage:` block on the stub records the thinking, as the dogfood inbox does).

### `rollup_costs(fy)`

The reconciliation beneath the FY cost worksheet (spec §6.4). The worksheet is the
human's document; this operation never writes a line in it.

1. Find the worksheet `sred/cost-tracking/<FY>-costs.yaml`. If it does not exist, create it
   from `templates/entities/FY-costs.yaml` with `fiscal_year` and `fy_end` filled in (from
   `state/sred.json → fiscal_years.<FY>`) and the three category lists empty, and tell
   the user the worksheet is theirs to fill.
2. Collect every EX whose `claim_fy` is the FY (fall back to `fiscal_year` on records that
   predate `claim_fy`, and say so). Sum `people_involved[].eligible_days` per person, with a
   per-EX breakdown.
3. Write ONLY the `rollup:` block: `generated_at`, `per_person: [{person,
   eligible_days_total, by_experiment: {EX-NN: days}}]`, and `discrepancies:`. Leave
   `eligible_experimental`, `partially_eligible_support` and `non_eligible_routine` as
   they are, byte for byte.
4. Discrepancies, one line each with the people and EX ids named:
   - a person with eligible days on EXs who appears in no worksheet line;
   - a person whose worksheet days (eligible plus partially eligible) exceed their
     rolled-up days;
   - an EX with zero eligible days whose id appears in a worksheet line's `linked_ex`;
   - an EX in the FY with no `people_involved` at all.
5. Report the totals and the discrepancies to the user. Do not resolve a discrepancy by
   editing either side; each is a question for the person who owns the worksheet.
6. Emit `sred.costs.rolled-up` with `{fy, people, eligible_days_total, discrepancies}`.

Run it whenever the worksheet or an EX's `people_involved` changes during cost
categorisation, and before `claim_status(fy, drafting)`.

### `claim_status(fy, status)`

Record a claim-status transition in `state/sred.json → fiscal_years.<FY>.claim_status`
(under its advisory lock): `capturing → costing → drafting → in-review → advisor-handoff →
filed | waived | forfeited`. Only the user moves a claim to `filed` or `waived`; the system
never files. Moving to `drafting` with unresolved `rollup_costs` discrepancies is allowed
but named. Emit `sred.claim.status-changed` with `{fy, from, to}`. A fiscal year not yet in
`fiscal_years` (back-capturing a prior year) is added with its `fy_end`, derived from
`capabilities.sred.fiscal_year_end`, at `capturing`; its deadlines are left for the
automation layer to compute, as for every FY (spec §6.1).

### `gap_analysis()`

Run the validator first and build on what it finds; do not re-derive by hand what it already
checks:

```bash
python3 capabilities/sred/validator/scripts/check.py <facility>/project-state --json
```

(In an installed plugin: `<plugin>/capabilities/sred/validator/scripts/check.py`.) It reads only.
Every `fail` goes into the gap list as High, every `warn` at the severity of the matching row
below (Medium where no row matches), each with its rule id and file. If Python or PyYAML is
missing it exits 2 — say so in the report and fall back to the table below by reading.

Then scan all TU/EX/ADV records and evidence log for the judgement gaps the script cannot see:

| Check | Risk if failed |
|-------|---------------|
| TU with no linked EX | High — uncertainty without investigation |
| EX with no linked TU | High — work without a declared uncertainty |
| EX with no evidence_records | High — no contemporaneous records |
| EX with no observations_and_results | High — no documented outcome |
| ADV with no linked EX | High — advancement without experimental basis |
| TU identified after EX start_date | Medium — backdating appearance |
| EX completed >90 days ago with no ADV | Medium — work without declared knowledge gain |
| Evidence log entry gap >30 days for active EX | Medium — stale capture |
| Milestone with experimental description and no linked TU | Medium — potential SR&ED work uncaptured |
| Work landed in a declared candidate uncertainty area (sred/criteria.yaml) with no TU on file | High — the criteria say this is frontier work and nothing was captured |
| High-activity correlation cluster (Jira/GitHub/Confluence joined) with no linked EX | High — the cohort found a work thread nothing claims |
| EX evidenced by a single source type | Low — suggest corroborating from the cohort (linked issue, build, page) while records are fresh |
| Cluster's earliest source timestamp predates linked TU identified_date / EX start_date | Medium — dates need correcting toward the server-timestamped record, or the framing needs review |
| Criteria status still `draft`, or last_refreshed older than 2 quarters | Low — capture lens going stale |

Return a prioritized gap list with recommended actions and deadlines.

### `quarterly_review()`

Run `gap_analysis()` and produce a structured quarterly review report:
1. SR&ED substrate summary: TU count, EX count, ADV count, evidence log entry count
2. Completeness gaps (from gap_analysis), opening with the validator's counts (`N fail(s),
   M warning(s)`) and every `fail` listed by rule id, file and entity
3. Cost allocation status: are people's time entries current?
4. 18-month deadline status: days remaining per fiscal year
5. Milestones completed since last review — any experimental work uncaptured?
6. Recommended actions before next quarter

Save to `reports/adhoc/sred-quarterly-YYYY-QN.md`. Offer to route to SR&ED lead via `project-notifier`.

### `traceability_map()`

Generate the full uncertainty → experiment → advancement chain for a given fiscal year:

```
TU-01 → EX-01 → ADV-01  ✓ complete
TU-01 → EX-02 → (no ADV) ⚠ advancement missing
TU-02 → (no EX) ✗ no experimental work recorded
```

Used as input to the evidence-map template and T661 narrative generation.

### `milestone_sred_check(milestone_id)`

Fired via the `sred.evidence-capture` matrix entry on `milestone.completed`. Asks:
- Does this milestone involve any experimental development? **Test against the criteria
  layers first** (`sred/criteria.yaml` candidate areas and declared-routine list, then the
  company Layer 1 — `sred/company-criteria.yaml`, else a forked pack's filled
  `innovation-criteria` profile; a blank template means no company lens, so say so): a
  milestone linked to a candidate area is
  presumed to need a TU; one squarely in declared-routine is presumed not to, and says so.
- If yes: are TU/EX records current?
- If no TU exists for this milestone: suggest creating one or confirming SR&ED non-applicability

### `evaluate_opportunity(subject)`

Screen any piece of work — a milestone, a Jira epic or issue, a Confluence design page,
a proposal, an idea in chat — through the evaluation ladder. Four rungs, in order, each
capable of ending the evaluation:

1. **Routine check** (project criteria). Is the subject squarely inside
   `declared_routine`? → verdict **routine**: say so, offer to record a one-line
   non-applicability note, stop. No CRA framing wasted on CRUD.
2. **Frontier check** (project + company criteria). Does it land in a
   `candidate_uncertainty_areas` entry, or fall outside the company
   `technology_baseline`? Landing in a declared area = strong candidate; outside both
   lists = evaluate on the merits at rung 3.
3. **The five questions** (Layer 0, `schema/eligibility-baseline.yaml`). Walk each:
   uncertainty, hypothesis, systematic investigation, advancement sought, records kept.
   Apply the **field-level rule** hard: "no one on our team knew how" is rung-3 failure
   unless it can be honestly reframed as a gap in the field's established practice.
4. **Capture decision.** Verdicts:
   - **capture-now** — knowledge gap is live and work is starting: create the TU
     (`record_uncertainty`) immediately, before the work; link the source (Jira epic,
     Confluence page) as the first evidence record.
   - **watch** — plausibly frontier but not yet concrete: add/extend a candidate area in
     `sred/criteria.yaml` so the harvester and milestone hook watch for it (emits
     `sred.criteria.updated`).
   - **routine** — record the non-applicability decision so the question isn't re-litigated.
   - **borderline** — capture as if eligible (a TU costs one file; a missed TU costs the
     claim) and flag for the advisor. Never resolve borderline toward "skip".

Output: a short screening note (subject, rung reached, verdict, reasoning, action taken).
Verdicts are capture decisions, not eligibility determinations — say so in the note.

### `weekly_digest()`

The weekly capture-discipline instrument (matrix entry `sred.weekly-progress`, Mondays).
NOT a mini-claim — the quarterly review owns completeness and audit posture. Five sections,
half a page:

1. **Captured this week** — new TUs/EXs/ADVs; evidence entries appended, grouped by EX.
2. **Uncaptured but candidate** — through the criteria lens: milestones advanced, commits
   or harvested signals in `candidate_uncertainty_areas` with no TU/EX on file. This
   section cannot exist without `sred/criteria.yaml`; if criteria are missing, say so and
   offer `define_criteria`.
3. **Going stale** — active EXs with no evidence entry in 14+ days.
4. **Inbox** — unconfirmed candidates in `sred/inbox/` (count + oldest).
5. **Deadline line** — per open FY: claim status, days to target and hard deadline,
   current escalation tier.

Save to `reports/adhoc/sred-weekly-YYYY-Wnn.md`; offer routing to the SR&ED lead via
`project-notifier` (Slack). Quiet weeks are reported as quiet — one line per empty
section, never padded.

### `define_criteria()`

Guided interview that authors or refreshes `sred/criteria.yaml` (Layer 2) — ideally with
the SR&ED advisor in the room. Reads the Layer 0 baseline
(`capabilities/sred/schema/eligibility-baseline.yaml`) and the company Layer 1
(`sred/company-criteria.yaml`, else a forked pack's filled `innovation-criteria.yaml`; a
blank template means no company lens — say so, and offer `sred-onboarding`'s company
chapter) first, then walks:

1. **Frontier** — "Where in this project does the field's standard practice run out?" Name
   each candidate uncertainty area (id, label, field-relative description), link milestones.
2. **Routine boundary** — "What is explicitly NOT a candidate here?" Declared-routine list.
3. **Harvester hints** — keywords, repo paths, people whose work is likely eligible.
4. **Confirm framing** — every area description must be field-relative; rewrite any
   "new to us" phrasing on the spot, citing the Layer 0 field-level rule.

Write the file from `templates/criteria.yaml`, `status: draft` until PL sign-off flips it
to `reviewed`. Emit `sred.criteria.updated` with areas added/removed — criteria drift is
audit-relevant and must be visible in the activity log. The quarterly review nudges a
refresh when `last_refreshed` ages past a quarter.

### `render_dashboard()` — the declared report

The SR&ED dashboard is a **declared report** (`capabilities/sred/surfaces.yaml → reports:`): the
app's SR&ED page renders `reports/adhoc/sred-dashboard.html` in place, so it must be fresh
whenever state changes. Run it after every operation above that writes a TU/EX/ADV, appends
evidence, or moves a claim status — and at the end of the weekly and quarterly reviews:

```bash
node capabilities/sred/views/build-sred-dashboard.mjs <facility>/project-state
```

It reads the manifest block, `sred/criteria.yaml`, the three entity directories, the evidence
log and `state/sred.json`; it writes ONE file and nothing else — a lens, never a writer. If Node
is unavailable, say so in the run report instead of leaving a stale page: the app shows the
last render's timestamp, and a stale timestamp is an honest signal. Before the first render (or
when the capability is merely installed) the app shows `samples/dashboard.html`, a fixture
render, banded "Template" — never mistake it for this project's data.

## Discipline rules

- **Capture at the time of the work.** Evidence entries should reference dates contemporaneous with the actual work — not the date they were entered into the system. If an entry is being back-filled, note the distinction.
- **Never invent experiments or results.** If the user provides insufficient detail, ask for it. Do not generate hypotheses or observed results that the user didn't provide.
- **Never imply eligibility certainty.** This skill captures and structures information. Eligibility determinations require a qualified SR&ED consultant. Flag borderline situations clearly.
- **Enforce the traceability chain.** Every ADV must trace to a TU and an EX. The skill will not create an ADV without both links.
- **Proportionality.** Advancement claims must match the scope of the experimental evidence. Warn when an advancement sounds broader than what the linked experiments support.
- **The 18-month deadline is hard.** When it is within 180 days, surface it prominently on every SR&ED interaction.
- **Criteria are a capture lens, never an eligibility argument.** The standard-practice test is field-level; "new to us" is ineligible. Criteria decide what gets recorded and investigated — eligibility framing stays field-relative and the final call is the advisor's.

## Integration

- **project-state** — all writes route through it; TU/EX/ADV are entities like milestones
- **project-milestone-manager** — calls `milestone_sred_check()` on completion; milestones link to TU/EX records
- **project-funder-reporting** — consumes TU/EX/ADV entities to generate T661 narrative via sred-canada pack profile
- **project-sred-reviewer** — receives the T661 draft for audit-risk review before advisor handoff
- **project-orchestrator** — quarterly review triggered via reporting matrix `sred.quarterly-log-review` entry
- **project-change-register** — significant scope changes may affect SR&ED eligibility; flag for advisor review

## Reference schema files

- `packs/sred-canada/templates/t661-narrative.md` — narrative template (Sections E/F/G)
- `packs/sred-canada/templates/evidence-map.md` — evidence map template
- `packs/sred-canada/templates/cost-categorization.yaml` — cost allocation template
- `packs/sred-canada/profiles/funder-reporting.yaml` — language guidance and cadence config
