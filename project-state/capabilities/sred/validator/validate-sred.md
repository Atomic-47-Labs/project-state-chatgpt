# validate-sred — sred capability validator

**The checks are executable:** [`scripts/check.py`](scripts/check.py). This page documents them; the
script's `RULES` table is the source, and `scripts/test-sred.py` fails if a rule id there is missing here.

```bash
python3 capabilities/sred/validator/scripts/check.py <facility>/project-state            # human-readable
python3 capabilities/sred/validator/scripts/check.py <facility>/project-state --json     # for machines
python3 capabilities/sred/validator/scripts/check.py --rules                              # this table, from the script
```

In an installed plugin the same script sits at `<plugin>/capabilities/sred/validator/scripts/check.py`.
Options: `--as-of YYYY-MM-DD` (ages are measured against it; default today), `--strict` (a warning also
exits 1). It reads only — it never writes, fixes or reformats a record. Needs Python 3 and PyYAML; without
PyYAML it says so and exits 2.

Composed with `project-state validate` per `CAPABILITY-PLUGINS.md` §6: runs when the `sred` capability is
enabled, and only reports on records in the `sred` namespace (plus the capability's own block in
`manifest.yaml`). Normative source: `docs/SRED-CAPABILITY-SPEC.md` §7, with §4.2 (traceability), §4.4
(evidence log, back-fill rule), §4.5 (cost worksheets) and §4.7 (runtime state).

## Output

One finding per line: severity (`fail` | `warn`), rule id, file (an evidence-log finding names its line,
`sred/evidence-log.ndjson:12`), entity id, and a one-line message. `--json` gives
`{ok, as_of, enabled, fails, warns, findings: [{severity, rule, path, entity, message}], not_checked}`.

Exit codes follow research's `check.py`: **0** no fails (warnings allowed), **1** at least one fail (or, with
`--strict`, a warning), **2** a usage or input error — no `manifest.yaml`, a bad `--as-of`, PyYAML missing.

Warn items feed the tracker's `gap_analysis()` and the reviewer's audit-risk pass; they are the same rules
at a different enforcement strength.

## The spec §7 checks

| Rule id | Severity | Source | Checks |
|---|---|---|---|
| `schema.parse` | fail | §7 #1 | a TU / EX / ADV / cost / criteria / inbox file that does not parse as a YAML mapping |
| `schema.shape` | fail | §7 #1 | required fields missing or empty, entity kind, status enum, unparseable dates, evidence_records shape |
| `schema.id` | fail | §7 #1 | id not of the form TU-NN / EX-NN / ADV-NN, file name not <id>-<slug>.yaml, or an id used twice |
| `trace.adv` | fail | §7 #2, §4.2 | ADV without ≥1 linked TU and ≥1 linked EX |
| `trace.ex-tu` | fail | §7 #3, §4.2 | EX without exactly one linked TU (missing, a list of several, or claimed by two TUs) |
| `ref.dangling` | fail | §7 #4 | a referenced TU / EX / ADV / milestone id that does not exist (records, criteria, cost worksheets) |
| `evidence.ref` | fail | §7 #5 | an evidence-log entry naming a TU / EX / ADV that does not exist |
| `state.deadline` | fail | §7 #6 | state/sred.json hard_deadline ≠ fy_end + 18 months or target_date ≠ fy_end + 15 months |
| `trace.backdating` | warn | §7 #7 | TU identified_date after a linked EX's start_date (backdating appearance) |
| `ex.no-evidence` | warn | §7 #8 | EX with no evidence_records and no evidence-log entries |
| `ex.no-adv` | warn | §7 #9 | EX completed more than 90 days ago with no linked ADV |
| `ex.evidence-gap` | warn | §7 #10 | active EX whose latest evidence is more than 30 days old |
| `evidence.backfill-share` | warn | §7 #11 | back-filled entries exceed 25% of a fiscal year's evidence |
| `manifest.version` | warn | §7 #12 | the manifest's capabilities.sred.version differs from the installed plugin.yaml version |
| `evidence.backfilled` | fail | §7 #13, §4.4 | entry logged more than 7 days after its date without backfilled: true |
| `inbox.stale` | warn | §7 #14 | a sred/inbox/ stub older than 90 days |
| `criteria.shape` | fail | §7 #15 | criteria.yaml / company-criteria.yaml shape (status, layer, area and routine lists) |
| `criteria.overlap` | fail | §7 #15 | an area listed both as a candidate uncertainty area and as declared routine |
| `criteria.layer0` | fail | §7 #16 | a candidate area naming an activity Layer 0 rules out (phrase match against not_eligible_regardless_of_criteria) |
| `criteria.stale` | warn | §7 #17 | criteria still draft after 90 days, or last refreshed more than two quarters ago |
| `criteria.routine-milestone` | warn | §7 #18 | a TU whose linked_milestones belong to a declared-routine entry |
| `evidence.excerpt` | fail | §7 #19 | tier-2 entry (slack_message, gdoc, meeting_note, email) without a verbatim excerpt and a record_reference |
| `inbox.label-ref` | fail | §7 #20 | a stub carrying a sred-ex-NN / sred-tu-NN label for an entity that does not exist |
| `ex.tier2-only` | warn | §7 #21 | EX whose evidence is entirely tier-2 |
| `evidence.corroborated-by` | fail | §7 #22 | corroborated_by not a list of {record_type, reference}, or naming an unknown record_type |
| `evidence.predates` | warn | §7 #23 | evidence dated before the linked TU's identified_date or the EX's start_date |
| `ex.single-source` | warn | §7 #24 | EX with ≥3 evidence records all of one record type |

