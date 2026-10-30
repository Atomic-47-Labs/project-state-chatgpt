#!/usr/bin/env python3
"""build-intel-map — every Wardley map, drawn, with the evidence behind each placement.

    python3 build-intel-map.py <facility-dir> [--out FILE] [--as-of YYYY-MM-DD] [--json FILE]

Reads intel/maps/*.md (the projections intel-map writes) and the claims they cite. Writes ONE file (default
<facility>/intel/reports/map.html) and nothing else: per map the anchor (user and need), the drawing — the
evolution axis in its four bands, the value chain by depth, dependency lines, movement arrows, this run's moves
as a ghost at the old position, hypothesis placements outlined, a stale basis hatched — a player filter (pure
CSS, no scripts), the placements with the claims behind each of Wardley's four characteristics, the notes, and
the OnlineWardleyMaps text for anyone who wants the map in that tool. The drawing comes from
scripts/wardley.py, so the report, the Console and the skill draw the same map.
--json gives the same maps as data (each with its rendered HTML) for the Console's Map tab
(view_capability intel-map). Declared in surfaces.yaml (`reports:`); no external resources.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from intel_lib import Facility, split_front, to_date  # noqa: E402
import wardley  # noqa: E402


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def ident(s) -> str:
    """A value used inside CSS selectors, ids and class names: letters, digits, _ and - only. Escaping is not enough
    there (a slug or player id with "</style>" in it once broke out of the map's <style> block), so anything else becomes -."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", "" if s is None else str(s))


def chip(f: Facility, cid, on):
    c = f.claims.get(cid)
    fr = "unknown" if not c or c.get("epistemic_status") == "unknown" else f.freshness(c, on)
    tip = esc(f"{cid} · {f.name(f.subject(c)) if c else '?'} · {(c or {}).get('epistemic_status')} · {fr}: {(c or {}).get('statement', '')[:160]}")
    return f'<span class="wcite{" is-stale" if fr == "stale" else ""}" title="{tip}"><i class="dot d-{fr}"></i>{cid.replace("INT-", "")}</span>'


def inline(f, text, on, names):
    t = esc(text)
    t = re.sub(r"\[((?:MAP:[a-z0-9-]+|INT-C-\d{3,})(?:\s*,\s*(?:MAP:[a-z0-9-]+|INT-C-\d{3,}))*)\]",
               lambda m: " ".join(chip(f, x.strip(), on) if x.strip().startswith("INT-C") else f'<span class="wcomp">{esc(names.get(x.strip()[4:], x.strip()[4:]))}</span>'
                                  for x in m.group(1).split(",")), t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\*([^*\n]+)\*", r"<i>\1</i>", t)
    return t.replace("&lt;!-- non-material --&gt;", "")


def render_map(f: Facility, path: Path):
    fm, body = split_front(path.read_text(encoding="utf-8"))
    slug = fm.get("slug") or path.stem
    on = to_date(fm.get("generated_at")) or f.as_of
    names = {c["id"]: c.get("name") or c["id"] for c in fm.get("components") or []}
    places = {p["component"]: p for p in fm.get("placements") or []}
    players = fm.get("players") or []
    h = fm.get("health") or {}
    slug = ident(slug)
    pid = lambda e: f"{slug}-p-{ident(e)}"  # noqa: E731
    radios = (f'<input type="radio" name="{esc(slug)}-who" id="{esc(slug)}-p-all" checked><label for="{esc(slug)}-p-all">everyone</label>'
              + "".join(f'<input type="radio" name="{esc(slug)}-who" id="{esc(pid(p["entity"]))}"><label for="{esc(pid(p["entity"]))}">{"us · " if p.get("self") else ""}{esc(p["name"])}</label>' for p in players))
    css = "".join(f'.wmap#{slug}:has(#{pid(p["entity"])}:checked) .wm-c:not([data-players~="{ident(p["entity"])}"]){{opacity:.22}}'
                  f'.wmap#{slug}:has(#{pid(p["entity"])}:checked) .wm-c[data-players~="{ident(p["entity"])}"] .wm-dot{{stroke-width:3.5}}' for p in players)
    rows = []
    for c in fm.get("components") or []:
        p = places.get(c["id"])
        if not p:
            continue
        basis = "".join(f'<div class="wb"><b>{esc(k)}</b>{" ".join(chip(f, i, on) for i in ids) or "<span class=none>no claim</span>"}</div>' for k, ids in (p.get("basis") or {}).items())
        mv = p.get("moving")
        who = ", ".join(("us" if pl.get("self") else pl["name"]) for pl in players if c["id"] in (pl.get("components") or []))
        rows.append(f'<tr><td class="wn"><b>{esc(names[c["id"]])}</b><span>depth {esc(c.get("depth"))}</span></td>'
                    f'<td><span class="wst wst-{ident(p["stage"])}">{esc(wardley.STAGE_LABEL.get(p["stage"], p["stage"]))}</span><span class="wpos">{esc(p["position"])}</span></td>'
                    f'<td><span class="wes wes-{ident(p["epistemic_status"])}">{esc(p["epistemic_status"])}</span>{"<span class=wes-stale>stale basis</span>" if p.get("stale_basis") else ""}</td>'
                    f'<td class="wbasis">{basis}{("<p class=wr>" + esc(p["rationale"]) + "</p>") if p.get("rationale") else ""}</td>'
                    f'<td>{("→ " + esc(mv["toward"]) + " " + " ".join(chip(f, i, on) for i in mv.get("basis") or [])) if mv else "—"}</td><td class="wwho">{esc(who) or "—"}</td></tr>')
    notes = []
    sec = None
    for line in body.splitlines():
        if line.startswith("## "):
            sec = line[3:].strip()
            notes.append(f"<h3>{esc(sec)}</h3>")
        elif line.startswith("- ") and sec:
            notes.append(f"<li>{inline(f, line[2:], on, names)}</li>")
    notes_html = re.sub(r"(<li>.*?</li>)+", lambda m: "<ul>" + m.group(0) + "</ul>", "".join(notes))
    fragment = (f'<section class="wmap" id="{esc(slug)}"><style>{css}</style>'
                f'<header class="wh"><div><div class="eyebrow">Wardley map · {esc(slug)} · intel/maps/{esc(path.name)}</div>'
                f'<h2>{esc(fm.get("need"))}</h2><p class="wuser">for <b>{esc(fm.get("user"))}</b> · generated {esc(on)}</p></div>'
                f'<div class="whealth"><span><b>{esc(h.get("placed", 0))}</b> placed</span><span><b>{esc(h.get("inferred", 0))}</b> inferred</span><span><b>{esc(h.get("hypothesis", 0))}</b> hypothesis</span>'
                f'<span><b>{esc(h.get("moving", 0))}</b> moving</span><span><b>{esc(h.get("moves", 0))}</b> moved since last</span><span><b>{esc(h.get("stale_basis", 0))}</b> stale basis</span></div></header>'
                f'<div class="wfilter"><span class="eyebrow">who plays where</span>{radios}</div>'
                f'<div class="wdraw">{wardley.svg(fm)}</div>'
                '<div class="wlegend"><span><i class="lg-inf"></i>inferred · two or more characteristics evidenced</span><span><i class="lg-hyp"></i>hypothesis · one or none</span>'
                '<span><i class="lg-mov"></i>moving toward</span><span><i class="lg-ghost"></i>moved since the last map</span><span><i class="lg-stale"></i>stale basis</span></div>'
                '<div class="wtbl"><table><thead><tr><th>Component</th><th>Stage</th><th>Status</th><th>Basis, by characteristic</th><th>Moving</th><th>Who plays</th></tr></thead><tbody>'
                + "".join(rows) + f'</tbody></table></div><div class="wnotes">{notes_html}</div>'
                f'<details class="wowm"><summary>OnlineWardleyMaps text — paste into onlinewardleymaps.com</summary><pre>{esc(wardley.owm(fm))}</pre></details></section>')
    return {"slug": slug, "path": f"intel/maps/{path.name}", "user": fm.get("user"), "need": fm.get("need"), "generated": on.isoformat(), "health": h,
            "players": [{"entity": p["entity"], "name": p["name"], "self": p.get("self")} for p in players], "owm": wardley.owm(fm), "html": fragment}


CSS = """
.wm-root{--paper:#F4F2EC;--card:#FFFFFF;--ink:#1D232B;--muted:#626B76;--rule:#DAD6CC;--soft:#F7F5F0;--accent:#2F5D8C;--hyp:#9A6B1E;--move:#7A4FC0;--fresh:#2B7A52;--aging:#946400;--stale:#B3261E;--unknown:#687384;--band0:#FBFAF6;--band1:#F3F0E8;
--display:"Archivo","Avenir Next Condensed","Helvetica Neue",Arial,sans-serif;--body:"Public Sans",-apple-system,"Segoe UI",Roboto,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;color:var(--ink);font:14.5px/1.5 var(--body)}
@media (prefers-color-scheme:dark){.wm-root{--paper:#11161C;--card:#181F28;--ink:#E4E8EE;--muted:#9AA3AF;--rule:#2C3542;--soft:#1D2530;--accent:#8DB2E0;--hyp:#E0B465;--move:#B79CF0;--fresh:#6CCB98;--aging:#E3B55A;--stale:#F28B82;--unknown:#9AA5B4;--band0:#171D25;--band1:#1B222C}}
.wm-root .eyebrow{font:500 11px/1.3 var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
.wmap{background:var(--card);border:1px solid var(--rule);border-radius:10px;padding:18px 20px;margin:0 0 32px;display:flex;flex-direction:column;gap:14px}
.wh{display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;align-items:flex-end;border-bottom:2px solid var(--ink);padding-bottom:12px}
.wh h2{font-family:var(--display);font-size:clamp(22px,3vw,30px);margin:6px 0 0;line-height:1.15;max-width:40ch}.wuser{margin:6px 0 0;color:var(--muted)}
.whealth{display:flex;flex-wrap:wrap;gap:6px}.whealth span{font:500 12px/1 var(--mono);border:1px solid var(--rule);border-radius:999px;padding:6px 9px;background:var(--soft)}.whealth b{font-weight:700}
.wfilter{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.wfilter input{position:absolute;opacity:0;pointer-events:none}
.wfilter label{font:500 12px/1 var(--mono);border:1px solid var(--rule);border-radius:999px;padding:6px 10px;cursor:pointer;background:var(--card)}.wfilter input:checked+label{background:var(--ink);color:var(--card);border-color:var(--ink)}
.wfilter input:focus-visible+label{outline:2px solid var(--accent);outline-offset:2px}
.wdraw{overflow-x:auto}.wm{width:100%;min-width:720px;height:auto;display:block;font-family:var(--body)}
.wm .wm-band0{fill:var(--band0)}.wm .wm-band1{fill:var(--band1)}.wm .wm-stage{fill:var(--muted);font:600 11px var(--mono);letter-spacing:.05em}
.wm .wm-axis{stroke:var(--muted);stroke-width:1.2}.wm .wm-ax{fill:var(--muted);font:500 10.5px var(--mono)}.wm .wm-arrowhead{fill:var(--muted)}
.wm .wm-anchor circle{fill:var(--ink)}.wm .wm-anchor-t{fill:var(--ink);font:700 13px var(--display)}.wm .wm-need{fill:var(--muted);font:italic 12px var(--body)}
.wm .wm-link{stroke:var(--rule);stroke-width:1.4}.wm .wm-c{transition:opacity .2s}
.wm .wm-dot{fill:var(--accent);stroke:var(--card);stroke-width:2}.wm .wm-hypothesis .wm-dot{fill:var(--card);stroke:var(--hyp);stroke-width:2.4;stroke-dasharray:3 2}
.wm .wm-label{fill:var(--ink);font:600 12.5px var(--body)}.wm .wm-hatch{stroke:var(--stale);stroke-width:2}
.wm .wm-moving{stroke:var(--move);stroke-width:2;stroke-dasharray:5 3}.wm .wm-moved{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:2 3}.wm .wm-ghost{fill:none;stroke:var(--muted);stroke-dasharray:2 2;opacity:.7}
.wlegend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--muted)}.wlegend i{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:5px;vertical-align:-2px}
.wlegend .lg-inf{background:var(--accent)}.wlegend .lg-hyp{border:2px dashed var(--hyp)}.wlegend .lg-mov{border-radius:0;height:3px;background:var(--move);vertical-align:3px}.wlegend .lg-ghost{border:1.5px dashed var(--muted)}.wlegend .lg-stale{background:repeating-linear-gradient(45deg,var(--stale) 0 2px,transparent 2px 5px)}
.wtbl{overflow-x:auto}.wtbl table{border-collapse:collapse;width:100%;font-size:13px}.wtbl th,.wtbl td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--rule)}
.wtbl th{font:600 10.5px/1.2 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}.wn b{display:block}.wn span,.wpos{font:500 11px var(--mono);color:var(--muted);margin-left:6px}.wn span{margin:0}
.wst{font:600 11px var(--mono);padding:3px 7px;border-radius:4px;background:var(--soft);border:1px solid var(--rule)}.wes{font:600 11px var(--mono);padding:3px 7px;border-radius:4px}.wes-inferred{background:color-mix(in srgb,var(--accent) 14%,var(--card));color:var(--accent)}
.wes-hypothesis{background:color-mix(in srgb,var(--hyp) 16%,var(--card));color:var(--hyp)}.wes-stale{display:block;margin-top:4px;font:600 10.5px var(--mono);color:var(--stale)}
.wb{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:2px 0}.wb b{font:600 10.5px var(--mono);text-transform:uppercase;letter-spacing:.05em;color:var(--muted);min-width:74px}.wb .none{font:400 11.5px var(--mono);color:var(--muted);font-style:italic}.wr{margin:4px 0 0;color:var(--muted);font-size:12.5px}
.wcite{display:inline-flex;align-items:center;gap:4px;font:500 11px/1 var(--mono);border:1px solid var(--rule);background:var(--soft);padding:3px 5px;border-radius:4px;white-space:nowrap}.wcite.is-stale{border-color:var(--stale);color:var(--stale)}
.wcomp{font:600 12px var(--body);border-bottom:2px solid var(--accent)}
.wm-root .dot{width:7px;height:7px;border-radius:50%;display:inline-block}.wm-root .d-fresh{background:var(--fresh)}.wm-root .d-aging{background:var(--aging)}.wm-root .d-stale{background:var(--stale)}.wm-root .d-unknown{border:1.5px solid var(--unknown)}
.wnotes h3{font-family:var(--display);font-size:16px;margin:14px 0 6px}.wnotes ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:5px}
.wowm summary{cursor:pointer;color:var(--muted);font:600 12px var(--mono)}.wowm pre{background:var(--soft);border:1px solid var(--rule);padding:10px;font:400 12px/1.5 var(--mono);white-space:pre-wrap}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Wardley maps</title><style>body{{margin:0;background:#F4F2EC}}@media (prefers-color-scheme:dark){{body{{background:#11161C}}}}.wrap{{max-width:1180px;margin:0 auto;padding:28px 16px 56px}}
.top-h h1{{font-family:var(--display);font-size:clamp(28px,4vw,40px);margin:6px 0 0}}.top-h p{{color:var(--muted);max-width:72ch}}{css}</style></head>
<body><div class="wrap wm-root"><div class="top-h"><div class="eyebrow">intel capability · Wardley maps · generated by build-intel-map · {now}</div><h1>{title} — where value sits</h1>
<p>What is on each map is declared in the manifest; where each component sits, and who plays where, is generated by intel-map from cited claims. Every placement is an inference — nothing here is verified — and every move since the last map is listed.</p></div>
{maps}</div></body></html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("facility"); ap.add_argument("--out"); ap.add_argument("--as-of"); ap.add_argument("--json")
    a = ap.parse_args(argv)
    f = Facility(a.facility, a.as_of)
    maps = [render_map(f, p) for p in sorted((f.root / "intel" / "maps").glob("*.md"))]
    declared = [m.get("id") for m in f.comp.get("maps") or [] if isinstance(m, dict)]
    name = ((f.manifest.get("project") or {}).get("name")) or f.root.parent.name
    now = f.as_of.isoformat() if a.as_of else dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps({"generator": "capabilities/intel/views/build-intel-map.py", "as_of": f.as_of.isoformat(), "project": name, "css": CSS,
                                            "declared": declared, "maps": maps}, indent=2, default=str))
    body = "\n".join(m["html"] for m in maps) or ('<p class="wuser">No map yet. ' + (f'Declared: {esc(", ".join(declared))} — run <b>intel-map</b> to place it.' if declared else 'Declare one with <b>intel-map draft "&lt;need&gt;"</b>.') + "</p>")
    out = Path(a.out) if a.out else f.root / "intel" / "reports" / "map.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PAGE.format(title=esc(name), now=esc(now), css=CSS, maps=body), encoding="utf-8")
    print(f"intel-map → {out}\n  as of {f.as_of} · {len(maps)} map(s) · declared {len(declared)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
