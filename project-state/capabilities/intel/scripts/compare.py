#!/usr/bin/env python3
"""compare — the deterministic half of intel-compare (the comparison matrix, docs/INTEL-COMPARE-AND-MAP-SPEC.md §1).

    python3 compare.py <facility> plan [--audience ID] [--json]
    python3 compare.py <facility> assemble <draft.json> [--slug S] [--generated-at ISO]   → the projection, on stdout
    python3 compare.py <facility> check [<matrix.md> ...] [--json]                          → validator check 22

plan      For each subject (self first, then the competitors in scope) and each dimension, the candidate claims:
          current claims on that subject in the dimension's categories, with status, confidence, freshness and any
          open conflict. What the skill chooses from. Cells with no candidate are listed: they will be "no claim".
assemble  Takes the skill's picks — per cell the claims it cites, a short phrase and, on a scored dimension, a score —
          and derives everything else: each cell's evidence state, the stale overlay, which scores are provisional,
          the self-against-competitor strip, the totals with their coverage, the health block. Renders the
          projection. It refuses a draft that cites a missing, superseded or wrong-subject claim, cites one side of
          an open conflict without the other, scores a cell that has no evidence, or scores off the dimension's scale.
check     Recomputes a written matrix from its own cells, as of the day it was generated, and reports every
          disagreement; a hash that differs from state/intel.json is a fork.

Reads only. The skill writes the projection and its hash through project-state.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intel_lib import Facility, sha256, split_front, to_date, yload  # noqa: E402

import yaml  # noqa: E402  (intel_lib exits with a message when it is missing)

DEFAULTS = Path(__file__).resolve().parent.parent / "templates" / "dimensions.yaml"
EVIDENCED_STATUS = {"verified", "reported"}
GOOD_CONFIDENCE = {"medium", "high"}
PRIORITY = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
RANK_MIN_COVERAGE = 0.6


class DraftError(ValueError):
    pass


# ── configuration ────────────────────────────────────────────────────────────
def dimensions(f: Facility, audience=None, only=None):
    """The manifest's dimensions, else the shipped defaults; filtered to an audience and to `only` ids."""
    raw = f.comp.get("dimensions") or (yload(DEFAULTS) or {}).get("dimensions") or []
    out = []
    for d in raw:
        if not isinstance(d, dict) or not d.get("id"):
            continue
        aud = d.get("audiences") or []
        if audience and aud and audience not in aud:
            continue
        if only and d["id"] not in only:
            continue
        scale = {int(k): str(v) for k, v in (d.get("scale") or {}).items()}
        out.append({"id": d["id"], "label": d.get("label") or d["id"], "question": d.get("question") or "",
                    "categories": list(d.get("categories") or []), "scored": bool(scale), "scale": scale})
    return out


def audiences(f: Facility):
    return {a["id"]: a for a in (f.comp.get("audiences") or []) if isinstance(a, dict) and a.get("id")}


def min_coverage(f: Facility):
    return float(((f.comp.get("compare") or {}).get("rank_min_coverage")) or RANK_MIN_COVERAGE)


def subjects(f: Facility, only=None):
    """self first, then the in-scope competitors by priority, then name."""
    comp = sorted(f.in_scope(), key=lambda e: (PRIORITY.get(str(f.entities[e].get("priority")), 9), str(f.name(e))))
    ids = ([f.self_id] if f.self_id in f.entities else []) + [e for e in comp if e != f.self_id]
    return [e for e in ids if not only or e in only]


# ── claims ───────────────────────────────────────────────────────────────────
def conflict_partners(f: Facility):
    out = {}
    for a, b in f.open_conflicts():
        out.setdefault(a, set()).add(b)
        out.setdefault(b, set()).add(a)
    return out


def info(f: Facility, c, partners):
    return {"id": c["id"], "category": c.get("category"), "statement": c.get("statement"), "status": c.get("epistemic_status"),
            "confidence": c.get("confidence"), "freshness": f.freshness(c), "material": bool(c.get("material")),
            "conflicts_with": sorted(partners.get(c["id"], ()))}


def plan(f: Facility, audience=None, only_subjects=None, only_dims=None):
    partners = conflict_partners(f)
    subs, dims = subjects(f, only_subjects), dimensions(f, audience, only_dims)
    cells, empty = [], []
    for s in subs:
        for d in dims:
            cands = sorted(f.current_claims(s, d["categories"]), key=lambda c: str(c.get("created") or ""))
            cells.append({"subject": s, "dimension": d["id"], "candidates": [info(f, c, partners) for c in cands]})
            if not cands:
                empty.append({"subject": s, "dimension": d["id"]})
    return {"as_of": f.as_of.isoformat(), "audience": audience, "self": f.self_id,
            "subjects": [{"id": s, "name": f.name(s), "self": s == f.self_id, "priority": f.entities[s].get("priority")} for s in subs],
            "dimensions": dims, "cells": cells, "empty": empty}


