---
name: intel-map
description: "Draw the Wardley map — 'wardley map', 'map the value chain', 'where does value sit', 'what is commoditising'. Components declared, placed on the evolution axis from cited claims, players drawn, every move listed."
metadata:
  map:
    tier: capability
    stage: generate
    requires: [memory, python]
    inputs: [operator]
    reads: [intel, manifest]
    writes: [intel, manifest, log]
    produces: [intel-competitive]
    calls: [intel-harvester]
---

# intel-map — where value sits, and who plays where

> **When to use — full trigger description.** The frontmatter carries a short, trigger-first
> description so all of the suite's skills fit Claude Code's skill-listing budget (see
> docs/SKILL-SPEC.md, *Description budget*). The complete version, kept here:
>
> The intel capability's Wardley map (docs/INTEL-COMPARE-AND-MAP-SPEC.md §2). What is ON a map is declared in the
> manifest (`capabilities.intel.competitive.maps`: a user, a need, components and their dependencies); where each
> component SITS on the evolution axis — genesis, custom-built, product (+rental), commodity (+utility) — and who
> plays where are generated from cited claims every run. Every placement is an inference from Wardley's four
> characteristics (ubiquity, certainty, market, practice): inferred where two or more are evidenced, a hypothesis
> where one or none is, never verified. Every move since the last map is listed, logged and flagged. Verbs:
> `intel-map draft "<need>" [--user …]` (propose the declared block) · `intel-map [<map-id>]` (generate). Trigger on
> 'wardley map', 'map our value chain', 'where does value sit', 'what is commoditising', 'where should we build',
> or the digest's intel.map-moved / intel.map-behind. Writes intel/maps/ through project-state; never edits a
> generated map.

A map is judgment. This skill makes the judgment visible: what is on the map is a person's declaration; where it
sits is an inference with its evidence attached; and nothing moves without the move being written down.
`scripts/wardley.py` holds the deterministic half — validation, depth in the value chain, the epistemic status, the
stale-basis overlay, the moves since the last generation, the drawing and the OnlineWardleyMaps export — so the page
shows what the claims support and the validator can recompute it.

## `draft "<need>"` — declare what is on the map

1. Read the focus, the self entity's claims and the competitors' product, feature and integration claims.
2. Propose the declared block: an `id`, the `user` and the `need` (the anchor), the `components` — each with an
   `id`, a `name` and `depends_on` (what it needs below it in the chain) — and the claim `categories` placement
   evidence is looked for in (default: product, feature, integration, pricing, market, compliance). Keep it to the
   components that decide strategy (5–12), not an inventory.
3. **Show it and confirm.** The operator edits names, adds or removes components, re-routes dependencies. Only
   then write it into `capabilities.intel.competitive.maps` through `project-state` (a manifest write; take the
   lock as the memory layer does). This declared block is the only part of a map a person writes.
4. Run `python3 <plugin>/capabilities/intel/scripts/wardley.py <facility>/project-state plan <map-id>` — it must
   report no problems (ids unique, dependencies resolve, no cycle).

## `[<map-id>]` — generate (every map when no id is given)

1. **Plan.** `wardley.py <facility> plan <map-id> --json`: the components with their depth, and the candidate
   claims (current claims in the map's categories, every subject).
2. **Refresh only what is stale and material** in the map's categories — `intel-harvester competitor <id>
   --stale-only` — never a full research pass.
3. **Place each component** — the judgment:
   - For each of the four characteristics, cite the claims that speak to it: **ubiquity** (how many vendors offer
     it — cite the claims that show who does), **certainty** (how well understood — published standards, teaching,
     documented practice), **market** (how it is sold — prices, packaging, pass-through), **practice** (how it is
     done — bespoke craft, feature competition, interchangeable). A characteristic with no claim stays empty.
   - Choose the **stage** the cited characteristics support and a **position** inside that stage's band
     (genesis 0–0.17, custom 0.17–0.40, product 0.40–0.70, commodity 0.70–1.0). Between two stages, the left one.
   - Write one **rationale** sentence. A component with no basis claim at all is a hypothesis and must say why it
     is placed where it is.
   - **Moving**: only with claims that show the movement (`{toward, basis}`), and only to the right.
4. **Players**: for each entity that provides components, the components and the **product, feature or
   integration** claims that show it. No such claim, no player.
5. **Notes** — four sections, every line citing `[MAP:<component>]` or `[INT-C-…]`: where to build (genesis and
   custom components we provide), where to buy or use (commodity we should not build), what is moving and what it
   does to us, what this map cannot see. Comparative, never pejorative. The script labels every line inferred.
6. **Assemble.** Write the picks as JSON (`{"placements": […], "players": […], "notes": {"build": […], "buy": […],
   "moving": […], "cannot_see": […]}}`) and run `wardley.py <facility> assemble <map-id> <draft.json>`. It derives the
   epistemic status, the stale basis, the moves against the last generation and the health, renders the projection,
   and **refuses** an undeclared or unplaced component, a position outside its band, a missing or superseded claim,
   a player without a product/feature/integration claim, a basis-less placement without a reason, and a notes line
   that cites nothing. Fix the pick; never hand-edit the output.
7. **Write and record.** Put it at `intel/maps/<map-id>.md`; record `{sha256, generated_at, claims, placements:
   {component: {stage, position}}}` in `state/intel.json → projections[path]` (the placements are what the next run
   diffs against); log `intel.map.generated` `{path, health}` and one `intel.map.moved` `{map, component, from, to,
   basis}` per move. Run `wardley.py <facility> check` — no problem. Re-render the map report
   (`python3 <plugin>/capabilities/intel/views/build-intel-map.py <facility>/project-state`).

## Reply

The anchor, the placements by stage (with which are hypotheses), what is moving, **what moved since the last map**
and why, who plays where, and the notes' build / buy lines.

## Human gate

The map is an internal file. Before it is shown outside the Project it goes through `project-notifier` /
`project-external-comms` and logs `intel.approval.logged`.

## Discipline

Declared, then generated · a placement is an inference with its claims, never verified · moves are listed, never
silent · players from product, feature or integration claims only · projections do not read projections (claims
only; the last placements come from state, not from the old map) · never edit a generated map — regenerate.
