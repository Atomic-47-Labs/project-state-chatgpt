---
name: intel-compare
description: "Build the comparison matrix — 'compare us with competitors', 'feature matrix', 'score the competitors', 'how do we stack up'. Every competitor and us on declared dimensions, each cell cited and scored; totals with coverage."
metadata:
  map:
    tier: capability
    stage: generate
    requires: [memory, python]
    inputs: [operator]
    reads: [intel, manifest]
    writes: [intel, log]
    produces: [intel-competitive]
    calls: [intel-harvester]
---

# intel-compare — every competitor and us, factor by factor

> **When to use — full trigger description.** The frontmatter carries a short, trigger-first
> description so all of the suite's skills fit Claude Code's skill-listing budget (see
> docs/SKILL-SPEC.md, *Description budget*). The complete version, kept here:
>
> The intel capability's comparison matrix (docs/INTEL-COMPARE-AND-MAP-SPEC.md §1). One row per subject —
> `self` first, then the competitors in scope — and one column per declared dimension. Each cell is a short
> phrase, the claims behind it, its evidence state (evidenced · inferred · unknown · no claim · contested, with a
> stale overlay) and, on a scored dimension, a score on that dimension's 1–5 rubric. Totals per audience weight
> the scored cells and always carry their coverage — the share of the weight that evidenced cells hold — and a
> subject is ranked only when coverage reaches the threshold. Usage: `intel-compare [--audience <id>]
> [--subjects INT-E-…] [--dimensions …]`. Trigger on 'compare us with X and Y', 'feature matrix', 'competitive
> matrix', 'score the competitors', 'how do we stack up', 'where are we ahead', or the digest's
> intel.matrix-behind. Writes intel/matrices/ through project-state; never edits a generated matrix.

A matrix is a projection of claims, like a battlecard. It is regenerated, never edited; a disagreement with
a cell goes into the claim set and the matrix is rebuilt. The judgment is yours — which claims answer a
dimension's question, the phrase, the score on the rubric. Everything derived from that judgment — each cell's
state, which scores are provisional, the totals, the coverage, the ranking, the health — is computed by
`scripts/compare.py`, so the numbers on the page can be recomputed by anyone and checked by the validator.

## Preconditions, every invocation

Via `project-state`: `capabilities.intel` enabled; `competitive.self_entity` resolves to an entity of type
`self` (refuse otherwise: "no self entity: we cannot be compared; run `/intel-onboarding competitive`"). With
`--audience`, the audience exists in `competitive.audiences`; its `weights` decide its totals, and a dimension
that lists audiences appears only in theirs. Dimensions come from `competitive.dimensions`, else the shipped
defaults in `templates/dimensions.yaml`.

## Method

1. **Plan.** `python3 <plugin>/capabilities/intel/scripts/compare.py <facility>/project-state plan --json
   [--audience <id>]` lists, per subject × dimension, the candidate claims (current claims on that subject in
   the dimension's categories) with status, confidence, freshness and any open conflict — and the cells with
   no candidate.
2. **Refresh only what is stale and material.** For cells whose only candidates are stale and material, call
   `intel-harvester competitor <id> --stale-only` scoped to those categories — never a full research pass. A
   cell with no candidate at all stays *no claim*; the matrix names the run that would fill it.
3. **Pick, per cell** — this is the judgment:
   - **Claims:** the candidates that answer the dimension's `question`. Cite nothing the question does not ask
     about. A claim from another category may be cited when it answers the question; its subject must be the
     cell's subject. When a claim is in an open conflict, cite **both** sides (the script refuses otherwise).
   - **Phrase:** 3–12 words condensing those claims, adding nothing they do not say, worded at the level of
     the weakest claim (an inferred claim never reads as fact).
   - **Score** (scored dimensions only): the rubric level the claims support, from the buyer's side; between
     two levels, the lower. A contested cell gets one score per side, `[a, b]`. **An unknown cell and a cell
     with no claim get no score** — never a zero, never a guess.
4. **Assemble.** Write the picks as JSON — `{"audience": null, "cells": [{"subject", "dimension", "claims",
   "value", "score"}]}` — and run `compare.py <facility> assemble <draft.json> [--slug …]`. It derives the
   states, provisional marks, the stale overlay, *us against each competitor*, the totals with coverage and
   ranking, and the health block, renders the projection, and **refuses** a draft that cites a missing,
   superseded or wrong-subject claim, one side of a conflict, an unsourced phrase, a score on an unknown or
   no-claim cell, or a score off the scale. Fix the pick; never hand-edit the output.
5. **Write and record.** Put the output at `intel/matrices/<slug>.md` (default slug `comparison-YYYY-MM`,
   `<audience>-comparison-YYYY-MM` for an audience); record `{sha256, generated_at, claims}` in
   `state/intel.json → projections[path]`; log `intel.matrix.generated` `{path, audience, health}`. Run
   `compare.py <facility> check <path>` — it must report no problem. Re-render the Competitive report
   (`python3 <plugin>/capabilities/intel/views/build-intel-competitive.py <facility>/project-state`).

## Reply

The grid's shape (subjects × dimensions), the health line (evidenced / inferred / unknown / no claim /
contested / stale), the ranked totals for each audience **with their coverage**, the subjects not ranked and
why, and the thinnest gaps with the run that would fill them.

## Human gate

The matrix is an internal file. Scores travel: before it is posted, mailed or put in a deck, it goes through
`project-notifier` / `project-external-comms` (Gmail always draft) and logs `intel.approval.logged`.

## Discipline

Claims before scores · a missing cell is never a zero · totals always with their coverage · the weakest claim
sets the register · contested shown, never resolved · projections do not read projections (claims only, never a
profile's prose) · never edit a generated matrix — regenerate.