def derive(f: Facility, ids, partners):
    """A cell's evidence state from the claims it cites (spec §1.3): the weakest claim decides."""
    cs = [f.claims[i] for i in ids if i in f.claims]
    if not cs:
        return "no-claim", False
    stale = any(f.freshness(c) == "stale" for c in cs)
    if any(partners.get(c["id"], set()) & set(ids) for c in cs):
        return "contested", stale
    known = [c for c in cs if c.get("epistemic_status") != "unknown"]
    if not known:
        return "unknown", stale
    if all(c.get("epistemic_status") in EVIDENCED_STATUS and c.get("confidence") in GOOD_CONFIDENCE for c in known):
        return "evidenced", stale
    return "inferred", stale


# ── assembly ─────────────────────────────────────────────────────────────────
def _score_ok(score, dim):
    return isinstance(score, int) and not isinstance(score, bool) and score in dim["scale"]


def build(f: Facility, draft: dict, strict=True):
    """Cells, versus, totals and health from a draft. strict=False collects problems instead of raising (check)."""
    problems = []

    def bad(msg):
        if strict:
            raise DraftError(msg)
        problems.append(msg)

    audience = draft.get("audience")
    if audience and audience not in audiences(f):
        bad(f"audience {audience!r} is not declared in competitive.audiences")
    subs = subjects(f, draft.get("subjects"))
    dims = dimensions(f, audience, draft.get("dimensions"))
    dim_by = {d["id"]: d for d in dims}
    partners = conflict_partners(f)
    picks = {}
    for c in draft.get("cells") or []:
        key = (c.get("subject"), c.get("dimension"))
        if key[0] not in subs or key[1] not in dim_by:
            bad(f"cell {key} is not a subject × dimension of this matrix")
            continue
        picks[key] = c
    cells = []
    for s in subs:
        for d in dims:
            p = picks.get((s, d["id"])) or {}
            ids = list(dict.fromkeys(p.get("claims") or []))
            value = (p.get("value") or "").strip()
            for i in ids:
                c = f.claims.get(i)
                if c is None:
                    bad(f"{s} · {d['id']}: {i} does not exist")
                elif f.subject(c) != s:
                    bad(f"{s} · {d['id']}: {i} is about {f.subject(c)}, not {s}")
                elif not f.current(c, f.as_of):
                    bad(f"{s} · {d['id']}: {i} was superseded by {f.superseded_by.get(i)}; cite the current claim")
                else:
                    missing = sorted(o for o in partners.get(i, ()) if o not in ids and f.subject(f.claims[o]) == s)
                    if missing:
                        bad(f"{s} · {d['id']}: {i} is in an open conflict with {', '.join(missing)}; cite both sides")
            if ids and not value:
                bad(f"{s} · {d['id']}: claims are cited but the cell has no phrase")
            if value and not ids:
                bad(f"{s} · {d['id']}: the phrase {value!r} cites no claim (an unsourced cell)")
            state, stale = derive(f, ids, partners) if ids else ("no-claim", False)
            score = p.get("score")
            if score is not None:
                if not d["scored"]:
                    bad(f"{s} · {d['id']}: the dimension is descriptive; it takes no score")
                    score = None
                elif state in ("unknown", "no-claim"):
                    bad(f"{s} · {d['id']}: {'an unknown' if state == 'unknown' else 'a no-claim'} cell takes no score (it is not a zero)")
                    score = None
                elif state == "contested":
                    if not (isinstance(score, list) and len(score) == 2 and all(_score_ok(x, d) for x in score)):
                        bad(f"{s} · {d['id']}: a contested cell is scored once per side, [a, b], on the scale")
                        score = None
                elif not _score_ok(score, d):
                    bad(f"{s} · {d['id']}: score {score!r} is not on the scale {sorted(d['scale'])}")
                    score = None
            cells.append({"subject": s, "dimension": d["id"], "value": value or None, "claims": ids, "state": state,
                          "score": score, "provisional": bool(state == "inferred" and score is not None), "stale": stale})
    return {"audience": audience, "subjects": subs, "dimensions": dims, "cells": cells,
            "versus": versus(f, cells, dims), "totals": totals(f, cells, dims, audience), "health": health(cells, dims)}, problems