## Further checks (schemas, shapes and consistency)

| Rule id | Severity | Source | Checks |
|---|---|---|---|
| `evidence.parse` | fail | §4.4 | an evidence-log line that is not a JSON object |
| `evidence.required` | fail | §4.4, entities.yaml | entry missing date, description, people or logged_at, or naming neither tu_id nor ex_id |
| `evidence.corrects` | fail | tracker update_record | corrects: that matches no other entry's timestamp |
| `evidence.entry-type` | warn | entities.yaml | entry_type outside the vocabulary |
| `evidence.record-type` | warn | entities.yaml | record_type outside the vocabulary (tier 1, tier 2 or other) |
| `evidence.ref-chain` | warn | §4.2 | entry's tu_id differs from its EX's linked_tu |
| `evidence.missing` | warn | §4.1 | the capability is enabled but sred/evidence-log.ndjson does not exist |
| `ref.backlink` | warn | §4.2 | a link recorded on one side only (TU ↔ EX, EX ↔ ADV), or an ADV's EX belonging to another TU |
| `tu.no-ex` | warn | tracker gap_analysis | TU with no experiment |
| `ex.no-results` | warn | tracker gap_analysis | EX with no observations_and_results |
| `costs.name` | warn | §4.5 | a file in sred/cost-tracking/ that is not a <FY>-costs.yaml worksheet (not checked further) |
| `costs.shape` | fail | §4.5, §6.4 | worksheet fiscal_year, category lines and rollup block shape |
| `state.missing` | fail | §4.7 | the capability is enabled but state/sred.json does not exist |
| `state.schema` | fail | §4.7 | state/sred.json does not satisfy schema/state.schema.json |
| `state.fy-end` | fail | §4.7 | a fiscal year's fy_end does not fall on fiscal_year_end, or state and manifest disagree on it |
| `state.fy-key` | warn | §4.7 | fiscal-year key not FY<year of fy_end> |
| `state.counters` | warn | §4.7 | a counter behind the highest id on disk (the next create would reuse an id) |
| `state.deadline-passed` | warn | §4.7 | hard deadline passed and the claim is not filed, waived or forfeited |
| `inbox.shape` | fail | §6.3, entities.yaml | a stub that is neither a single {date, source{surface, ref}, description_draft} nor a cluster {records, window, corroboration} |
| `inbox.ref` | fail | §6.3 | suggested_ex / suggested_tu naming an entity that does not exist |
| `inbox.excerpt` | warn | tracker confirm_evidence | a tier-2 stub or cluster record without an excerpt (cannot be confirmed until captured) |
| `inbox.record-type` | warn | entities.yaml | a cluster record_type outside the vocabulary |
| `inbox.corroboration` | warn | Addendum C | a cluster's corroboration count above its distinct tier-1 record types |
| `fy.format` | fail | §4.2 | claim_fy not FY<year>, or fiscal_year not <year> / FY<year> |
| `fy.mismatch` | fail | §4.2, §12.2 | claim_fy and fiscal_year name different years |
| `fy.missing` | warn | §4.2 | record without claim_fy (predates it; rollup_costs falls back to fiscal_year) |
| `fy.unknown` | warn | §4.7 | claim_fy not in state/sred.json fiscal_years |
| `fy.span` | warn | §12.2 | an EX dated outside its claim year (split it into per-FY EX records) |
| `revisions.shape` | fail | tracker update_record | revisions: entries not {at, by, fields, reason, prior}, or revising a field update_record refuses |
| `review-notes.shape` | fail | §4.2 | review_notes item neither a string nor {date, by, finding, severity, status, resolution} with valid enums |
| `review-notes.incomplete` | warn | §4.2 | a structured note missing date / by, or resolved without a resolution |

## Not checked

- **costs.rollup-preserves-manual** — §4.5 / §6.4: rollup_costs never overwrites manual worksheet lines — a property of a write, not of a snapshot; one copy of the file cannot show what it said before. Not checkable here.
- **criteria.layer0 (judgement)** — §7 #16 is checked by phrase match only; whether a candidate area is in substance routine work is the reviewer's and the advisor's call.
- **criteria.routine-milestone (string entries)** — §7 #18 needs a declared_routine entry that names milestones ({label, linked_milestones}); a plain-string entry carries no link to check.
- **evidence.predates (source timestamps)** — §7 #23 compares each entry's own date, not the server timestamp of the source record behind it — that needs the source.
- **narrative quality** — risky language, proportionality and field-relative framing are project-sred-reviewer's job.

## Reading the findings

- `evidence.backfilled` and `evidence.predates` on a back-filled record are the honest signal the spec
  asks for, not something to tidy away: add `backfilled: true` by appending a correcting entry
  (`corrects:` the original's timestamp) — the log is append-only, entries are never edited.
- `trace.backdating` names a TU identified after its experiment started. Correct the date toward a
  server-timestamped source with `update_record`, or leave it and let the advisor see it; never move
  `identified_date` earlier to tidy the chain.
- A `fail` blocks nothing by itself — the validator reports, people decide. The tracker refuses to
  create records that would break `trace.adv` or `trace.ex-tu`; the validator finds the ones that exist.
