#!/usr/bin/env python3
"""wardley — the deterministic half of intel-map (the Wardley map, docs/INTEL-COMPARE-AND-MAP-SPEC.md §2).

    python3 wardley.py <facility> plan <map-id> [--json]
    python3 wardley.py <facility> assemble <map-id> <draft.json> [--generated-at ISO]   → the projection, on stdout
    python3 wardley.py <facility> svg <intel/maps/<id>.md>                              → the drawing, on stdout
    python3 wardley.py <facility> owm <intel/maps/<id>.md>                              → OnlineWardleyMaps text
    python3 wardley.py <facility> check [<intel/maps/<id>.md> ...] [--json]             → validator check 23

What is ON the map is declared in the manifest (capabilities.intel.competitive.maps: user, need, components and
their dependencies); where each component SITS, and who plays where, is generated from claims by intel-map.

plan      The declared map, validated (ids unique, dependencies resolve, no cycle), each component's depth in the
          value chain, and the candidate claims: current claims in the map's categories, every subject.
assemble  Takes the skill's placements — per component a stage, a position and the claims behind each of Wardley's
          four characteristics — plus players and notes, and derives the rest: the epistemic status (two or more
          characteristics evidenced → inferred, one or none → hypothesis; never verified), the stale-basis overlay,
          the moves since the last generation (from state/intel.json), the health. It refuses an undeclared or
          unplaced component, a position outside its stage's band, a missing or superseded claim, a player without
          a product, feature or integration claim about it, a hypothesis with no rationale, and a notes line that
          cites nothing.
check     Recomputes a written map from its own placements, as of the day it was generated; a hash that differs
          from state/intel.json is a fork.

Reads only; the skill writes through project-state.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intel_lib import Facility, sha256, split_front, to_date  # noqa: E402

import yaml  # noqa: E402

STAGES = [("genesis", 0.0, 0.17), ("custom", 0.17, 0.40), ("product", 0.40, 0.70), ("commodity", 0.70, 1.0)]
STAGE_LABEL = {"genesis": "Genesis", "custom": "Custom-built", "product": "Product (+rental)", "commodity": "Commodity (+utility)"}
CHARACTERISTICS = ["ubiquity", "certainty", "market", "practice"]
PLAYER_CATEGORIES = {"product", "feature", "integration"}
MOVE_SHIFT = 0.15
CITE = re.compile(r"\[(?:MAP:[a-z0-9-]+|INT-C-\d{3,})(?:\s*,\s*(?:MAP:[a-z0-9-]+|INT-C-\d{3,}))*\]")


class MapError(ValueError):
    pass


def band(stage):
    for s, lo, hi in STAGES:
        if s == stage:
            return lo, hi
    raise MapError(f"unknown stage {stage!r} (genesis, custom, product, commodity)")


def stage_index(stage):
    return [s for s, _, _ in STAGES].index(stage)


# ── the declared map ─────────────────────────────────────────────────────────
def declared(f: Facility, map_id):
    for m in f.comp.get("maps") or []:
        if isinstance(m, dict) and m.get("id") == map_id:
            return m
    raise MapError(f"no map {map_id!r} in capabilities.intel.competitive.maps")


def validate(m):
    problems = []
    comps = m.get("components") or []
    ids = [c.get("id") for c in comps]
    if not m.get("user") or not m.get("need"):
        problems.append("the anchor needs a user and a need")
    if len(set(ids)) != len(ids) or not all(ids):
        problems.append("component ids must be present and unique")
    known = set(ids)
    for c in comps:
        for d in c.get("depends_on") or []:
            if d not in known:
                problems.append(f"{c.get('id')} depends on {d}, which is not declared")
    # cycles
    graph = {c.get("id"): list(c.get("depends_on") or []) for c in comps}
    state = {}

    def visit(n, stack):
        if state.get(n) == 1:
            problems.append("dependency cycle: " + " → ".join(stack + [n]))
            return
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in graph.get(n, []):
            if d in graph:
                visit(d, stack + [n])
        state[n] = 2
    for n in graph:
        visit(n, [])
    return problems


def depths(m):
    """Depth in the value chain: a component nothing depends on sits just under the anchor (1); a dependency sits
    one below the deepest component that needs it."""
    comps = {c["id"]: c for c in m.get("components") or []}
    parents = {i: [p for p, c in comps.items() if i in (c.get("depends_on") or [])] for i in comps}
    memo = {}

    def d(i, seen=()):
        if i in memo:
            return memo[i]
        if i in seen:
            return 1
        ps = parents[i]
        memo[i] = 1 if not ps else 1 + max(d(p, seen + (i,)) for p in ps)
        return memo[i]
    return {i: d(i) for i in comps}


def plan(f: Facility, map_id):
    m = declared(f, map_id)
    probs = validate(m)
    cats = set(m.get("categories") or ["product", "feature", "integration", "market", "pricing"])
    cands = [{"id": c["id"], "subject": f.subject(c), "subject_name": f.name(f.subject(c)), "category": c.get("category"), "statement": c.get("statement"),
              "status": c.get("epistemic_status"), "confidence": c.get("confidence"), "freshness": f.freshness(c)}
             for c in sorted(f.current_claims(None, cats), key=lambda c: c["id"])]
    dp = depths(m) if not probs else {}
    return {"as_of": f.as_of.isoformat(), "map": map_id, "user": m.get("user"), "need": m.get("need"), "problems": probs,
            "components": [{**c, "depth": dp.get(c["id"])} for c in m.get("components") or []], "categories": sorted(cats), "candidates": cands}


# ── assembly ─────────────────────────────────────────────────────────────────
def build(f: Facility, m: dict, draft: dict, previous=None, strict=True):
    problems = []

    def bad(msg):
        if strict:
            raise MapError(msg)
        problems.append(msg)
    for p in validate(m):
        bad(p)
    comps = {c["id"]: c for c in m.get("components") or []}
    dp = depths(m) if not problems else {i: 1 for i in comps}

    def claim_ok(i, where):
        c = f.claims.get(i)
        if c is None:
            bad(f"{where}: {i} does not exist")
            return False
        if not f.current(c, f.as_of):
            bad(f"{where}: {i} was superseded by {f.superseded_by.get(i)}; cite the current claim")
            return False
        return True
    placed = {}
    for p in draft.get("placements") or []:
        cid = p.get("component")
        if cid not in comps:
            bad(f"placement for {cid!r}, which is not declared on the map")
            continue
        if cid in placed:
            bad(f"{cid} is placed twice")
            continue
        stage = p.get("stage")
        try:
            lo, hi = band(stage)
        except MapError as e:
            bad(f"{cid}: {e}")
            continue
        pos = p.get("position")
        if not isinstance(pos, (int, float)) or not (lo <= float(pos) <= hi):
            bad(f"{cid}: position {pos!r} is outside the {stage} band [{lo}, {hi}]")
            pos = round((lo + hi) / 2, 2)
        basis = {k: list(dict.fromkeys((p.get("basis") or {}).get(k) or [])) for k in CHARACTERISTICS}
        for k, ids in basis.items():
            for i in ids:
                claim_ok(i, f"{cid} · {k}")
        evidenced = [k for k, ids in basis.items() if ids]
        status = "inferred" if len(evidenced) >= 2 else "hypothesis"
        rationale = (p.get("rationale") or "").strip()
        if not evidenced and not rationale:
            bad(f"{cid}: a placement with no basis claim must state its reason (a hypothesis with no rationale)")
        all_ids = [i for ids in basis.values() for i in ids if i in f.claims]
        stale = bool(all_ids) and all(f.freshness(f.claims[i]) == "stale" or not f.current(f.claims[i], f.as_of) for i in all_ids)
        moving = p.get("moving")
        if moving:
            toward = moving.get("toward")
            try:
                band(toward)
                if stage_index(toward) <= stage_index(stage):
                    bad(f"{cid}: moving toward {toward}, which is not to the right of {stage}")
            except MapError as e:
                bad(f"{cid}: moving: {e}")
            mb = list(dict.fromkeys(moving.get("basis") or []))
            if not mb:
                bad(f"{cid}: a movement needs the claims that show it")
            for i in mb:
                claim_ok(i, f"{cid} · moving")
            moving = {"toward": toward, "basis": mb}
        placed[cid] = {"component": cid, "stage": stage, "position": round(float(pos), 2), "epistemic_status": status, "basis": basis,
                       "rationale": rationale or None, "moving": moving or None, "stale_basis": stale}
    for cid in comps:
        if cid not in placed:
            bad(f"{cid} is declared but not placed")
    players = []
    for pl in draft.get("players") or []:
        e = pl.get("entity")
        if e not in f.entities:
            bad(f"player {e!r} is not an entity")
            continue
        cs = [c for c in pl.get("components") or [] if c in comps]
        if len(cs) != len(pl.get("components") or []):
            bad(f"player {e}: names a component that is not declared")
        ids = list(dict.fromkeys(pl.get("claims") or []))
        good = []
        for i in ids:
            if claim_ok(i, f"player {e}"):
                c = f.claims[i]
                if f.subject(c) != e:
                    bad(f"player {e}: {i} is about {f.subject(c)}")
                elif c.get("category") not in PLAYER_CATEGORIES:
                    bad(f"player {e}: {i} is a {c.get('category')} claim; a player rests on product, feature or integration claims")
                else:
                    good.append(i)
        if not good:
            bad(f"player {e}: no product, feature or integration claim places it on the map")
            continue
        players.append({"entity": e, "name": f.name(e), "self": e == f.self_id, "components": cs, "claims": good})
    # moves since the previous generation (state, not the previous projection: projections do not read projections)
    moves = []
    prev = previous or {}
    for cid, pl in placed.items():
        old = prev.get(cid)
        if old is None:
            if prev:
                moves.append({"component": cid, "kind": "added", "to": pl["stage"], "position": pl["position"]})
        elif old.get("stage") != pl["stage"] or abs(float(old.get("position", 0)) - pl["position"]) >= MOVE_SHIFT:
            moves.append({"component": cid, "kind": "moved", "from": old.get("stage"), "from_position": old.get("position"), "to": pl["stage"], "position": pl["position"],
                          "basis": sorted({i for ids in pl["basis"].values() for i in ids})})
    for cid in prev:
        if cid not in placed:
            moves.append({"component": cid, "kind": "removed", "from": prev[cid].get("stage")})
    # notes: every line cites a component or a claim; every line is inference
    notes = {}
    for sec_ in ("build", "buy", "moving", "cannot_see"):
        lines = []
        for line in (draft.get("notes") or {}).get(sec_) or []:
            line = str(line).strip()
            if not CITE.search(line):
                bad(f"notes · {sec_}: a line cites nothing — {line[:60]}")
                continue
            for ref in re.findall(r"MAP:([a-z0-9-]+)", line):
                if ref not in comps:
                    bad(f"notes · {sec_}: [MAP:{ref}] is not a declared component")
            for i in re.findall(r"INT-C-\d{3,}", line):
                claim_ok(i, f"notes · {sec_}")
            lines.append(line if re.search(r"\binferred\b|\bhypothes", line, re.I) else line + " *(inferred)*")
        notes[sec_] = lines
    health = {"components": len(comps), "placed": len(placed), "inferred": sum(1 for p in placed.values() if p["epistemic_status"] == "inferred"),
              "hypothesis": sum(1 for p in placed.values() if p["epistemic_status"] == "hypothesis"),
              "stale_basis": sum(1 for p in placed.values() if p["stale_basis"]), "moving": sum(1 for p in placed.values() if p["moving"]),
              "players": len(players), "moves": len([x for x in moves if x["kind"] == "moved"])}
    placements = [placed[c] for c in comps if c in placed]
    return {"components": [{"id": c["id"], "name": c.get("name") or c["id"], "depends_on": list(c.get("depends_on") or []), "depth": dp.get(c["id"], 1)} for c in comps.values()],
            "placements": placements, "players": players, "moves": moves, "notes": notes, "health": health}, problems


def _prev(f: Facility, rel):
    rec = (f.state.get("projections") or {}).get(rel) or {}
    return rec.get("placements") if isinstance(rec, dict) else None


def render(f: Facility, m: dict, built: dict, generated_at: str) -> str:
    claims = sorted({i for p in built["placements"] for ids in p["basis"].values() for i in ids}
                    | {i for p in built["placements"] if p["moving"] for i in p["moving"]["basis"]}
                    | {i for pl in built["players"] for i in pl["claims"]}
                    | {i for ls in built["notes"].values() for line in ls for i in re.findall(r"INT-C-\d{3,}", line)})
    fm = {"kind": "map", "slug": m["id"], "user": m.get("user"), "need": m.get("need"), "generated_at": generated_at, "generator": "intel-map",
          "components": built["components"], "placements": built["placements"], "players": built["players"], "moves": built["moves"],
          "claims": claims, "health": built["health"]}
    head = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=1000)
    names = {c["id"]: c["name"] for c in built["components"]}
    L = [f"# Wardley map — {m.get('need')}", "",
         f"> For **{m.get('user')}**. Generated from claims; not edited. Every placement is an inference from Wardley's four",
         "> characteristics (ubiquity, certainty, market, practice) read from cited claims — inferred where two or more are",
         "> evidenced, a hypothesis where one or none is. Nothing on a map is verified.", "",
         "## Where to build", ""] + [f"- {l}" for l in built["notes"].get("build") or []] + ["", "## Where to buy or use", ""] + \
        [f"- {l}" for l in built["notes"].get("buy") or []] + ["", "## What is moving and what it does to us", ""] + [f"- {l}" for l in built["notes"].get("moving") or []]
    L += ["", "## What moved since the last map", ""]
    mv = []
    for x in built["moves"]:
        if x["kind"] == "moved":
            mv.append(f"- **{names.get(x['component'], x['component'])}** moved from {x['from']} ({x['from_position']}) to {x['to']} ({x['position']}) "
                      + " ".join(f"[{i}]" for i in x.get("basis") or []) + " *(inferred)*")
        else:
            mv.append(f"- **{names.get(x['component'], x['component'])}** {x['kind']} [MAP:{x['component']}]")
    L += mv or ["- Nothing moved: this is the first map, or every component held its stage. <!-- non-material -->"]
    hyp = [p for p in built["placements"] if p["epistemic_status"] == "hypothesis"]
    L += ["", "## What this map cannot see", ""] + [f"- **{names[p['component']]}** is a hypothesis: " + (", ".join(k for k, v in p["basis"].items() if v) or "no characteristic")
                                                     + " evidenced. <!-- non-material -->" for p in hyp] + [f"- {l}" for l in built["notes"].get("cannot_see") or []]
    if not hyp and not built["notes"].get("cannot_see"):
        L.append("- Every placement rests on two or more evidenced characteristics. <!-- non-material -->")
    return "---\n" + head + "---\n\n" + "\n".join(L) + "\n"


def assemble(f: Facility, map_id, draft, generated_at=None):
    m = declared(f, map_id)
    built, _ = build(f, m, draft, _prev(f, f"intel/maps/{map_id}.md"), strict=True)
    generated_at = generated_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return render(f, m, built, generated_at)


# ── drawing ──────────────────────────────────────────────────────────────────
def svg(fm: dict, width=980) -> str:
    comps = fm.get("components") or []
    places = {p["component"]: p for p in fm.get("placements") or []}
    maxd = max([c.get("depth") or 1 for c in comps] + [1])
    L, R, T, row = 90, 30, 92, 74
    H = T + maxd * row + 64
    W = width
    X = lambda pos: L + (W - L - R) * float(pos)  # noqa: E731
    Y = lambda d: T + (d - 0.5) * row  # noqa: E731
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    # inside class names and the players list a CSS selector matches (build-intel-map.py's ident): no escaping is enough there
    ident = lambda s: re.sub(r"[^A-Za-z0-9_-]", "-", str(s))  # noqa: E731
    who = {}
    for pl in fm.get("players") or []:
        for c in pl.get("components") or []:
            who.setdefault(c, []).append(pl["entity"])
    out = [f'<svg class="wm" viewBox="0 0 {W} {H}" role="img" aria-label="Wardley map: {e(fm.get("need"))}" xmlns="http://www.w3.org/2000/svg">',
           '<defs><pattern id="wm-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" class="wm-hatch"/></pattern>'
           '<marker id="wm-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" class="wm-arrowhead"/></marker></defs>']
    for i, (s, lo, hi) in enumerate(STAGES):
        out.append(f'<rect x="{X(lo):.1f}" y="{T - 30}" width="{X(hi) - X(lo):.1f}" height="{H - T - 4:.1f}" class="wm-band{i % 2}"/>'
                   f'<text x="{(X(lo) + X(hi)) / 2:.1f}" y="{H - 14}" text-anchor="middle" class="wm-stage">{e(STAGE_LABEL[s])}</text>')
    out.append(f'<line x1="{L}" y1="{H - 30}" x2="{W - R}" y2="{H - 30}" class="wm-axis" marker-end="url(#wm-arrow)"/>'
               f'<text x="{L - 10}" y="{T - 12}" text-anchor="end" class="wm-ax">visible</text><text x="{L - 10}" y="{H - 36}" text-anchor="end" class="wm-ax">invisible</text>'
               f'<line x1="{L - 4}" y1="{T - 6}" x2="{L - 4}" y2="{H - 40}" class="wm-axis"/>')
    # anchor
    out.append(f'<g class="wm-anchor"><circle cx="{L + 16}" cy="{T - 54}" r="7"/><text x="{L + 30}" y="{T - 50}" class="wm-anchor-t">{e(fm.get("user"))}</text>'
               f'<text x="{L + 30}" y="{T - 36}" class="wm-need">{e(fm.get("need"))}</text></g>')
    tops = [c for c in comps if (c.get("depth") or 1) == 1]
    for c in tops:
        p = places.get(c["id"])
        if p:
            out.append(f'<line x1="{L + 16}" y1="{T - 47}" x2="{X(p["position"]):.1f}" y2="{Y(1):.1f}" class="wm-link"/>')
    for c in comps:
        p = places.get(c["id"])
        if not p:
            continue
        for d in c.get("depends_on") or []:
            q, dc = places.get(d), next((x for x in comps if x["id"] == d), None)
            if q and dc:
                out.append(f'<line x1="{X(p["position"]):.1f}" y1="{Y(c.get("depth") or 1):.1f}" x2="{X(q["position"]):.1f}" y2="{Y(dc.get("depth") or 1):.1f}" class="wm-link"/>')
    moved = {x["component"]: x for x in fm.get("moves") or [] if x.get("kind") == "moved"}
    for c in comps:
        p = places.get(c["id"])
        if not p:
            continue
        x, y = X(p["position"]), Y(c.get("depth") or 1)
        g = [f'<g class="wm-c wm-{ident(p["epistemic_status"])}{" wm-stale" if p.get("stale_basis") else ""}" data-component="{e(c["id"])}" data-players="{e(" ".join(ident(w) for w in who.get(c["id"], [])))}">']
        mv = moved.get(c["id"])
        if mv and mv.get("from_position") is not None:
            ox = X(mv["from_position"])
            g.append(f'<circle cx="{ox:.1f}" cy="{y:.1f}" r="7" class="wm-ghost"/><line x1="{ox + 8:.1f}" y1="{y:.1f}" x2="{x - 10:.1f}" y2="{y:.1f}" class="wm-moved" marker-end="url(#wm-arrow)"/>')
        if p.get("moving"):
            lo, _ = band(p["moving"]["toward"])
            tx = max(X(lo) + 14, x + 36)
            g.append(f'<line x1="{x + 10:.1f}" y1="{y:.1f}" x2="{tx:.1f}" y2="{y:.1f}" class="wm-moving" marker-end="url(#wm-arrow)"/>')
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" class="wm-dot"/>')
        if p.get("stale_basis"):
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="url(#wm-hatch)"/>')
        g.append(f'<text x="{x + 12:.1f}" y="{y - 10:.1f}" class="wm-label">{e(c["name"])}</text>')
        g.append(f'<title>{e(c["name"])} · {e(p["stage"])} ({e(p["position"])}) · {e(p["epistemic_status"])} · basis: '
                 + "; ".join(f"{e(k)} {e(', '.join(str(x) for x in v))}" for k, v in p["basis"].items() if v) + "</title></g>")
        out.append("".join(g))
    out.append("</svg>")
    return "".join(out)


def owm(fm: dict) -> str:
    """OnlineWardleyMaps text: component Name [visibility, evolution]; visibility 1 is the top."""
    comps = fm.get("components") or []
    places = {p["component"]: p for p in fm.get("placements") or []}
    maxd = max([c.get("depth") or 1 for c in comps] + [1])
    vis = lambda d: round(0.92 - 0.84 * (d - 1) / max(1, maxd - 1), 2) if maxd > 1 else 0.6  # noqa: E731
    name = {c["id"]: c["name"] for c in comps}
    out = [f"title {fm.get('need')}", f"anchor {fm.get('user')} [0.98, 0.5]"]
    for c in comps:
        p = places.get(c["id"])
        if p:
            out.append(f"component {name[c['id']]} [{vis(c.get('depth') or 1)}, {p['position']}]" + (" label [10, -8]" if False else ""))
    for c in comps:
        if (c.get("depth") or 1) == 1:
            out.append(f"{fm.get('user')}->{name[c['id']]}")
        for d in c.get("depends_on") or []:
            out.append(f"{name[c['id']]}->{name.get(d, d)}")
    for c in comps:
        p = places.get(c["id"])
        if p and p.get("moving"):
            lo, hi = band(p["moving"]["toward"])
            out.append(f"evolve {name[c['id']]} {round(max(lo + 0.05, p['position'] + 0.1), 2)}")
    out.append(f"note Generated by intel-map {str(fm.get('generated_at'))[:10]}; every placement is an inference from cited claims [0.03, 0.75]")
    return "\n".join(out) + "\n"


# ── the check (validator 23) ─────────────────────────────────────────────────
def check(f: Facility, path: Path):
    text = path.read_text(encoding="utf-8")
    fm, _ = split_front(text)
    rel = str(path.relative_to(f.root)) if path.is_relative_to(f.root) else str(path)
    if fm.get("kind") != "map":
        return [f"{rel}: not a map (kind {fm.get('kind')!r})"]
    on = to_date(fm.get("generated_at")) or f.as_of
    g = Facility(f.root, on.isoformat())
    try:
        m = declared(g, fm.get("slug"))
    except MapError as e:
        return [f"{rel}: {e}"]
    draft = {"placements": [{k: p.get(k) for k in ("component", "stage", "position", "basis", "rationale", "moving")} for p in fm.get("placements") or []],
             "players": [{k: p.get(k) for k in ("entity", "components", "claims")} for p in fm.get("players") or []]}
    built, problems = build(g, m, draft, None, strict=False)
    problems = [f"{rel}: {p}" for p in problems]
    stored = {p["component"]: p for p in fm.get("placements") or []}
    for p in built["placements"]:
        s = stored.get(p["component"]) or {}
        for k in ("epistemic_status", "stale_basis"):
            if s.get(k) != p[k]:
                problems.append(f"{rel}: {p['component']}: {k} is {s.get(k)!r}, the claims say {p[k]!r}")
    if any(p.get("epistemic_status") == "verified" for p in fm.get("placements") or []):
        problems.append(f"{rel}: a placement is marked verified; nothing on a map is verified")
    h = dict(fm.get("health") or {})
    want = dict(built["health"]); want["moves"] = h.get("moves", want["moves"])
    if {k: v for k, v in h.items() if k != "moves"} != {k: v for k, v in want.items() if k != "moves"}:
        problems.append(f"{rel}: health does not match what wardley.py computes")
    rec = ((f.state.get("projections") or {}).get(rel)) or {}
    want_sha = rec.get("sha256") if isinstance(rec, dict) else rec
    if want_sha and sha256(text) != want_sha:
        problems.append(f"{rel}: fork — the file was edited after generation; regenerate it")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("facility")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("plan"); p1.add_argument("map"); p1.add_argument("--json", action="store_true"); p1.add_argument("--as-of")
    p2 = sub.add_parser("assemble"); p2.add_argument("map"); p2.add_argument("draft"); p2.add_argument("--generated-at"); p2.add_argument("--as-of")
    p3 = sub.add_parser("svg"); p3.add_argument("file")
    p4 = sub.add_parser("owm"); p4.add_argument("file")
    p5 = sub.add_parser("check"); p5.add_argument("files", nargs="*"); p5.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    f = Facility(a.facility, getattr(a, "as_of", None))
    try:
        if a.cmd == "plan":
            out = plan(f, a.map)
            if a.json:
                print(json.dumps(out, indent=2, default=str))
            else:
                print(f"map {out['map']}: {len(out['components'])} components, {len(out['candidates'])} candidate claims" + (f"; problems: {out['problems']}" if out["problems"] else ""))
                for c in out["components"]:
                    print(f"  {c['depth']} · {c['id']} — {c.get('name')} → {', '.join(c.get('depends_on') or []) or '—'}")
            return 0 if not out["problems"] else 1
        if a.cmd == "assemble":
            sys.stdout.write(assemble(f, a.map, json.loads(Path(a.draft).read_text(encoding="utf-8")), a.generated_at))
            return 0
        if a.cmd in ("svg", "owm"):
            fm, _ = split_front(Path(a.file).read_text(encoding="utf-8"))
            sys.stdout.write(svg(fm) if a.cmd == "svg" else owm(fm))
            return 0
    except MapError as e:
        print(f"wardley: refused — {e}", file=sys.stderr)
        return 1
    files = [Path(x) for x in a.files] or sorted((f.root / "intel" / "maps").glob("*.md"))
    problems = [p for x in files for p in check(f, x.resolve())]
    if a.json:
        print(json.dumps({"checked": len(files), "problems": problems}, indent=2))
    else:
        print(f"{len(files)} map file(s) checked, {len(problems)} problem(s)")
        for p in problems:
            print(f"  {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