def _single(c):
    return c["state"] in ("evidenced", "inferred") and isinstance(c["score"], int)


def versus(f: Facility, cells, dims):
    """Self against each competitor, per scored dimension, where both cells carry a single score."""
    me = f.self_id
    if not me:
        return []
    by = {(c["subject"], c["dimension"]): c for c in cells}
    out = []
    for d in dims:
        if not d["scored"]:
            continue
        mine = by.get((me, d["id"]))
        for s in sorted({c["subject"] for c in cells} - {me}, key=lambda x: [c["subject"] for c in cells].index(x)):
            theirs = by.get((s, d["id"]))
            if not mine or not theirs or not _single(mine) or not _single(theirs):
                continue
            rel = "ahead" if mine["score"] > theirs["score"] else "behind" if mine["score"] < theirs["score"] else "level"
            out.append({"dimension": d["id"], "competitor": s, "relation": rel, "provisional": mine["provisional"] or theirs["provisional"]})
    return out


def _weights(f: Facility, dims, audience):
    if audience is None:
        return {d["id"]: 1 for d in dims if d["scored"]}
    w = (audiences(f).get(audience) or {}).get("weights") or {}
    return {d["id"]: float(w.get(d["id"], 0)) for d in dims if d["scored"] and float(w.get(d["id"], 0)) > 0}


def totals(f: Facility, cells, dims, audience):
    """Per audience: score over scored cells only, coverage of the weight by evidenced cells, provisional share.
    `all` is unweighted; each audience with weights gets its own block (an audience matrix: only its own)."""
    keys = [audience] if audience else ["all"] + [a for a, d in audiences(f).items() if d.get("weights")]
    floor = min_coverage(f)
    out = {}
    for key in keys:
        w = _weights(f, dims, None if key == "all" else key)
        total_w = sum(w.values())
        rows = []
        for s in dict.fromkeys(c["subject"] for c in cells):
            mine = [c for c in cells if c["subject"] == s and c["dimension"] in w and _single(c)]
            sw = sum(w[c["dimension"]] for c in mine)
            ev = sum(w[c["dimension"]] for c in mine if c["state"] == "evidenced")
            score = round(sum(w[c["dimension"]] * c["score"] for c in mine) / sw, 2) if sw else None
            coverage = round(ev / total_w, 2) if total_w else 0.0
            rows.append({"subject": s, "score": score, "coverage": coverage,
                         "provisional_share": round((sw - ev) / sw, 2) if sw else 0.0, "ranked": bool(score is not None and coverage >= floor)})
        rows.sort(key=lambda r: (not r["ranked"], -(r["score"] or 0)))
        out[key] = {"weights": w, "rank_min_coverage": floor, "rows": rows}
    return out


def health(cells, dims):
    scored_dims = {d["id"] for d in dims if d["scored"]}
    n = lambda st: sum(1 for c in cells if c["state"] == st)  # noqa: E731
    return {"cells": len(cells), "evidenced": n("evidenced"), "inferred": n("inferred"), "unknown": n("unknown"), "no_claim": n("no-claim"),
            "contested": n("contested"), "stale": sum(1 for c in cells if c["stale"]), "scored": sum(1 for c in cells if c["score"] is not None),
            "unscored_in_scored_dimensions": sum(1 for c in cells if c["dimension"] in scored_dims and c["score"] is None and c["state"] in ("evidenced", "inferred")),
            "unsourced_cells": sum(1 for c in cells if c["value"] and not c["claims"]),
            "scores_on_unknown": sum(1 for c in cells if c["score"] is not None and c["state"] in ("unknown", "no-claim"))}


# ── rendering ────────────────────────────────────────────────────────────────
def _esc(s):
    return str(s or "").replace("|", "/").replace("\n", " ").strip()


def _cell_text(c, dim):
    if c["state"] == "no-claim":
        return ""
    ids = " ".join(f"[{i}]" for i in c["claims"])
    sc = c["score"]
    if c["state"] == "contested":
        score = f" · {sc[0]}/{sc[1]}" if isinstance(sc, list) else ""
        text = f"{_esc(c['value'])} (contested){score} {ids}"
    elif c["state"] == "unknown":
        text = f"{_esc(c['value'])} (unknown) · — {ids}"
    elif c["state"] == "inferred":
        text = f"*{_esc(c['value'])}* (inferred){f' · ~{sc}' if sc is not None else ''} {ids}"
    else:
        text = f"{_esc(c['value'])}{f' · **{sc}**' if sc is not None else ''} {ids}"
    return text + (" (stale)" if c["stale"] else "")


