#!/usr/bin/env python3
"""check — the SR&ED capability's executable validator (docs/SRED-CAPABILITY-SPEC.md §7).

    python3 check.py <facility> [--json] [--strict] [--as-of YYYY-MM-DD]     the whole sred namespace
    python3 check.py --rules [--json]                                          the rule table this script enforces

<facility> is a project's `project-state/` folder (or the folder holding it). Composed with the core
validator under validator/validate-sred.md; reads only records in the `sred` namespace and writes nothing.

Every finding carries a severity (fail | warn), a rule id, the file, the entity id and a one-line message.
Exit codes follow research's check.py: 0 no fails (warnings allowed; with --strict a warning also counts),
1 at least one fail, 2 a usage or input error (no manifest, PyYAML missing, bad arguments).

What it checks — the rule ids are the ones validate-sred.md documents (RULES below is the source):
  schema       YAML parse, required fields, ids, file names, enums and dates of TU / EX / ADV records
  trace        ADV → ≥1 TU and ≥1 EX; EX → exactly one TU; every referenced id exists (spec §4.2)
  evidence     the log's required fields, ids, the 7-day back-fill rule (§4.4), tier-2 excerpts, corroborated_by,
               corrects, dates against the TU / EX they evidence, and the back-filled share per fiscal year
  ex           evidence, staleness, advancement and corroboration warnings per experiment
  costs        <FY>-costs.yaml worksheets: shape, fiscal year, linked EX ids, the rollup block's shape
  state        state/sred.json against schema/state.schema.json; computed deadlines; counters
  inbox        single and cluster proposal stubs: shape, links, sred-ex-NN / sred-tu-NN labels, age
  criteria     sred/criteria.yaml and sred/company-criteria.yaml: shape, overlap, Layer 0, staleness
  fy           claim_fy / fiscal_year agreement, and an EX staying inside its claim year
  revisions    the update_record trail on a record
  review-notes string or {date, by, finding, severity, status, resolution}
  manifest     the enabled block's version against this capability's plugin.yaml

Not checked (named in every report under "not checked"): see SKIPPED below.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # the same refusal research gives, with the exit code this script documents
    print("check: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

HERE = Path(__file__).resolve().parent
CAP = HERE.parent.parent  # capabilities/sred (or plugin/capabilities/sred once published)

# ── the rule table ───────────────────────────────────────────────────────────────────────────────
# id: (severity, where it comes from, what it checks). validate-sred.md renders this table; the
# spec's §7 numbering is kept in the second column so the two can be read side by side.
RULES = {
    "schema.parse":            ("fail", "§7 #1", "a TU / EX / ADV / cost / criteria / inbox file that does not parse as a YAML mapping"),
    "schema.shape":            ("fail", "§7 #1", "required fields missing or empty, entity kind, status enum, unparseable dates, evidence_records shape"),
    "schema.id":               ("fail", "§7 #1", "id not of the form TU-NN / EX-NN / ADV-NN, file name not <id>-<slug>.yaml, or an id used twice"),
    "trace.adv":               ("fail", "§7 #2, §4.2", "ADV without ≥1 linked TU and ≥1 linked EX"),
    "trace.ex-tu":             ("fail", "§7 #3, §4.2", "EX without exactly one linked TU (missing, a list of several, or claimed by two TUs)"),
    "ref.dangling":            ("fail", "§7 #4", "a referenced TU / EX / ADV / milestone id that does not exist (records, criteria, cost worksheets)"),
    "evidence.ref":            ("fail", "§7 #5", "an evidence-log entry naming a TU / EX / ADV that does not exist"),
    "state.deadline":          ("fail", "§7 #6", "state/sred.json hard_deadline ≠ fy_end + 18 months or target_date ≠ fy_end + 15 months"),
    "trace.backdating":        ("warn", "§7 #7", "TU identified_date after a linked EX's start_date (backdating appearance)"),
    "ex.no-evidence":          ("warn", "§7 #8", "EX with no evidence_records and no evidence-log entries"),
    "ex.no-adv":               ("warn", "§7 #9", "EX completed more than 90 days ago with no linked ADV"),
    "ex.evidence-gap":         ("warn", "§7 #10", "active EX whose latest evidence is more than 30 days old"),
    "evidence.backfill-share": ("warn", "§7 #11", "back-filled entries exceed 25% of a fiscal year's evidence"),
    "manifest.version":        ("warn", "§7 #12", "the manifest's capabilities.sred.version differs from the installed plugin.yaml version"),
    "evidence.backfilled":     ("fail", "§7 #13, §4.4", "entry logged more than 7 days after its date without backfilled: true"),
    "inbox.stale":             ("warn", "§7 #14", "a sred/inbox/ stub older than 90 days"),
    "criteria.shape":          ("fail", "§7 #15", "criteria.yaml / company-criteria.yaml shape (status, layer, area and routine lists)"),
    "criteria.overlap":        ("fail", "§7 #15", "an area listed both as a candidate uncertainty area and as declared routine"),
    "criteria.layer0":         ("fail", "§7 #16", "a candidate area naming an activity Layer 0 rules out (phrase match against not_eligible_regardless_of_criteria)"),
    "criteria.stale":          ("warn", "§7 #17", "criteria still draft after 90 days, or last refreshed more than two quarters ago"),
    "criteria.routine-milestone": ("warn", "§7 #18", "a TU whose linked_milestones belong to a declared-routine entry"),
    "evidence.excerpt":        ("fail", "§7 #19", "tier-2 entry (slack_message, gdoc, meeting_note, email) without a verbatim excerpt and a record_reference"),
    "inbox.label-ref":         ("fail", "§7 #20", "a stub carrying a sred-ex-NN / sred-tu-NN label for an entity that does not exist"),
    "ex.tier2-only":           ("warn", "§7 #21", "EX whose evidence is entirely tier-2"),
    "evidence.corroborated-by": ("fail", "§7 #22", "corroborated_by not a list of {record_type, reference}, or naming an unknown record_type"),
    "evidence.predates":       ("warn", "§7 #23", "evidence dated before the linked TU's identified_date or the EX's start_date"),
    "ex.single-source":        ("warn", "§7 #24", "EX with ≥3 evidence records all of one record type"),
    "evidence.parse":          ("fail", "§4.4", "an evidence-log line that is not a JSON object"),
    "evidence.required":       ("fail", "§4.4, entities.yaml", "entry missing date, description, people or logged_at, or naming neither tu_id nor ex_id"),
    "evidence.corrects":       ("fail", "tracker update_record", "corrects: that matches no other entry's timestamp"),
    "evidence.entry-type":     ("warn", "entities.yaml", "entry_type outside the vocabulary"),
    "evidence.record-type":    ("warn", "entities.yaml", "record_type outside the vocabulary (tier 1, tier 2 or other)"),
    "evidence.ref-chain":      ("warn", "§4.2", "entry's tu_id differs from its EX's linked_tu"),
    "evidence.missing":        ("warn", "§4.1", "the capability is enabled but sred/evidence-log.ndjson does not exist"),
    "ref.backlink":            ("warn", "§4.2", "a link recorded on one side only (TU ↔ EX, EX ↔ ADV), or an ADV's EX belonging to another TU"),
    "tu.no-ex":                ("warn", "tracker gap_analysis", "TU with no experiment"),
    "ex.no-results":           ("warn", "tracker gap_analysis", "EX with no observations_and_results"),
    "costs.name":              ("warn", "§4.5", "a file in sred/cost-tracking/ that is not a <FY>-costs.yaml worksheet (not checked further)"),
    "costs.shape":             ("fail", "§4.5, §6.4", "worksheet fiscal_year, category lines and rollup block shape"),
    "state.missing":           ("fail", "§4.7", "the capability is enabled but state/sred.json does not exist"),
    "state.schema":            ("fail", "§4.7", "state/sred.json does not satisfy schema/state.schema.json"),
    "state.fy-end":            ("fail", "§4.7", "a fiscal year's fy_end does not fall on fiscal_year_end, or state and manifest disagree on it"),
    "state.fy-key":            ("warn", "§4.7", "fiscal-year key not FY<year of fy_end>"),
    "state.counters":          ("warn", "§4.7", "a counter behind the highest id on disk (the next create would reuse an id)"),
    "state.deadline-passed":   ("warn", "§4.7", "hard deadline passed and the claim is not filed, waived or forfeited"),
    "inbox.shape":             ("fail", "§6.3, entities.yaml", "a stub that is neither a single {date, source{surface, ref}, description_draft} nor a cluster {records, window, corroboration}"),
    "inbox.ref":               ("fail", "§6.3", "suggested_ex / suggested_tu naming an entity that does not exist"),
    "inbox.excerpt":           ("warn", "tracker confirm_evidence", "a tier-2 stub or cluster record without an excerpt (cannot be confirmed until captured)"),
    "inbox.record-type":       ("warn", "entities.yaml", "a cluster record_type outside the vocabulary"),
    "inbox.corroboration":     ("warn", "Addendum C", "a cluster's corroboration count above its distinct tier-1 record types"),
    "fy.format":               ("fail", "§4.2", "claim_fy not FY<year>, or fiscal_year not <year> / FY<year>"),
    "fy.mismatch":             ("fail", "§4.2, §12.2", "claim_fy and fiscal_year name different years"),
    "fy.missing":              ("warn", "§4.2", "record without claim_fy (predates it; rollup_costs falls back to fiscal_year)"),
    "fy.unknown":              ("warn", "§4.7", "claim_fy not in state/sred.json fiscal_years"),
    "fy.span":                 ("warn", "§12.2", "an EX dated outside its claim year (split it into per-FY EX records)"),
    "revisions.shape":         ("fail", "tracker update_record", "revisions: entries not {at, by, fields, reason, prior}, or revising a field update_record refuses"),
    "review-notes.shape":      ("fail", "§4.2", "review_notes item neither a string nor {date, by, finding, severity, status, resolution} with valid enums"),
    "review-notes.incomplete": ("warn", "§4.2", "a structured note missing date / by, or resolved without a resolution"),
}

SKIPPED = [
    ("costs.rollup-preserves-manual", "§4.5 / §6.4: rollup_costs never overwrites manual worksheet lines — a property of a write, "
     "not of a snapshot; one copy of the file cannot show what it said before. Not checkable here."),
    ("criteria.layer0 (judgement)", "§7 #16 is checked by phrase match only; whether a candidate area is in substance routine "
     "work is the reviewer's and the advisor's call."),
    ("criteria.routine-milestone (string entries)", "§7 #18 needs a declared_routine entry that names milestones "
     "({label, linked_milestones}); a plain-string entry carries no link to check."),
    ("evidence.predates (source timestamps)", "§7 #23 compares each entry's own date, not the server timestamp of the "
     "source record behind it — that needs the source."),
    ("narrative quality", "risky language, proportionality and field-relative framing are project-sred-reviewer's job."),
]

TU_RE, EX_RE, ADV_RE = (re.compile(rf"^{p}-\d{{2,}}$") for p in ("TU", "EX", "ADV"))
FY_RE = re.compile(r"^FY(\d{4})$")
KINDS = {
    "TU": {"dir": "uncertainties", "re": TU_RE, "entity": {"technological_uncertainty", "sred.technological_uncertainty"},
           "required": ["id", "uncertainty_statement", "standard_practice_gap", "field_of_science", "identified_date", "status"],
           "dates": ["identified_date", "work_start_date", "work_end_date"], "status": {"active", "resolved", "removed"}},
    "EX": {"dir": "experiments", "re": EX_RE, "entity": {"experiment", "sred.experiment"},
           "required": ["id", "hypothesis", "method_and_trials", "start_date", "status"],
           "dates": ["start_date", "end_date"], "status": {"in_progress", "complete", "abandoned"}},
    "ADV": {"dir": "advancements", "re": ADV_RE, "entity": {"technological_advancement", "sred.technological_advancement"},
            "required": ["id", "advancement_statement"], "dates": ["established_date"], "status": None},
}
ENTRY_TYPES = {"experiment", "test", "failure", "iteration", "advancement", "meeting", "publication", "harvested"}
FROZEN_FIELDS = {"id", "entity", "created_by", "schema_version"}  # update_record refuses these
TIER2_SURFACES = {"slack", "gdocs", "gdoc", "gmail", "email", "meeting", "meeting_note"}


def yload(p: Path):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _schema():
    try:
        return yload(CAP / "schema" / "entities.yaml") or {}
    except Exception:
        return {}


SCHEMA = _schema()
_tiers = SCHEMA.get("evidence_source_tiers") or {}
TIER1 = set(_tiers.get("tier_1_primary") or [])
TIER2 = set(_tiers.get("tier_2_corroborating") or [])
RECORD_TYPES = TIER1 | TIER2 | {"other"}
_entry = ((SCHEMA.get("files") or [{}])[0] or {}).get("entry_schema") or {}
ENTRY_REQUIRED = _entry.get("required") or ["date", "description", "people", "logged_at"]
ENTRY_ONE_OF = _entry.get("one_of_required") or ["tu_id", "ex_id"]


# ── small helpers ────────────────────────────────────────────────────────────────────────────────
def to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str) and len(v) >= 10:
        try:
            return dt.date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def to_dt(v):
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day, tzinfo=dt.timezone.utc)
    if isinstance(v, str) and v:
        s = v.strip().replace("Z", "+00:00")
        try:
            d = dt.datetime.fromisoformat(s)
        except ValueError:
            d0 = to_date(s)
            return to_dt(d0) if d0 else None
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    return None


def add_months(d: dt.date, n: int) -> dt.date:
    """d + n months; a month-end date stays a month-end (2026-12-31 + 18 → 2028-06-30)."""
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    last = calendar.monthrange(y, m)[1]
    eom = d.day == calendar.monthrange(d.year, d.month)[1]
    return dt.date(y, m, last if eom else min(d.day, last))


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def norm_fy(v):
    """'FY2026' or 2026 or '2026' → 'FY2026'; anything else → None."""
    s = str(v).strip() if v is not None else ""
    if re.fullmatch(r"\d{4}", s):
        return "FY" + s
    return s if FY_RE.match(s) else None


class Findings:
    def __init__(self):
        self.items = []

    def add(self, rule, path, entity, message):
        sev = RULES[rule][0]
        self.items.append({"severity": sev, "rule": rule, "path": path, "entity": entity, "message": message})

    @property
    def fails(self):
        return [f for f in self.items if f["severity"] == "fail"]

    @property
    def warns(self):
        return [f for f in self.items if f["severity"] == "warn"]


# ── a tiny JSON Schema subset, enough for schema/state.schema.json (no jsonschema dependency) ────
def json_schema_errors(inst, sch, where="$"):
    out = []
    types = sch.get("type")
    if types:
        tl = types if isinstance(types, list) else [types]
        ok = any({"object": isinstance(inst, dict), "array": isinstance(inst, list), "string": isinstance(inst, str),
                  "boolean": isinstance(inst, bool), "null": inst is None,
                  "integer": isinstance(inst, int) and not isinstance(inst, bool),
                  "number": isinstance(inst, (int, float)) and not isinstance(inst, bool)}[t] for t in tl)
        if not ok:
            return [f"{where}: expected {' or '.join(tl)}, got {type(inst).__name__}"]
    if "const" in sch and inst != sch["const"]:
        out.append(f"{where}: must be {sch['const']!r}")
    if "enum" in sch and inst not in sch["enum"]:
        out.append(f"{where}: {inst!r} not one of {', '.join(map(str, sch['enum']))}")
    if isinstance(inst, str):
        if "pattern" in sch and not re.search(sch["pattern"], inst):
            out.append(f"{where}: {inst!r} does not match {sch['pattern']}")
        if sch.get("format") == "date" and (not re.fullmatch(r"\d{4}-\d{2}-\d{2}", inst) or to_date(inst) is None):
            out.append(f"{where}: {inst!r} is not a YYYY-MM-DD date")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool) and "minimum" in sch and inst < sch["minimum"]:
        out.append(f"{where}: {inst} below minimum {sch['minimum']}")
    if isinstance(inst, dict):
        for k in sch.get("required") or []:
            if k not in inst:
                out.append(f"{where}: missing required {k!r}")
        props = sch.get("properties") or {}
        for k, v in inst.items():
            if k in props:
                out += json_schema_errors(v, props[k], f"{where}.{k}")
            elif isinstance(sch.get("additionalProperties"), dict):
                out += json_schema_errors(v, sch["additionalProperties"], f"{where}.{k}")
            elif sch.get("additionalProperties") is False:
                out.append(f"{where}: unexpected property {k!r}")
    if isinstance(inst, list) and isinstance(sch.get("items"), dict):
        for i, v in enumerate(inst):
            out += json_schema_errors(v, sch["items"], f"{where}[{i}]")
    return out


# ── the check ────────────────────────────────────────────────────────────────────────────────────
def check(fac: Path, as_of: dt.date | None = None, strict: bool = False) -> dict:
    as_of = as_of or dt.date.today()
    F = Findings()
    fac = Path(fac)
    sred = fac / "sred"
    manifest = {}
    try:
        manifest = yload(fac / "manifest.yaml") or {}
    except Exception:
        pass
    block = ((manifest.get("capabilities") or {}).get("sred") or {}) if isinstance(manifest, dict) else {}
    enabled = bool(isinstance(block, dict) and block.get("enabled"))

    # ── manifest ─────────────────────────────────────────────────────────────
    try:
        plugin_version = str(((yload(CAP / "plugin.yaml") or {}).get("plugin") or {}).get("version") or "")
    except Exception:
        plugin_version = ""
    if enabled and plugin_version and block.get("version") is not None and str(block.get("version")) != plugin_version:
        F.add("manifest.version", "manifest.yaml", "capabilities.sred", f"enabled at version {block.get('version')}, installed capability is {plugin_version}")

    # ── state/sred.json (read first: fiscal years feed the record checks) ────
    state, fys = {}, {}
    sp = fac / "state" / "sred.json"
    if sp.exists():
        try:
            state = json.loads(sp.read_text(encoding="utf-8"))
        except Exception as e:
            F.add("state.schema", "state/sred.json", "-", f"does not parse as JSON: {e}")
            state = {}
        if state:
            try:
                sch = json.loads((CAP / "schema" / "state.schema.json").read_text(encoding="utf-8"))
            except Exception:
                sch = {}
            for err in json_schema_errors(state, sch):
                F.add("state.schema", "state/sred.json", "-", err)
    elif enabled:
        F.add("state.missing", "state/sred.json", "-", "the sred capability is enabled but state/sred.json does not exist")
    if isinstance(state, dict):
        fye = state.get("fiscal_year_end")
        mfye = block.get("fiscal_year_end") if isinstance(block, dict) else None
        if fye and mfye and str(fye) != str(mfye):
            F.add("state.fy-end", "state/sred.json", "fiscal_year_end", f"state says {fye}, manifest capabilities.sred says {mfye}")
        for key, fy in (state.get("fiscal_years") or {}).items() if isinstance(state.get("fiscal_years"), dict) else []:
            if not isinstance(fy, dict):
                continue
            end = to_date(fy.get("fy_end"))
            if end:
                fys[key] = end
            else:
                continue
            if isinstance(fye, str) and re.fullmatch(r"--\d{2}-\d{2}", fye) and end.strftime("--%m-%d") != fye:
                F.add("state.fy-end", "state/sred.json", key, f"fy_end {end} does not fall on fiscal_year_end {fye}")
            m = FY_RE.match(str(key))
            if not m or int(m.group(1)) != end.year:
                F.add("state.fy-key", "state/sred.json", key, f"key should be FY{end.year} for fy_end {end}")
            for field, months in (("hard_deadline", 18), ("target_date", 15)):
                want = add_months(end, months)
                got = to_date(fy.get(field))
                if got is not None and got != want:
                    F.add("state.deadline", "state/sred.json", key, f"{field} {got} ≠ fy_end + {months} months ({want})")
            hd = to_date(fy.get("hard_deadline"))
            if hd and hd < as_of and fy.get("claim_status") not in ("filed", "waived", "forfeited"):
                F.add("state.deadline-passed", "state/sred.json", key, f"hard deadline {hd} has passed and the claim is {fy.get('claim_status')} — record it as forfeited, loudly")

    def fy_of(d: dt.date | None):
        if not d:
            return None
        for key, end in fys.items():
            if add_months(end, -12) < d <= end:
                return key
        return None

    if not sred.is_dir():
        if enabled:
            F.add("schema.shape", "sred/", "-", "the sred capability is enabled but sred/ does not exist")
        return finish(F, strict, as_of, enabled)

    # ── milestones the records may name ──────────────────────────────────────
    milestones = set()
    for p in sorted((fac / "milestones").glob("*.yaml")) if (fac / "milestones").is_dir() else []:
        milestones.add(p.stem)
        milestones.add(p.stem.split("-")[0])
        try:
            d = yload(p)
            if isinstance(d, dict) and d.get("id"):
                milestones.add(str(d["id"]))
        except Exception:
            pass

    def milestone_ok(mid):
        return not milestones or str(mid) in milestones or str(mid).split("-")[0] in milestones

    # ── TU / EX / ADV records ────────────────────────────────────────────────
    recs = {"TU": {}, "EX": {}, "ADV": {}}
    for kind, spec in KINDS.items():
        d = sred / spec["dir"]
        for p in sorted(d.glob("*.yaml")) if d.is_dir() else []:
            rel = p.relative_to(fac).as_posix()
            try:
                doc = yload(p)
            except Exception as e:
                F.add("schema.parse", rel, p.stem, f"does not parse: {str(e).splitlines()[0]}")
                continue
            if not isinstance(doc, dict):
                F.add("schema.parse", rel, p.stem, "is not a YAML mapping")
                continue
            rid = str(doc.get("id") or "")
            if not spec["re"].match(rid):
                F.add("schema.id", rel, rid or p.stem, f"id {rid!r} is not of the form {kind}-NN")
                rid = rid or p.stem
            elif not (p.stem == rid or p.stem.startswith(rid + "-")):
                F.add("schema.id", rel, rid, f"file name should be {rid}-<slug>.yaml")
            if rid in recs[kind]:
                F.add("schema.id", rel, rid, f"{rid} is also used by {recs[kind][rid]['_path']}")
                continue
            doc["_path"] = rel
            recs[kind][rid] = doc
            ent = doc.get("entity")
            if ent is not None and ent not in spec["entity"]:
                F.add("schema.shape", rel, rid, f"entity {ent!r} should be {sorted(spec['entity'])[0]}")
            missing = [k for k in spec["required"] if blank(doc.get(k))]
            if missing:
                F.add("schema.shape", rel, rid, f"missing or empty: {', '.join(missing)}")
            for k in spec["dates"]:
                if doc.get(k) is not None and to_date(doc.get(k)) is None:
                    F.add("schema.shape", rel, rid, f"{k} {doc.get(k)!r} is not a YYYY-MM-DD date")
            if spec["status"] and doc.get("status") is not None and doc.get("status") not in spec["status"]:
                F.add("schema.shape", rel, rid, f"status {doc.get('status')!r} not one of {', '.join(sorted(spec['status']))}")
            check_fy(F, doc, rel, rid, fys)
            check_revisions(F, doc, rel, rid)
            check_review_notes(F, doc, rel, rid)
            for m in as_list(doc.get("linked_milestones")):
                if not milestone_ok(m):
                    F.add("ref.dangling", rel, rid, f"linked milestone {m} does not exist")

    TU, EX, ADV = recs["TU"], recs["EX"], recs["ADV"]

    # TU → EX
    for tid, t in TU.items():
        for e in as_list(t.get("linked_experiments")):
            if e not in EX:
                F.add("ref.dangling", t["_path"], tid, f"linked experiment {e} does not exist")
            elif EX[e].get("linked_tu") != tid and tid not in as_list(EX[e].get("linked_tu")):
                F.add("ref.backlink", t["_path"], tid, f"lists {e}, whose linked_tu is {EX[e].get('linked_tu')}")
    # EX → TU (exactly one), EX → ADV
    claimed_by = {}
    for tid, t in TU.items():
        for e in as_list(t.get("linked_experiments")):
            claimed_by.setdefault(e, []).append(tid)
    for eid, e in EX.items():
        lt = e.get("linked_tu")
        tus = [x for x in as_list(lt) if not blank(x)]
        if len(tus) != 1:
            F.add("trace.ex-tu", e["_path"], eid, "no linked_tu" if not tus else f"linked_tu names {len(tus)} TUs ({', '.join(map(str, tus))}) — an EX tests exactly one")
        for x in tus:
            if x not in TU:
                F.add("ref.dangling", e["_path"], eid, f"linked TU {x} does not exist")
            elif eid not in as_list(TU[x].get("linked_experiments")):
                F.add("ref.backlink", e["_path"], eid, f"linked to {x}, which does not list it in linked_experiments")
        others = sorted(set(claimed_by.get(eid, [])) - set(tus))
        if others and tus:
            F.add("trace.ex-tu", e["_path"], eid, f"also claimed by {', '.join(others)} — an EX belongs to exactly one TU")
        for a in as_list(e.get("linked_advancements")):
            if a not in ADV:
                F.add("ref.dangling", e["_path"], eid, f"linked advancement {a} does not exist")
            elif eid not in as_list(ADV[a].get("linked_experiments")):
                F.add("ref.backlink", e["_path"], eid, f"lists {a}, which does not list it in linked_experiments")
        if blank(e.get("observations_and_results")):
            F.add("ex.no-results", e["_path"], eid, "no observations_and_results — no documented outcome")
        er = e.get("evidence_records")
        if er is not None and not (isinstance(er, list) and all(isinstance(x, dict) and x.get("type") and x.get("reference") for x in er)):
            F.add("schema.shape", e["_path"], eid, "evidence_records must be a list of {type, reference, date, description}")
        if e.get("people_involved") is not None:
            pi = e.get("people_involved")
            if not isinstance(pi, list) or not all(isinstance(x, dict) and x.get("name") and isinstance(x.get("eligible_days", 0), (int, float)) and not isinstance(x.get("eligible_days", 0), bool) for x in pi):
                F.add("schema.shape", e["_path"], eid, "people_involved must be a list of {name, role, eligible_days: number}")
        # TU identified after the EX started (§7 #7)
        for x in tus:
            if x in TU:
                ti, es = to_date(TU[x].get("identified_date")), to_date(e.get("start_date"))
                if ti and es and ti > es:
                    F.add("trace.backdating", TU[x]["_path"], x, f"identified {ti}, after {eid} started {es}")
    # ADV → TU and EX
    for aid, a in ADV.items():
        tus = [x for x in as_list(a.get("linked_tu")) if not blank(x)]
        exs = [x for x in as_list(a.get("linked_experiments")) if not blank(x)]
        if not tus or not exs:
            F.add("trace.adv", a["_path"], aid, "needs ≥1 linked TU and ≥1 linked EX — " + ("no TU" if not tus else "") + (" and " if not tus and not exs else "") + ("no EX" if not exs else ""))
        for x in tus:
            if x not in TU:
                F.add("ref.dangling", a["_path"], aid, f"linked TU {x} does not exist")
        for x in exs:
            if x not in EX:
                F.add("ref.dangling", a["_path"], aid, f"linked experiment {x} does not exist")
                continue
            if aid not in as_list(EX[x].get("linked_advancements")):
                F.add("ref.backlink", a["_path"], aid, f"lists {x}, which does not list it in linked_advancements")
            if tus and EX[x].get("linked_tu") not in tus:
                F.add("ref.backlink", a["_path"], aid, f"{x} belongs to {EX[x].get('linked_tu')}, not {', '.join(tus)}")
    for tid, t in TU.items():
        if not as_list(t.get("linked_experiments")) and not any(e.get("linked_tu") == tid for e in EX.values()) and t.get("status") != "removed":
            F.add("tu.no-ex", t["_path"], tid, "no experiment investigates this uncertainty")
    # EX dates against the claim year (§12.2)
    for eid, e in EX.items():
        cfy = norm_fy(e.get("claim_fy")) or norm_fy(e.get("fiscal_year"))
        if cfy in fys:
            lo, hi = add_months(fys[cfy], -12), fys[cfy]
            for k in ("start_date", "end_date"):
                d = to_date(e.get(k))
                if d and not (lo < d <= hi):
                    F.add("fy.span", e["_path"], eid, f"{k} {d} falls outside {cfy} ({lo + dt.timedelta(days=1)} – {hi}) — split multi-year work into per-FY EX records")

    # ── the evidence log ─────────────────────────────────────────────────────
    lp = sred / "evidence-log.ndjson"
    entries = []
    if lp.exists():
        for n, line in enumerate(lp.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            where = f"sred/evidence-log.ndjson:{n}"
            try:
                e = json.loads(line)
            except json.JSONDecodeError as err:
                F.add("evidence.parse", where, f"line {n}", f"not JSON: {err.msg}")
                continue
            if not isinstance(e, dict):
                F.add("evidence.parse", where, f"line {n}", "not a JSON object")
                continue
            e["_where"], e["_n"] = where, n
            entries.append(e)
    elif enabled:
        F.add("evidence.missing", "sred/evidence-log.ndjson", "-", "no evidence log — nothing has been captured contemporaneously")

    stamps = {}
    for e in entries:
        for k in ("timestamp", "logged_at"):
            t = to_dt(e.get(k))
            if t:
                stamps.setdefault(t, []).append(e["_n"])
    for e in entries:
        w = e["_where"]
        ent = e.get("ex_id") or e.get("tu_id") or f"line {e['_n']}"
        missing = [k for k in ENTRY_REQUIRED if blank(e.get(k))]
        if missing:
            extra = " (it carries appended_at, the server's stamp; logged_at is the entry's own)" if "logged_at" in missing and e.get("appended_at") else ""
            F.add("evidence.required", w, ent, f"missing {', '.join(missing)}{extra}")
        if e.get("people") is not None and not isinstance(e.get("people"), list):
            F.add("evidence.required", w, ent, "people must be a list of names")
        if all(blank(e.get(k)) for k in ENTRY_ONE_OF):
            F.add("evidence.required", w, ent, f"names none of {', '.join(ENTRY_ONE_OF)}")
        d = to_date(e.get("date"))
        if e.get("date") is not None and d is None:
            F.add("evidence.required", w, ent, f"date {e.get('date')!r} is not a YYYY-MM-DD date")
        e["_date"] = d
        for k, pool in (("tu_id", TU), ("ex_id", EX), ("adv_id", ADV)):
            v = e.get(k)
            if not blank(v) and v not in pool:
                F.add("evidence.ref", w, ent, f"{k} {v} does not exist")
        if e.get("ex_id") in EX and not blank(e.get("tu_id")) and EX[e["ex_id"]].get("linked_tu") != e.get("tu_id"):
            F.add("evidence.ref-chain", w, ent, f"tu_id {e.get('tu_id')} but {e['ex_id']} belongs to {EX[e['ex_id']].get('linked_tu')}")
        if e.get("entry_type") is not None and e.get("entry_type") not in ENTRY_TYPES:
            F.add("evidence.entry-type", w, ent, f"entry_type {e.get('entry_type')!r} is not in the vocabulary")
        rt = e.get("record_type")
        if rt is not None and rt not in RECORD_TYPES:
            F.add("evidence.record-type", w, ent, f"record_type {rt!r} is not in the vocabulary")
        # the 7-day back-fill rule (§4.4)
        logged = to_dt(e.get("logged_at")) or to_dt(e.get("appended_at"))
        late = bool(d and logged and (logged.date() - d).days > 7)
        e["_late"] = late or e.get("backfilled") is True
        if late and e.get("backfilled") is not True:
            F.add("evidence.backfilled", w, ent, f"logged {logged.date()}, {(logged.date() - d).days} days after the work ({d}), without backfilled: true")
        if rt in TIER2 and (blank(e.get("excerpt")) or blank(e.get("record_reference"))):
            need = [k for k in ("excerpt", "record_reference") if blank(e.get(k))]
            F.add("evidence.excerpt", w, ent, f"tier-2 {rt} without {' and '.join(need)} — the source may not survive; the excerpt is what does")
        cb = e.get("corroborated_by")
        if cb is not None:
            if not isinstance(cb, list) or not all(isinstance(x, dict) and not blank(x.get("record_type")) and not blank(x.get("reference")) for x in cb):
                F.add("evidence.corroborated-by", w, ent, "must be a list of {record_type, reference}")
            else:
                bad = [x["record_type"] for x in cb if x["record_type"] not in RECORD_TYPES]
                if bad:
                    F.add("evidence.corroborated-by", w, ent, f"unknown record_type {', '.join(map(str, bad))}")
        if not blank(e.get("corrects")):
            t = to_dt(e.get("corrects"))
            hits = [n for n in stamps.get(t, []) if n != e["_n"]] if t else []
            if not hits:
                F.add("evidence.corrects", w, ent, f"corrects {e.get('corrects')!r}, which is no other entry's timestamp")
        if d:
            if e.get("tu_id") in TU:
                ti = to_date(TU[e["tu_id"]].get("identified_date"))
                if ti and d < ti:
                    F.add("evidence.predates", w, ent, f"dated {d}, before {e['tu_id']} was identified ({ti})")
            if e.get("ex_id") in EX:
                es = to_date(EX[e["ex_id"]].get("start_date"))
                if es and d < es:
                    F.add("evidence.predates", w, ent, f"dated {d}, before {e['ex_id']} started ({es})")

    # back-filled share per fiscal year (§7 #11) — counts entries back-filled by the 7-day rule, flagged or not
    per_fy = {}
    for e in entries:
        fy = None
        for k, pool in (("ex_id", EX), ("tu_id", TU)):
            if e.get(k) in pool:
                fy = norm_fy(pool[e[k]].get("claim_fy")) or norm_fy(pool[e[k]].get("fiscal_year"))
                if fy:
                    break
        fy = fy or fy_of(e.get("_date"))
        if fy:
            c = per_fy.setdefault(fy, [0, 0])
            c[0] += 1
            c[1] += 1 if e["_late"] else 0
    for fy, (tot, late) in sorted(per_fy.items()):
        if tot and late / tot > 0.25:
            F.add("evidence.backfill-share", "sred/evidence-log.ndjson", fy, f"{late} of {tot} entries ({round(100 * late / tot)}%) are back-filled — above 25%")

    # ── per experiment: evidence, staleness, advancement, corroboration ──────
    for eid, e in EX.items():
        logs = [x for x in entries if x.get("ex_id") == eid]
        recs_ = [x for x in (e.get("evidence_records") or []) if isinstance(x, dict)]
        if not logs and not recs_:
            F.add("ex.no-evidence", e["_path"], eid, "no evidence_records and no evidence-log entries")
        dates = [x["_date"] for x in logs if x.get("_date")] + [to_date(x.get("date")) for x in recs_ if to_date(x.get("date"))]
        if e.get("status") == "in_progress":
            last = max(dates) if dates else to_date(e.get("start_date"))
            if last and (as_of - last).days > 30:
                F.add("ex.evidence-gap", e["_path"], eid, f"active, latest evidence {last} — {(as_of - last).days} days ago")
        if e.get("status") == "complete":
            end = to_date(e.get("end_date"))
            has_adv = bool(as_list(e.get("linked_advancements"))) or any(eid in as_list(a.get("linked_experiments")) for a in ADV.values())
            if end and (as_of - end).days > 90 and not has_adv:
                F.add("ex.no-adv", e["_path"], eid, f"completed {end} ({(as_of - end).days} days ago) with no advancement declared")
        types = [x.get("type") for x in recs_ if x.get("type")] + [x.get("record_type") for x in logs if x.get("record_type")]
        known = [t for t in types if t in RECORD_TYPES]
        if known and all(t in TIER2 for t in known):
            F.add("ex.tier2-only", e["_path"], eid, f"all {len(known)} evidence record(s) are tier-2 — anchor to a commit, issue, build or versioned page")
        if len(types) >= 3 and len(set(types)) == 1:
            F.add("ex.single-source", e["_path"], eid, f"{len(types)} evidence records, all {types[0]} — corroborate from another source type while it is fresh")

    # ── state counters against the ids on disk ───────────────────────────────
    counters = state.get("counters") if isinstance(state, dict) else None
    if isinstance(counters, dict):
        for kind, key in (("TU", "tu"), ("EX", "ex"), ("ADV", "adv")):
            nums = [int(i.split("-")[1]) for i in recs[kind] if KINDS[kind]["re"].match(i)]
            c = counters.get(key)
            if nums and isinstance(c, int) and c < max(nums):
                F.add("state.counters", "state/sred.json", f"counters.{key}", f"{c} is behind {kind}-{max(nums):02d} on disk — the next create would reuse an id")

    # ── cost worksheets (§4.5) ───────────────────────────────────────────────
    cd = sred / "cost-tracking"
    for p in sorted(cd.glob("*")) if cd.is_dir() else []:
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(fac).as_posix()
        m = re.fullmatch(r"(FY\d{4})-costs\.ya?ml", p.name)
        if not m:
            F.add("costs.name", rel, p.stem, "not a <FY>-costs.yaml worksheet — not checked as one")
            continue
        check_costs(F, p, rel, m.group(1), EX, fys)

    # ── the inbox (§6.3) ─────────────────────────────────────────────────────
    ib = sred / "inbox"
    num = {"EX": {int(i.split("-")[1]) for i in EX if EX_RE.match(i)}, "TU": {int(i.split("-")[1]) for i in TU if TU_RE.match(i)}}
    for p in sorted(ib.glob("*.y*ml")) if ib.is_dir() else []:
        check_stub(F, p, p.relative_to(fac).as_posix(), TU, EX, num, as_of)

    # ── criteria (§7 #15-18) ─────────────────────────────────────────────────
    check_criteria(F, sred, TU, as_of)

    return finish(F, strict, as_of, enabled)


def finish(F, strict, as_of, enabled):
    ok = not F.fails and not (strict and F.warns)
    return {"ok": ok, "as_of": as_of.isoformat(), "enabled": enabled, "fails": len(F.fails), "warns": len(F.warns),
            "findings": F.items, "not_checked": [{"rule": r, "why": w} for r, w in SKIPPED]}


def check_fy(F, doc, rel, rid, fys):
    cfy, fy = doc.get("claim_fy"), doc.get("fiscal_year")
    if cfy is None:
        F.add("fy.missing", rel, rid, "no claim_fy" + (f" (fiscal_year {fy})" if fy is not None else ""))
    elif not FY_RE.match(str(cfy)):
        F.add("fy.format", rel, rid, f"claim_fy {cfy!r} should be FY<year>")
    elif fys and str(cfy) not in fys:
        F.add("fy.unknown", rel, rid, f"claim_fy {cfy} is not in state/sred.json fiscal_years")
    if fy is not None and norm_fy(fy) is None:
        F.add("fy.format", rel, rid, f"fiscal_year {fy!r} should be <year> or FY<year>")
    elif fy is not None and cfy is not None and FY_RE.match(str(cfy)) and norm_fy(fy) != str(cfy):
        F.add("fy.mismatch", rel, rid, f"claim_fy {cfy} but fiscal_year {fy} — an entity belongs to one claim year")


def check_revisions(F, doc, rel, rid):
    rv = doc.get("revisions")
    if rv is None:
        return
    if not isinstance(rv, list):
        F.add("revisions.shape", rel, rid, "revisions must be a list")
        return
    for i, r in enumerate(rv):
        if not isinstance(r, dict):
            F.add("revisions.shape", rel, rid, f"revisions[{i}] is not {{at, by, fields, reason, prior}}")
            continue
        probs = []
        if to_dt(r.get("at")) is None:
            probs.append("at is not an ISO8601 time")
        if blank(r.get("by")):
            probs.append("no by")
        flds = r.get("fields")
        if not isinstance(flds, list) or not flds or not all(isinstance(x, str) for x in flds):
            probs.append("fields must name the changed fields")
            flds = []
        if blank(r.get("reason")) or not isinstance(r.get("reason"), str):
            probs.append("no reason")
        prior = r.get("prior")
        if not isinstance(prior, dict):
            probs.append("prior must map each changed field to its old value")
        else:
            extra = sorted(set(prior) - set(flds))
            gone = sorted(set(flds) - set(prior))
            if extra:
                probs.append(f"prior holds {', '.join(extra)}, not in fields")
            if gone:
                probs.append(f"prior lacks {', '.join(gone)}")
        frozen = sorted(set(flds) & FROZEN_FIELDS)
        if frozen:
            probs.append(f"revises {', '.join(frozen)}, which update_record refuses")
        if probs:
            F.add("revisions.shape", rel, rid, f"revisions[{i}]: " + "; ".join(probs))


def check_review_notes(F, doc, rel, rid):
    rn = doc.get("review_notes")
    if rn is None:
        return
    if not isinstance(rn, list):
        F.add("review-notes.shape", rel, rid, "review_notes must be a list")
        return
    for i, n in enumerate(rn):
        if isinstance(n, str):
            continue
        if not isinstance(n, dict):
            F.add("review-notes.shape", rel, rid, f"review_notes[{i}] is a {type(n).__name__}, not a string or a finding")
            continue
        probs = [f"no {k}" for k in ("finding", "severity", "status") if blank(n.get(k))]
        if not blank(n.get("severity")) and n.get("severity") not in ("high", "medium", "low"):
            probs.append(f"severity {n.get('severity')!r} not high | medium | low")
        if not blank(n.get("status")) and n.get("status") not in ("open", "resolved"):
            probs.append(f"status {n.get('status')!r} not open | resolved")
        if n.get("date") is not None and to_date(n.get("date")) is None:
            probs.append(f"date {n.get('date')!r} is not a date")
        unknown = sorted(set(n) - {"date", "by", "finding", "severity", "status", "resolution"})
        if unknown:
            probs.append(f"unknown key(s) {', '.join(unknown)}")
        if probs:
            F.add("review-notes.shape", rel, rid, f"review_notes[{i}]: " + "; ".join(probs))
            continue
        soft = [f"no {k}" for k in ("date", "by") if blank(n.get(k))]
        if n.get("status") == "resolved" and blank(n.get("resolution")):
            soft.append("resolved without a resolution")
        if soft:
            F.add("review-notes.incomplete", rel, rid, f"review_notes[{i}]: " + "; ".join(soft))


def check_costs(F, p, rel, fy, EX, fys):
    try:
        doc = yload(p)
    except Exception as e:
        F.add("schema.parse", rel, fy, f"does not parse: {str(e).splitlines()[0]}")
        return
    if not isinstance(doc, dict):
        F.add("schema.parse", rel, fy, "is not a YAML mapping")
        return
    if str(doc.get("fiscal_year")) != fy:
        F.add("costs.shape", rel, fy, f"fiscal_year {doc.get('fiscal_year')!r} should be {fy}, as the file name says")
    if doc.get("fy_end") is not None:
        end = to_date(doc.get("fy_end"))
        if end is None:
            F.add("costs.shape", rel, fy, f"fy_end {doc.get('fy_end')!r} is not a date")
        elif fy in fys and end != fys[fy]:
            F.add("costs.shape", rel, fy, f"fy_end {end} but state/sred.json says {fys[fy]}")
    # the three categories sit at the top level (templates/entities/FY-costs.yaml); an older layout nests them under categories:
    cats = doc.get("categories") if isinstance(doc.get("categories"), dict) else doc
    for cat in ("eligible_experimental", "partially_eligible_support", "non_eligible_routine"):
        lines = cats.get(cat)
        if lines is None:
            continue
        if not isinstance(lines, list):
            F.add("costs.shape", rel, fy, f"{cat} must be a list of lines")
            continue
        for i, ln in enumerate(lines):
            if not isinstance(ln, dict) or blank(ln.get("person")):
                F.add("costs.shape", rel, fy, f"{cat}[{i}] needs at least a person")
                continue
            for k in ("days", "amount", "eligible_fraction"):
                v = ln.get(k)
                if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0):
                    F.add("costs.shape", rel, fy, f"{cat}[{i}] {k} {v!r} must be a non-negative number")
            ef = ln.get("eligible_fraction")
            if isinstance(ef, (int, float)) and not isinstance(ef, bool) and ef > 1:
                F.add("costs.shape", rel, fy, f"{cat}[{i}] eligible_fraction {ef} is above 1")
            for x in as_list(ln.get("linked_ex")):
                if x not in EX:
                    F.add("ref.dangling", rel, fy, f"{cat}[{i}] links {x}, which does not exist")
    ru = doc.get("rollup")
    if ru is not None:
        if not isinstance(ru, dict):
            F.add("costs.shape", rel, fy, "rollup must be a mapping {generated_at, per_person, discrepancies}")
            return
        pp = ru.get("per_person")
        if pp is not None:
            if not isinstance(pp, list):
                F.add("costs.shape", rel, fy, "rollup.per_person must be a list")
            else:
                for i, x in enumerate(pp):
                    if not isinstance(x, dict) or blank(x.get("person")) or not isinstance(x.get("by_experiment", {}), dict):
                        F.add("costs.shape", rel, fy, f"rollup.per_person[{i}] must be {{person, eligible_days_total, by_experiment}}")
                        continue
                    for k in (x.get("by_experiment") or {}):
                        if k not in EX:
                            F.add("ref.dangling", rel, fy, f"rollup.per_person[{i}] counts {k}, which does not exist")
        if ru.get("discrepancies") is not None and not isinstance(ru.get("discrepancies"), list):
            F.add("costs.shape", rel, fy, "rollup.discrepancies must be a list")


LABEL_RE = re.compile(r"\bsred-(ex|tu)-(\d+)\b", re.I)


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def check_stub(F, p, rel, TU, EX, num, as_of):
    try:
        s = yload(p)
    except Exception as e:
        F.add("schema.parse", rel, p.stem, f"does not parse: {str(e).splitlines()[0]}")
        return
    if not isinstance(s, dict):
        F.add("schema.parse", rel, p.stem, "is not a YAML mapping")
        return
    ent = s.get("suggested_ex") or s.get("suggested_tu") or p.stem
    probs = []
    if "records" in s:  # a cluster from the correlation pass
        recs = s.get("records")
        if not isinstance(recs, list) or not recs:
            probs.append("records must be a non-empty list")
            recs = []
        tier1 = set()
        for i, r in enumerate(recs):
            if not isinstance(r, dict) or blank(r.get("record_type")) or blank(r.get("reference")):
                probs.append(f"records[{i}] needs record_type and reference")
                continue
            if r.get("date") is not None and to_date(r.get("date")) is None:
                probs.append(f"records[{i}] date {r.get('date')!r} is not a date")
            rt = r.get("record_type")
            if rt not in RECORD_TYPES:
                F.add("inbox.record-type", rel, ent, f"records[{i}] record_type {rt!r} is not in the vocabulary")
            t2 = rt in TIER2 or r.get("tier") == 2
            if t2 and blank(r.get("excerpt")):
                F.add("inbox.excerpt", rel, ent, f"records[{i}] is tier-2 with no excerpt — capture it before confirming")
            if rt in TIER1 and r.get("tier") != 2:
                tier1.add(rt)
        w = s.get("window")
        if not isinstance(w, dict) or to_date(w.get("from")) is None or to_date(w.get("to")) is None:
            probs.append("window must be {from, to} dates")
        c = s.get("corroboration")
        if not isinstance(c, int) or isinstance(c, bool) or c < 0:
            probs.append("corroboration must be a count")
        elif recs and c > len(tier1):
            F.add("inbox.corroboration", rel, ent, f"corroboration {c} but {len(tier1)} distinct tier-1 record type(s) — tier-2 records never raise it")
        when = to_date(s.get("proposed_at")) or (to_date(w.get("to")) if isinstance(w, dict) else None) or to_date(s.get("date"))
    else:  # a single-record stub
        if to_date(s.get("date")) is None:
            probs.append("date missing or not a date")
        src = s.get("source")
        if not isinstance(src, dict) or blank(src.get("surface")) or blank(src.get("ref")):
            probs.append("source must be {surface, ref}")
            src = {}
        if blank(s.get("description_draft")):
            probs.append("no description_draft")
        if s.get("people") is not None and not isinstance(s.get("people"), list):
            probs.append("people must be a list")
        if s.get("tier") is not None and s.get("tier") not in (1, 2):
            probs.append(f"tier {s.get('tier')!r} not 1 or 2")
        t2 = s.get("tier") == 2 or (s.get("tier") is None and str(src.get("surface", "")).lower() in TIER2_SURFACES)
        if t2 and blank(s.get("excerpt")):
            F.add("inbox.excerpt", rel, ent, f"tier-2 ({src.get('surface')}) with no excerpt — capture it before confirming")
        when = to_date(s.get("proposed_at")) or to_date(s.get("date"))
    if probs:
        F.add("inbox.shape", rel, ent, "; ".join(probs))
    for k, pool in (("suggested_ex", EX), ("suggested_tu", TU)):
        v = s.get(k)
        if not blank(v) and v not in pool:
            F.add("inbox.ref", rel, ent, f"{k} {v} does not exist")
    seen = set()
    for txt in _strings(s):
        for kind, n in LABEL_RE.findall(txt):
            key = (kind.upper(), int(n))
            if key in seen:
                continue
            seen.add(key)
            if key[1] not in num[key[0]]:
                F.add("inbox.label-ref", rel, ent, f"label sred-{kind.lower()}-{n} names {key[0]}-{key[1]:02d}, which does not exist")
    if when and (as_of - when).days > 90:
        F.add("inbox.stale", rel, ent, f"waiting since {when} ({(as_of - when).days} days) — confirm, reject or note why it waits")


def _names(item):
    if isinstance(item, str):
        return {item.strip().lower()}
    if isinstance(item, dict):
        return {str(item[k]).strip().lower() for k in ("id", "label", "area") if not blank(item.get(k))}
    return set()


def check_criteria(F, sred, TU, as_of):
    p = sred / "criteria.yaml"
    if p.exists():
        rel = "sred/criteria.yaml"
        try:
            c = yload(p)
        except Exception as e:
            F.add("schema.parse", rel, "criteria", f"does not parse: {str(e).splitlines()[0]}")
            c = None
        if c is not None and not isinstance(c, dict):
            F.add("schema.parse", rel, "criteria", "is not a YAML mapping")
        elif isinstance(c, dict):
            probs = []
            if c.get("status") not in ("draft", "reviewed"):
                probs.append(f"status {c.get('status')!r} not draft | reviewed")
            if c.get("layer") is not None and c.get("layer") != 2:
                probs.append(f"layer {c.get('layer')!r} should be 2")
            areas = c.get("candidate_uncertainty_areas")
            if areas is not None and not isinstance(areas, list):
                probs.append("candidate_uncertainty_areas must be a list")
                areas = []
            areas = areas or []
            for i, a in enumerate(areas):
                if not isinstance(a, dict) or not _names(a):
                    probs.append(f"candidate_uncertainty_areas[{i}] needs an id, label or area")
            routine = c.get("declared_routine")
            if routine is not None and not isinstance(routine, list):
                probs.append("declared_routine must be a list")
                routine = []
            routine = routine or []
            for i, r in enumerate(routine):
                if not (isinstance(r, str) or (isinstance(r, dict) and _names(r))):
                    probs.append(f"declared_routine[{i}] must be a string or {{label, linked_milestones}}")
            if probs:
                F.add("criteria.shape", rel, "criteria", "; ".join(probs))
            rnames = set().union(*[_names(r) for r in routine]) if routine else set()
            for a in areas:
                if not isinstance(a, dict):
                    continue
                aid = a.get("id") or a.get("label") or a.get("area")
                both = _names(a) & rnames
                if both:
                    F.add("criteria.overlap", rel, aid, f"{', '.join(sorted(both))} is both a candidate area and declared routine")
                text = " ".join(str(a.get(k) or "") for k in ("id", "label", "area", "description")).lower()
                for phrase in LAYER0_PHRASES:
                    if phrase in text:
                        F.add("criteria.layer0", rel, aid, f"names {phrase!r}, which Layer 0 rules out regardless of criteria")
                for t in as_list(a.get("linked_tus")):
                    if t not in TU:
                        F.add("ref.dangling", rel, aid, f"linked TU {t} does not exist")
            # §7 #17 — staleness
            rv = c.get("review") if isinstance(c.get("review"), dict) else {}
            refreshed = to_date(rv.get("last_refreshed")) or to_date(c.get("reviewed_date")) or to_date(c.get("reviewed_on"))
            started = to_date(c.get("created")) or refreshed
            if c.get("status") == "draft" and started and (as_of - started).days > 90:
                F.add("criteria.stale", rel, "criteria", f"still draft {(as_of - started).days} days after {started} — PL and advisor review flips it to reviewed")
            if refreshed and (as_of - refreshed).days > 182:
                F.add("criteria.stale", rel, "criteria", f"last refreshed {refreshed}, more than two quarters ago")
            # §7 #18 — TU milestones in a routine entry that names milestones
            for r in routine:
                if isinstance(r, dict):
                    ms = {str(m) for m in as_list(r.get("linked_milestones"))}
                    for tid, t in TU.items():
                        hit = ms & {str(m) for m in as_list(t.get("linked_milestones"))}
                        if hit:
                            F.add("criteria.routine-milestone", t["_path"], tid, f"linked to {', '.join(sorted(hit))}, which criteria declare routine ({r.get('label') or r.get('id')}) — one of them is wrong")
    p = sred / "company-criteria.yaml"
    if p.exists():
        rel = "sred/company-criteria.yaml"
        try:
            c = yload(p)
        except Exception as e:
            F.add("schema.parse", rel, "company-criteria", f"does not parse: {str(e).splitlines()[0]}")
            return
        if not isinstance(c, dict):
            F.add("schema.parse", rel, "company-criteria", "is not a YAML mapping")
            return
        probs = []
        if c.get("layer") is not None and c.get("layer") != 1:
            probs.append(f"layer {c.get('layer')!r} should be 1")
        for k in ("technology_baseline", "fields_of_science"):
            if c.get(k) is not None and not isinstance(c.get(k), list):
                probs.append(f"{k} must be a list")
        if probs:
            F.add("criteria.shape", rel, "company-criteria", "; ".join(probs))


def _layer0_phrases():
    try:
        items = (yload(CAP / "schema" / "eligibility-baseline.yaml") or {}).get("not_eligible_regardless_of_criteria") or []
    except Exception:
        items = []
    out = []
    for it in items:
        for part in re.split(r",|/", str(it)):
            part = part.strip().lower()
            # only the short, distinctive activity names — a long clause ("adopting or integrating known tools where...")
            # is judgement, not a phrase, and is left to the reviewer (SKIPPED)
            if part and len(part.split()) <= 3 and part not in ("style",):
                out.append(part)
    return out


LAYER0_PHRASES = _layer0_phrases()


# ── command line ─────────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("facility", nargs="?")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="a warning also exits 1")
    ap.add_argument("--as-of", help="evaluate ages against this date (default today)")
    ap.add_argument("--rules", action="store_true", help="print the rule table and exit")
    a = ap.parse_args(argv)
    if a.rules:
        if a.json:
            print(json.dumps([{"rule": k, "severity": s, "source": src, "checks": d} for k, (s, src, d) in RULES.items()]
                             + [{"rule": r, "severity": "not checked", "source": "", "checks": w} for r, w in SKIPPED], indent=1, ensure_ascii=False))
        else:
            for k, (s, src, d) in RULES.items():
                print(f"{s:4}  {k:28} {src:24} {d}")
            for r, w in SKIPPED:
                print(f"skip  {r}: {w}")
        return 0
    if not a.facility:
        ap.print_usage(sys.stderr)
        print("check: a facility path is required", file=sys.stderr)
        return 2
    as_of = None
    if a.as_of:
        as_of = to_date(a.as_of)
        if as_of is None:
            print(f"check: --as-of {a.as_of!r} is not a YYYY-MM-DD date", file=sys.stderr)
            return 2
    fac = Path(a.facility)
    if not (fac / "manifest.yaml").exists() and (fac / "project-state" / "manifest.yaml").exists():
        fac = fac / "project-state"
    if not (fac / "manifest.yaml").exists():
        print(f"check: no manifest.yaml in {a.facility}", file=sys.stderr)
        return 2
    out = check(fac, as_of, a.strict)
    if a.json:
        print(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    else:
        if not out["enabled"] and not (fac / "sred").is_dir():
            print("sred check: the sred capability is not enabled here and there is no sred/ — nothing to check")
            return 0
        def order(f):
            path, _, line = f["path"].partition(":")
            return (f["severity"] != "fail", path, int(line) if line.isdigit() else 0, f["rule"])
        for f in sorted(out["findings"], key=order):
            print(f"{'✗' if f['severity'] == 'fail' else '·'} {f['severity']:4} [{f['rule']}] {f['path']} {f['entity']}: {f['message']}")
        print(f"sred check (as of {out['as_of']}): {out['fails']} fail(s), {out['warns']} warning(s)" + (" — clean" if out["ok"] and not out["warns"] else " — no fails" if out["ok"] else ""))
        print("not checked: " + "; ".join(r for r, _ in SKIPPED) + " (--rules says why)")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
