#!/usr/bin/env python3
"""build-intel-battlecards — every battlecard as a visual card, with the evidence ledger beside it.

    python3 build-intel-battlecards.py <facility-dir> [--out FILE] [--as-of YYYY-MM-DD] [--json FILE]

Reads intel/battlecards/*.md (the projections intel-battlecard writes), the claims they cite, the entities and
the manifest's audiences. Writes ONE file (default <facility>/intel/reports/battlecards.html) and nothing else:
an index of the cards, then each card in the design first drawn for the Northline sample (2026-09-28) — the
cover with its audience and a health panel, positioning, when they win / when we win, differentiators with the
three-part test, discovery questions, they say / we say, objections, proof, avoid saying struck through,
the talk track, the unknowns — and a ledger of every claim the card cites. Every claim chip on a card is
coloured by the claim's freshness on the day the card was generated, and links to its ledger entry.

The card is parsed from its own markdown; nothing is re-derived or re-worded. A section this builder does not
recognise is drawn as plain prose, so a card is never silently shortened. --json gives the same cards as data
(each with its rendered HTML) for the Console's Battlecards tab (view_capability intel-battlecards).
Declared in surfaces.yaml (`reports:`); no scripts, no external resources.
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

ID = re.compile(r"INT-C-\d{3,}")
# "[INT-C-001, INT-C-002]", and "([INT-C-093] low)" — the parenthesis is eaten only when it wraps the citation
BRACKET = re.compile(r"\(\[((?:[^\[\]]*?INT-C-\d{3,}[^\[\]]*?))\](?:\s*(low|unknown|inferred|hypothesis)\b)?\)|\[((?:[^\[\]]*?INT-C-\d{3,}[^\[\]]*?))\](?:\s*(low|unknown|inferred|hypothesis)\b)?")


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


class Card:
    """One battlecard: frontmatter, sections, and the claims it cites, freshness taken on its generation day."""

    def __init__(self, f: Facility, path: Path):
        self.f = f
        self.path = path
        self.rel = "intel/battlecards/" + path.name
        self.fm, self.body = split_front(path.read_text(encoding="utf-8"))
        self.subject = self.fm.get("subject")
        self.audience = (self.fm.get("audience") or {}) if isinstance(self.fm.get("audience"), dict) else {"id": self.fm.get("audience")}
        self.generated = to_date(self.fm.get("generated_at")) or f.as_of
        self.slug = path.stem
        self.sections = []  # (heading, [lines])
        cur = None
        for line in self.body.splitlines():
            if line.startswith("## "):
                cur = (line[3:].strip(), [])
                self.sections.append(cur)
            elif cur is not None:
                cur[1].append(line)
        ids = list(dict.fromkeys(ID.findall(self.body)))
        self.claims = [i for i in ids if i in f.claims]
        self.missing = [i for i in ids if i not in f.claims]

    # ── a claim, as the card saw it ──────────────────────────────────────────
    def fresh(self, cid):
        c = self.f.claims.get(cid)
        if not c:
            return "unknown"
        if c.get("epistemic_status") == "unknown":
            return "unknown"
        return self.f.freshness(c, self.generated)

    def chip(self, cid):
        fr = self.fresh(cid)
        cls = " is-stale" if fr == "stale" else ""
        return f'<a class="cite{cls}" href="#{esc(self.slug)}--{cid}" data-claim="{cid}"><i class="dot d-{fr}"></i>{cid.replace("INT-", "")}</a>'

    # ── inline markdown with citation chips ──────────────────────────────────
    def inline(self, text: str) -> str:
        chips = []

        def take(m):
            ids = ID.findall(m.group(1) or m.group(3))
            word = m.group(2) or m.group(4)
            chips.append(" ".join(self.chip(i) for i in ids) + (f' <span class="q">{esc(word)}</span>' if word else ""))
            return f"\x00{len(chips) - 1}\x00"
        t = BRACKET.sub(take, text)
        t = esc(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\x00(\d+)\x00", lambda m: chips[int(m.group(1))], t)
        return t

    # ── section helpers ──────────────────────────────────────────────────────
    def get(self, *names):
        for h, lines in self.sections:
            if any(h.lower().startswith(n) for n in names):
                return lines
        return None

    @staticmethod
    def bullets(lines):
        out, cur = [], None
        for l in lines or []:
            m = re.match(r"^\s*[-*]\s+(.*)$", l)
            if m:
                cur = m.group(1).strip()
                out.append(cur)
            elif l.startswith("  ") and out:
                out[-1] += " " + l.strip()
        return out

    @staticmethod
    def table(lines):
        rows = [l for l in lines or [] if l.strip().startswith("|")]
        if len(rows) < 2:
            return None, []
        cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]  # noqa: E731
        return cells(rows[0]), [cells(r) for r in rows[2:]]

    @staticmethod
    def prose(lines):
        return " ".join(l.strip() for l in lines or [] if l.strip() and not l.strip().startswith("|") and not re.match(r"^\s*[-*]\s", l)).strip()

    # ── the three-part test, read from the card and its claims ───────────────
    def true_test(self, ids):
        cs = [self.f.claims[i] for i in ids if i in self.f.claims]
        if not cs:
            return ("na", "No claim resolves.")
        good = [c for c in cs if c.get("epistemic_status") in ("verified", "reported") and c.get("confidence") in ("medium", "high")]
        if len(good) == len(cs):
            return ("ok", f"{len(cs)} claim(s), {', '.join(sorted({c.get('epistemic_status') for c in cs}))}, medium confidence or better.")
        weak = [c for c in cs if c not in good]
        ours = [c for c in good if self.f.subject(c) == self.f.self_id]
        lead = f"{len(ours)} claim(s) about us hold; " if ours else ""
        return ("na", lead + f"{', '.join(c['id'] for c in weak)} {'is' if len(weak) == 1 else 'are'} {', '.join(sorted({c.get('epistemic_status') if c.get('epistemic_status') in ('inferred', 'unknown', 'hypothesis') else 'low' for c in weak}))} — so the card qualifies it.")

    def render(self) -> str:
        f, name = self.f, self.f.name(self.subject)
        me = f.name(f.self_id) if f.self_id else "us"
        aud = self.audience or {}
        decl = next((a for a in (f.comp.get("audiences") or []) if isinstance(a, dict) and a.get("id") == aud.get("id")), {}) if aud.get("id") else {}
        chips = [("audience", aud.get("id") or "general")] + [(k, (decl or aud).get(k)) for k in ("persona", "segment", "geography") if (decl or aud).get(k)]
        cw = self.fm.get("claim_window") or {}
        chips += [("generated", self.generated.isoformat())] + ([("claim window", f"{to_date(cw.get('from'))} → {to_date(cw.get('to'))}")] if cw else [])
        fr = {k: 0 for k in ("fresh", "aging", "stale", "unknown")}
        for i in self.claims:
            fr[self.fresh(i)] += 1
        hl = self.fm.get("health") or {}
        uns = hl.get("unsourced_lines", "—")
        stale_used = hl.get("stale_claims_used", 0)
        meter = "".join(f'<i class="d-{k}" style="flex:{v}"></i>' for k, v in fr.items() if v)
        out = [f'<article class="bc-card" id="{esc(self.slug)}">',
               '<header class="cover"><div>',
               f'<div class="eyebrow">Battlecard · {esc(self.subject)} · {esc(self.rel)}</div>',
               f'<h1>{esc(name)}<span class="vs">against {esc(me)}</span></h1>',
               '<p class="lede">Ninety seconds before a call: what to ask, what to expect, what not to say.</p>',
               '<div class="aud">' + "".join(f'<span><i>{esc(k)}</i> {esc(v)}</span>' for k, v in chips) + "</div></div>",
               '<div class="health" aria-label="Card health"><div class="eyebrow">Health</div>',
               f'<div class="row"><span>Claims cited</span><b>{len(self.claims)}</b></div>',
               f'<div class="meter" role="img" aria-label="{fr["fresh"]} fresh, {fr["aging"]} aging, {fr["stale"]} stale, {fr["unknown"]} unknown">{meter}</div>',
               '<div class="legend">' + "".join(f'<span><i class="dot d-{k}"></i>{v} {k}</span>' for k, v in fr.items() if v) + "</div>",
               f'<div class="row"><span>Unsourced lines</span><b class="{"ok" if uns == 0 else "warn"}">{esc(uns)}</b></div>',
               f'<div class="row"><span>Stale claims used</span><b class="{"ok" if not stale_used else "warn"}">{esc(stale_used)}</b></div>',
               "</div></header>", '<div class="grid"><div class="main">']
        done = set()

        def sec(title, inner, cls=""):
            out.append(f'<section class="sec {cls}"><h2>{esc(title)}</h2>{inner}</section>')

        pos = self.get("one-line positioning")
        if pos is not None:
            done.add("one-line positioning")
            sec("One-line positioning", f'<p class="big">{self.inline(self.prose(pos))}</p>')
        they, we = self.get("when they win"), self.get("when we win")
        if they is not None or we is not None:
            done.update({"when they win", "when we win"})
            li = lambda xs: "<ul class=\"plain\">" + "".join(f"<li>{self.inline(x)}</li>" for x in xs) + "</ul>"  # noqa: E731
            notes = [l for l in (they or []) if l.strip().startswith("*") and not l.strip().startswith("* ")]
            out.append('<section class="sec flush"><div class="pair">'
                       f'<div><span class="who them">When they win</span>{li([b for b in self.bullets(they) if not b.startswith("*These")])}</div>'
                       f'<div><span class="who us">When we win</span>{li(self.bullets(we))}</div></div>'
                       + "".join(f'<p class="note">{self.inline(n.strip().strip("-").strip())}</p>' for n in self.bullets(they) if n.startswith("*These")) + "</section>")
        diff = self.get("differentiators")
        if diff is not None:
            done.add("differentiators")
            head, rows = self.table(diff)
            items = []
            for r in rows:
                if len(r) < 2:
                    continue
                d, cl = r[0], r[1]
                prov = r[2] if len(r) > 2 else ""
                ids = ID.findall(cl)
                qualified = d.startswith("**Qualified:**")
                t_cls, t_txt = self.true_test(ids)
                rel_txt = (f"For the {esc(aud.get('id'))} audience." if aud.get("id") else "General card: no audience's criteria declared.") + (" Qualified on the card." if qualified else "")
                items.append(f'<div class="diff{" qualified" if qualified else ""}"><div class="claim">{self.inline(d)} <span class="ids">{self.inline(cl)}</span></div>'
                             f'<div class="tests"><div class="test {"" if t_cls == "ok" else "na"}"><b>True</b>{esc(t_txt)}</div>'
                             f'<div class="test {"na" if qualified or not aud.get("id") else ""}"><b>Relevant</b>{rel_txt}</div>'
                             f'<div class="test {"" if prov.strip() else "na"}"><b>Provable</b>{self.inline(prov) or "Not stated."}</div></div></div>')
            rest = [l for l in diff if l.strip() and not l.strip().startswith("|") and not l.startswith("Each passed")]
            cut = "".join(f'<p class="cut">{self.inline(l.strip())}</p>' for l in rest)
            sec("Differentiators", '<p class="sub">Each one passed the three-part test before it was allowed on the card.</p><div class="diffs">' + "".join(items) + "</div>" + cut)
        dq = self.get("discovery question")
        if dq is not None:
            done.add("discovery question")
            sec("Discovery questions", "".join(f'<p class="question">{self.inline(b)}</p>' for b in self.bullets(dq)))
        tr = self.get("competitive traps")
        if tr is not None:
            done.add("competitive traps")
            sec("Competitive traps", '<ul class="plain">' + "".join(f"<li>{self.inline(b)}</li>" for b in self.bullets(tr)) + "</ul>")
        lc = self.get("likely competitor claims")
        if lc is not None:
            done.add("likely competitor claims")
            pairs = []
            for b in self.bullets(lc):
                m = re.match(r"\*\*They say:\*\*\s*(.*?)\s*—\s*\*\*We say:\*\*\s*(.*)$", b)
                pairs.append(f'<div class="says"><div class="t"><span class="who them">They say</span><p>{self.inline(m.group(1))}</p></div><div class="u"><span class="who us">We say</span><p>{self.inline(m.group(2))}</p></div></div>'
                             if m else f"<p>{self.inline(b)}</p>")
            sec("Likely competitor claims", "".join(pairs))
        ob = self.get("objection")
        if ob is not None:
            done.add("objection")
            dls = []
            for b in self.bullets(ob):
                parts = re.split(r"\s+·\s+(?=\*\*)", b)
                kv = [re.match(r"\*\*(.+?):\*\*\s*(.*)$", p) for p in parts]
                if all(kv):
                    dls.append('<dl class="obj">' + "".join(f'<dt>{esc(k.group(1))}</dt><dd class="{"quote" if k.group(1).lower().endswith("says") else ""}">{self.inline(k.group(2))}</dd>' for k in kv) + "</dl>")
                else:
                    dls.append(f"<p>{self.inline(b)}</p>")
            sec("Objection handling", "".join(dls))
        pp = self.get("proof point")
        if pp is not None:
            done.add("proof point")
            sec("Proof points", '<ul class="plain">' + "".join(f"<li>{self.inline(b)}</li>" for b in self.bullets(pp)) + "</ul>")
        av = self.get("avoid saying")
        if av is not None:
            done.add("avoid saying")
            head, rows = self.table(av)
            lis = []
            for r in rows:
                if len(r) >= 2:
                    word = re.match(r"^\s*([a-z][a-z -]+?)(?::|;|\s—|$)", re.sub(r"\[.*", "", r[1]).strip(), re.I)
                    w = word.group(1) if word and len(word.group(1)) < 24 else ""
                    rest = r[1][len(w):].lstrip(":; —") if w else r[1]
                    lis.append(f'<li><span class="line">{self.inline(r[0])}</span><span class="why">{f"<b>{esc(w)}</b>" if w else ""}{self.inline(rest)}</span></li>')
            sec("Avoid saying", '<ul class="avoid">' + "".join(lis) + "</ul>")
        tt = self.get("talk track")
        if tt is not None:
            done.add("talk track")
            bl = self.bullets(tt)
            sec("Talk track", ('<ol class="track">' + "".join(f"<li>{self.inline(b)}</li>" for b in bl) + "</ol>") if bl else f'<p class="track-p">{self.inline(self.prose(tt))}</p>')
        dk = self.get("what this card does not know")
        if dk is not None:
            done.add("what this card does not know")
            sec("What this card does not know", '<div class="unknowns">' + "".join(f"<span>{self.inline(b)}</span>" for b in self.bullets(dk)) + "</div>")
        for h, lines in self.sections:  # anything else, as written — a card is never silently shortened
            if not any(h.lower().startswith(d) for d in done):
                sec(h, "".join(f"<p>{self.inline(l.strip())}</p>" for l in lines if l.strip()))
        out.append("</div>")
        # the ledger
        led = ['<aside class="ledger" aria-label="Evidence"><div><h2>Evidence behind the card</h2>'
               f'<p class="sub">Every chip on the card links here. Freshness is measured on the day the card was generated ({self.generated}) against the category half-life.</p></div>']
        for cid in self.claims:
            c = f.claims[cid]
            subj = f.subject(c)
            fr_ = self.fresh(cid)
            d = f.claim_date(c)
            age = (self.generated - d).days if d else None
            hlife = f.half.get(c.get("category"), 180)
            src = c.get("source") or {}
            us = subj == f.self_id
            led.append(f'<article class="claim-c{" stale" if fr_ == "stale" else ""}" id="{esc(self.slug)}--{cid}">'
                       f'<div class="top"><span class="id">{cid}</span><span class="tag {"us" if us else "them"}">{"us" if us else esc(f.name(subj))} · {esc(c.get("category"))}</span></div>'
                       f'<p class="st">{esc(c.get("statement"))}</p>'
                       + (f'<blockquote>"{esc(src.get("excerpt"))}"</blockquote>' if src.get("excerpt") else "")
                       + f'<div class="meta"><span class="fr {fr_}"><i class="dot d-{fr_}"></i>{fr_ if fr_ != "unknown" or c.get("epistemic_status") == "unknown" else "undated"}'
                       + (f" · {age}d / {hlife}d" if age is not None and c.get("epistemic_status") != "unknown" else "") + "</span>"
                       f'<span>{esc(c.get("epistemic_status"))} · {esc(c.get("confidence"))}</span><span>{esc(src.get("class"))}</span>'
                       + (f'<span>{esc(c.get("source_date"))}</span>' if c.get("source_date") else "") + "</div>"
                       + (f'<div class="src">{esc(src.get("ref"))}</div>' if src.get("ref") else "") + "</article>")
        for cid in self.missing:
            led.append(f'<article class="claim-c stale" id="{esc(self.slug)}--{cid}"><div class="top"><span class="id">{cid}</span></div><p class="st">Cited, but no such claim exists.</p></article>')
        led.append("</aside>")
        out += led
        out.append("</div></article>")
        return "\n".join(out)

    def summary(self):
        f = self.f
        fr = {k: 0 for k in ("fresh", "aging", "stale", "unknown")}
        for i in self.claims:
            fr[self.fresh(i)] += 1
        newer = [c for c in f.current_claims(self.subject) if c.get("material") and to_date(c.get("created")) and to_date(c.get("created")) > self.generated]
        return {"slug": self.slug, "path": self.rel, "subject": self.subject, "name": f.name(self.subject), "audience": (self.audience or {}).get("id"),
                "generated": self.generated.isoformat(), "claims": len(self.claims), "freshness": fr, "health": self.fm.get("health") or {},
                "behind": len(newer)}


CSS = """
.bc{--paper:#EEF1F4;--card:#FFFFFF;--ink:#16202B;--muted:#586576;--rule:#D5DCE4;--soft:#F5F7F9;--us:#2742A8;--us-bg:#E8ECFA;--them:#8C4A2F;--them-bg:#F6EBE5;
--fresh:#2B7A52;--aging:#946400;--stale:#B3261E;--unknown:#687384;--stale-bg:#FBEAE8;--hl:#FFF6CC;
--display:"Archivo","Avenir Next Condensed","Helvetica Neue",Arial,sans-serif;--body:"Public Sans",-apple-system,"Segoe UI",Roboto,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
color:var(--ink);font:15px/1.55 var(--body)}
@media (prefers-color-scheme:dark){.bc{--paper:#0F141B;--card:#171E27;--ink:#E4E9EF;--muted:#98A4B3;--rule:#2B3542;--soft:#1C2430;--us:#8FA6FF;--us-bg:#1D2748;--them:#E6A184;--them-bg:#3A241B;--fresh:#6CCB98;--aging:#E3B55A;--stale:#F28B82;--unknown:#9AA5B4;--stale-bg:#3A1D1B;--hl:#3A3417}}
.bc *{box-sizing:border-box}.bc h1,.bc h2,.bc h3{font-family:var(--display);margin:0;text-wrap:balance}
.bc .eyebrow{font:500 11px/1.3 var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
.bc-card{display:flex;flex-direction:column;gap:20px;margin:0 0 56px}
.bc header.cover{display:grid;grid-template-columns:1fr auto;gap:18px 28px;align-items:end;border-bottom:2px solid var(--ink);padding-bottom:18px}
.bc .cover h1{font-size:clamp(30px,5vw,50px);font-weight:800;line-height:.98;letter-spacing:-.01em;margin-top:10px}
.bc .cover h1 .vs{display:block;font-size:.38em;font-weight:600;color:var(--muted);letter-spacing:0;margin-top:10px}
.bc .cover .lede{margin:10px 0 0;color:var(--muted);font-style:italic}
.bc .aud{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}.bc .aud span{font:500 12px/1 var(--mono);border:1px solid var(--rule);background:var(--card);padding:6px 9px;border-radius:999px}.bc .aud span i{font-style:normal;color:var(--muted)}
.bc .health{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:14px 16px;min-width:260px;display:flex;flex-direction:column;gap:10px}
.bc .health .row{display:flex;justify-content:space-between;gap:16px;font-size:13px}.bc .health .row b{font:600 13px/1.3 var(--mono)}
.bc .ok{color:var(--fresh)}.bc .warn{color:var(--stale)}
.bc .meter{display:flex;height:8px;border-radius:4px;overflow:hidden;gap:2px;background:var(--soft)}.bc .meter i{display:block;height:100%}
.bc .legend{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:11.5px;color:var(--muted)}.bc .legend span{display:inline-flex;align-items:center;gap:5px}
.bc .dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none}
.bc .d-fresh{background:var(--fresh)}.bc .d-aging{background:var(--aging)}.bc .d-stale{background:var(--stale)}.bc .d-unknown{background:transparent;border:1.5px solid var(--unknown)}
.bc .grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:24px;align-items:start}
.bc .main{background:var(--card);border:1px solid var(--rule);border-radius:10px;overflow:hidden}
.bc .sec{padding:18px 22px;border-top:1px solid var(--rule);display:flex;flex-direction:column;gap:10px}.bc .sec:first-child{border-top:0}.bc .sec.flush{padding:0;gap:0}
.bc .sec h2{font-size:13px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}.bc .sec.flush h2{display:none}
.bc .sec p{margin:0;max-width:70ch}.bc .big{font-size:18px;line-height:1.45}.bc .sub{font-size:13px;color:var(--muted)}.bc .note{padding:0 22px 14px;font-size:12.5px;color:var(--muted)}
.bc ul.plain{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px}
.bc .pair{display:grid;grid-template-columns:1fr 1fr}.bc .pair>div{padding:18px 22px;display:flex;flex-direction:column;gap:8px}.bc .pair>div+div{border-left:1px solid var(--rule)}
.bc .who{font:600 11px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:4px 7px;border-radius:4px;align-self:flex-start}
.bc .who.us{background:var(--us-bg);color:var(--us)}.bc .who.them{background:var(--them-bg);color:var(--them)}
.bc .cite{display:inline-flex;align-items:center;gap:4px;font:500 11.5px/1 var(--mono);text-decoration:none;color:var(--ink);border:1px solid var(--rule);background:var(--soft);padding:3px 6px 3px 5px;border-radius:4px;vertical-align:1px;white-space:nowrap;cursor:pointer}
.bc .cite:hover{border-color:var(--ink)}.bc .cite .dot{width:7px;height:7px}.bc .cite.is-stale{background:var(--stale-bg);border-color:var(--stale);color:var(--stale)}.bc .q{font:500 11px/1 var(--mono);color:var(--muted)}
.bc .diffs{display:flex;flex-direction:column;gap:12px}.bc .diff{border:1px solid var(--rule);border-radius:8px;padding:12px 14px;display:flex;flex-direction:column;gap:8px}.bc .diff .claim{font-weight:600}.bc .diff .ids{font-weight:400}
.bc .tests{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.bc .test{font-size:12.5px;line-height:1.4;background:var(--soft);border-radius:6px;padding:8px 10px}
.bc .test b{display:block;font:600 10.5px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--fresh);margin-bottom:5px}.bc .test b::before{content:"✓ "}
.bc .test.na b{color:var(--aging)}.bc .test.na b::before{content:"? "}.bc .cut{font-size:13px;color:var(--muted)}
.bc .question{font-family:var(--display);font-size:19px;font-weight:600;line-height:1.35;border-left:3px solid var(--us);padding-left:14px;max-width:52ch}
.bc .says{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:8px}.bc .says>div{border-radius:8px;padding:12px 14px;display:flex;flex-direction:column;gap:6px}.bc .says .t{background:var(--them-bg)}.bc .says .u{background:var(--us-bg)}
.bc dl.obj{display:grid;grid-template-columns:max-content 1fr;gap:8px 16px;margin:0 0 12px;padding-bottom:12px;border-bottom:1px dashed var(--rule)}.bc dl.obj:last-child{border-bottom:0;margin-bottom:0;padding-bottom:0}
.bc dl.obj dt{font:600 11px/1.9 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}.bc dl.obj dd{margin:0}.bc dl.obj .quote{font-weight:600}
.bc .avoid{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}.bc .avoid li{border:1px solid var(--stale);background:var(--stale-bg);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:4px}
.bc .avoid .line{font-weight:600;text-decoration:line-through;text-decoration-color:var(--stale);text-decoration-thickness:2px}.bc .avoid .why{font-size:13px}.bc .avoid .why b{color:var(--stale);font:600 11px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;margin-right:6px}
.bc ol.track{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:4px}.bc .track-p{font-size:15.5px;line-height:1.6}
.bc .unknowns{display:flex;flex-wrap:wrap;gap:8px}.bc .unknowns span{border:1.5px dashed var(--unknown);color:var(--muted);border-radius:6px;padding:6px 10px;font-size:13.5px}
.bc aside.ledger{position:sticky;top:16px;display:flex;flex-direction:column;gap:10px;max-height:calc(100vh - 32px);overflow:auto;padding-right:2px}
.bc .ledger h2{font-size:18px;font-weight:700}.bc .ledger .sub{margin:0;font-size:12.5px;color:var(--muted)}
.bc .claim-c{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:11px 12px;display:flex;flex-direction:column;gap:6px;scroll-margin-top:20px;transition:background .3s}
.bc .claim-c:target,.bc .claim-c.hl{background:var(--hl);border-color:var(--ink)}.bc .claim-c.stale{border-color:var(--stale)}
.bc .claim-c .top{display:flex;justify-content:space-between;align-items:center;gap:8px}.bc .claim-c .id{font:600 12px/1 var(--mono)}
.bc .tag{font:500 10.5px/1.2 var(--mono);letter-spacing:.05em;text-transform:uppercase;padding:3px 6px;border-radius:3px}.bc .tag.us{background:var(--us-bg);color:var(--us)}.bc .tag.them{background:var(--them-bg);color:var(--them)}
.bc .claim-c .st{font-size:13px;line-height:1.45;margin:0}.bc .claim-c blockquote{margin:0;font:400 12px/1.45 var(--mono);color:var(--muted);border-left:2px solid var(--rule);padding-left:8px}
.bc .meta{display:flex;flex-wrap:wrap;gap:4px 10px;font:400 11.5px/1.4 var(--mono);color:var(--muted)}
.bc .fr{display:inline-flex;align-items:center;gap:5px;font-weight:500}.bc .fr.fresh{color:var(--fresh)}.bc .fr.aging{color:var(--aging)}.bc .fr.stale{color:var(--stale)}.bc .fr.unknown{color:var(--unknown)}
.bc .src{font:400 11.5px/1.4 var(--mono);color:var(--muted);word-break:break-all}.bc code{font:400 .92em var(--mono)}
@media (max-width:900px){.bc .grid{grid-template-columns:1fr}.bc aside.ledger{position:static;max-height:none;overflow:visible}}
@media (max-width:640px){.bc header.cover{grid-template-columns:1fr}.bc .health{min-width:0}.bc .pair,.bc .says{grid-template-columns:1fr}.bc .pair>div+div{border-left:0;border-top:1px solid var(--rule)}.bc .tests{grid-template-columns:1fr}.bc .sec,.bc .pair>div{padding:16px}.bc dl.obj{grid-template-columns:1fr;gap:2px}}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — battlecards</title>
<style>
body{{margin:0;background:var(--paper,#EEF1F4)}}
@media (prefers-color-scheme:dark){{body{{background:#0F141B}}}}
.wrap{{max-width:1180px;margin:0 auto;padding:28px 16px 56px}}
.index{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin:14px 0 36px}}
.index a{{display:flex;flex-direction:column;gap:6px;text-decoration:none;color:var(--ink);background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:12px 14px}}
.index a:hover{{border-color:var(--ink)}}.index b{{font-family:var(--display);font-size:16px}}.index span{{font:500 11.5px/1.4 var(--mono);color:var(--muted)}}
.top-h h1{{font-family:var(--display);font-size:clamp(28px,4vw,40px);margin:6px 0 0}}.top-h p{{color:var(--muted);margin:8px 0 0;max-width:70ch}}
{css}
</style></head><body><div class="wrap bc">
<div class="top-h"><div class="eyebrow">intel capability · battlecards · generated by build-intel-battlecards · {now}</div>
<h1>{title} — battlecards</h1>
<p>Every card intel-battlecard has generated, drawn from the card itself and the claims it cites. A card is regenerated, never edited: a disagreement belongs in the claim set.</p></div>
<div class="index">{index}</div>
{cards}
</div></body></html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("facility"); ap.add_argument("--out"); ap.add_argument("--as-of"); ap.add_argument("--json")
    a = ap.parse_args(argv)
    f = Facility(a.facility, a.as_of)
    fac = f.root
    cards = [Card(f, p) for p in sorted((fac / "intel" / "battlecards").glob("*.md"))]
    cards = [c for c in cards if c.subject]
    cards.sort(key=lambda c: (str((f.entities.get(c.subject) or {}).get("priority") or "P9"), f.name(c.subject), c.slug))
    rendered = [(c, c.render()) for c in cards]
    name = ((f.manifest.get("project") or {}).get("name")) or fac.parent.name
    now = f.as_of.isoformat() if a.as_of else dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    if a.json:
        data = {"generator": "capabilities/intel/views/build-intel-battlecards.py", "as_of": f.as_of.isoformat(), "project": name, "css": CSS,
                "self": ({"id": f.self_id, "name": f.name(f.self_id)} if f.self_id else None),
                "cards": [{**c.summary(), "html": h} for c, h in rendered]}
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(data, indent=2, default=str))
    index = "".join(f'<a href="#{esc(c.slug)}"><b>{esc(f.name(c.subject))}</b><span>{esc((c.audience or {}).get("id") or "general")} · generated {c.generated} · {len(c.claims)} claims'
                    f'{" · behind by " + str(c.summary()["behind"]) if c.summary()["behind"] else ""}</span></a>' for c, _ in rendered) \
        or '<p class="sub">No battlecard yet — run intel-battlecard on a competitor once its claims exist.</p>'
    page = PAGE.format(title=esc(name), now=esc(now), css=CSS, index=index, cards="\n".join(h for _, h in rendered))
    out = Path(a.out) if a.out else fac / "intel" / "reports" / "battlecards.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"intel-battlecards → {out}\n  as of {f.as_of} · {len(cards)} card(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