def render(f: Facility, m: dict, slug: str, generated_at: str) -> str:
    dims, cells, subs = m["dimensions"], m["cells"], m["subjects"]
    by = {(c["subject"], c["dimension"]): c for c in m["cells"]}
    name = lambda s: ("us · " if s == f.self_id else "") + str(f.name(s))  # noqa: E731
    claims = sorted({i for c in cells for i in c["claims"]})
    fm = {"kind": "matrix", "slug": slug, "audience": m["audience"], "generated_at": generated_at, "generator": "intel-compare",
          "subjects": [{"id": s, "name": f.name(s), "self": s == f.self_id} for s in subs],
          "dimensions": [{"id": d["id"], "label": d["label"], "scored": d["scored"], **({"scale": d["scale"]} if d["scored"] else {})} for d in dims],
          "cells": cells, "versus": m["versus"], "totals": m["totals"], "claims": claims, "health": m["health"]}
    head = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=1000)
    aud = m["audience"]
    L = [f"# Comparison matrix — {aud if aud else 'all audiences'}", "",
         "> Generated from claims; not edited. Every cell cites its claims and is worded at the level of its weakest claim.",
         "> Scores read from the buyer's side on each dimension's 1–5 scale. `~` marks a provisional score resting on inferred or",
         "> low-confidence evidence; `—` means no score (unknown, or nobody has looked). A total weights what is evidenced; it is not a verdict.", "",
         "## The grid", "", "| | " + " | ".join(_esc(d["label"]) for d in dims) + " |", "|---|" + "---|" * len(dims)]
    for s in subs:
        L.append(f"| **{_esc(name(s))}** | " + " | ".join(_cell_text(by[(s, d['id'])], d) for d in dims) + " |")
    for key, t in m["totals"].items():
        L += ["", f"## Totals — {'unweighted, every scored dimension' if key == 'all' else key}", "",
              "| Subject | Score | Coverage of the weight | Provisional share | Ranked |", "|---|---|---|---|---|"]
        for r in t["rows"]:
            L.append(f"| {_esc(name(r['subject']))} | {r['score'] if r['score'] is not None else '—'} | {round(100 * r['coverage'])}% | "
                     f"{round(100 * r['provisional_share'])}% | {'yes' if r['ranked'] else 'no — not enough evidence to rank'} |")
    comps = [s for s in subs if s != f.self_id]
    if m["versus"] and comps:
        L += ["", "## Us against each competitor", "", "| Dimension | " + " | ".join(_esc(f.name(s)) for s in comps) + " |", "|---|" + "---|" * len(comps)]
        rel = {(v["dimension"], v["competitor"]): v["relation"] + (" (provisional)" if v["provisional"] else "") for v in m["versus"]}
        for d in dims:
            if d["scored"] and any((d["id"], s) in rel for s in comps):
                L.append(f"| {_esc(d['label'])} | " + " | ".join(rel.get((d["id"], s), "") for s in comps) + " |")
    thin = []
    for s in subs:
        gaps = [d for d in dims if by[(s, d["id"])]["state"] == "no-claim"]
        if gaps:
            cats = sorted({c for d in gaps for c in d["categories"]})
            run = "/intel-harvester competitor self" if s == f.self_id else f"/intel-harvester competitor {s}"
            thin.append(f"- **{_esc(name(s))}**: nothing on {', '.join(d['label'].lower() for d in gaps)} — `{run}` scoped to {', '.join(cats)}.")
    L += ["", "## Where the picture is thin", ""] + (thin or ["- Every cell has a claim behind it."])
    L += ["", "## How the scores were made", ""]
    for d in dims:
        if d["scored"]:
            L.append(f"- **{_esc(d['label'])}** — " + "; ".join(f"{k} = {_esc(v)}" for k, v in sorted(d["scale"].items())) + ".")
    for key, t in m["totals"].items():
        if key != "all":
            L.append(f"- Weights for **{key}**: " + ", ".join(f"{k} {v:g}" for k, v in t["weights"].items()) + ".")
    floor = next(iter(m["totals"].values()))["rank_min_coverage"] if m["totals"] else RANK_MIN_COVERAGE
    L += [f"- A subject is ranked only when evidenced cells carry at least {round(100 * floor)}% of the weight.",
          "", "## What this matrix does not say", "",
          "- Nothing about a cell marked — or left empty: an unknown is a search that found nothing; an empty cell is a question nobody has asked yet.",
          "- A total is a weighting of what is evidenced on these dimensions for this audience, not a verdict on the products.",
          "- A score sits at the lower of two rubric levels when the evidence falls between them."]
    return "---\n" + head + "---\n\n" + "\n".join(L) + "\n"


def assemble(f: Facility, draft: dict, slug=None, generated_at=None) -> str:
    m, _ = build(f, draft, strict=True)
    generated_at = generated_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    slug = slug or draft.get("slug") or (f"{m['audience']}-" if m["audience"] else "") + f"comparison-{generated_at[:7]}"
    return render(f, m, slug, generated_at)


# ── the check (validator 22) ─────────────────────────────────────────────────
def check(f: Facility, path: Path):
    text = path.read_text(encoding="utf-8")
    fm, _ = split_front(text)
    rel = str(path.relative_to(f.root)) if path.is_relative_to(f.root) else str(path)
    if fm.get("kind") != "matrix":
        return [f"{rel}: not a matrix (kind {fm.get('kind')!r})"]
    on = to_date(fm.get("generated_at")) or f.as_of
    g = Facility(f.root, on.isoformat())
    draft = {"audience": fm.get("audience"), "subjects": [s["id"] for s in fm.get("subjects") or []],
             "dimensions": [d["id"] for d in fm.get("dimensions") or []],
             "cells": [{k: c.get(k) for k in ("subject", "dimension", "value", "claims", "score")} for c in fm.get("cells") or []]}
    m, problems = build(g, draft, strict=False)
    problems = [f"{rel}: {p}" for p in problems]
    stored = {(c["subject"], c["dimension"]): c for c in fm.get("cells") or []}
    for c in m["cells"]:
        s = stored.get((c["subject"], c["dimension"])) or {}
        for k in ("state", "provisional", "stale"):
            if s.get(k) != c[k]:
                problems.append(f"{rel}: {c['subject']} · {c['dimension']}: {k} is {s.get(k)!r}, the claims say {c[k]!r}")
    for k in ("versus", "totals", "health"):
        if json.loads(json.dumps(fm.get(k), default=str)) != json.loads(json.dumps(m[k], default=str)):
            problems.append(f"{rel}: {k} does not match what compare.py computes from the cells")
    cited = sorted({i for c in m["cells"] for i in c["claims"]})
    if sorted(fm.get("claims") or []) != cited:
        problems.append(f"{rel}: frontmatter claims: differs from the ids the cells cite")
    rec = ((f.state.get("projections") or {}).get(rel)) or {}
    want = rec.get("sha256") if isinstance(rec, dict) else rec
    if want and sha256(text) != want:
        problems.append(f"{rel}: fork — the file was edited after generation; regenerate it")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("facility")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("plan"); p1.add_argument("--audience"); p1.add_argument("--as-of"); p1.add_argument("--json", action="store_true")
    p2 = sub.add_parser("assemble"); p2.add_argument("draft"); p2.add_argument("--slug"); p2.add_argument("--generated-at"); p2.add_argument("--as-of")
    p3 = sub.add_parser("check"); p3.add_argument("files", nargs="*"); p3.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    f = Facility(a.facility, getattr(a, "as_of", None))
    if a.cmd == "plan":
        out = plan(f, a.audience)
        if a.json:
            print(json.dumps(out, indent=2, default=str))
        else:
            print(f"{len(out['subjects'])} subjects × {len(out['dimensions'])} dimensions as of {out['as_of']}; {len(out['empty'])} cell(s) with no candidate claim")
            for c in out["cells"]:
                print(f"  {c['subject']} · {c['dimension']}: " + (", ".join(f"{x['id']} ({x['status']}, {x['confidence']}, {x['freshness']})" for x in c["candidates"]) or "—"))
        return 0
    if a.cmd == "assemble":
        draft = json.loads(Path(a.draft).read_text(encoding="utf-8"))
        try:
            sys.stdout.write(assemble(f, draft, a.slug, a.generated_at))
        except DraftError as e:
            print(f"compare: refused — {e}", file=sys.stderr)
            return 1
        return 0
    files = [Path(x) for x in a.files] or sorted((f.root / "intel" / "matrices").glob("*.md"))
    problems = [p for x in files for p in check(f, x.resolve())]
    if a.json:
        print(json.dumps({"checked": len(files), "problems": problems}, indent=2))
    else:
        print(f"{len(files)} matrix file(s) checked, {len(problems)} problem(s)")
        for p in problems:
            print(f"  {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
