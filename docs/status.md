# Status — Four-Channel Relay Controller

**Not designed.** Benchmark board 3 of 32, at
scaffolding stage.

## What exists

| | |
|---|---|
| Brief | supplied, preserved byte for byte, authoritative |
| Fixed requirements extracted | 13, each bound to verbatim brief text |
| Open decisions recorded | 20, none answered |
| Architecture worksheet | questions only, no answers |
| Source ledger | classes of evidence, no documents chosen |
| Toolkit | pinned submodule at `tooling/PCBA_AutoDesignAndTest` |

## What does not exist, deliberately

- No schematic, netlist, board, footprint or symbol library.
- No part selection. Not an MCU, not a connector, not a passive value.
- No board outline, stackup, layer count or mechanical envelope beyond what the
  brief states.
- No manifest policy blocks: `board/manifest.template.json` is the toolkit's
  documented minimum and points at files that are not there yet. It becomes
  `board/manifest.json` when they are.
- No candidates, no routing output, no release, no openEMS run.

None of that is missing. A benchmark board is supposed to start from its brief,
and a repository that pre-answered these questions would be measuring the person
who scaffolded it instead of the agent that designs it.

## The next step

Read [BRIEF.md](../BRIEF.md), then
[board/requirements.md](../board/requirements.md), then answer
[architecture.md](architecture.md) — recording each answer against the open
decision it settles. The board comes after that, not before.

## An ACCEPTED verdict on this board would mean nothing

`run.py validate board/manifest.template.json` exits 0 and prints **ACCEPTED**.
It is not a pass. Every gate reports `NOT_APPLICABLE` because no policy block
opts into it, and no gate reads `sources.pcb`, so the fact that this board has
no board file is never noticed.

That is the toolkit working as designed — a gate whose policy is absent reports
`NOT_APPLICABLE` *with a reason* and still appears in the matrix, which is why
the matrix is the evidence and the verdict line is not. The trap is a reader,
human or agent, who runs the validator on an undesigned board, sees ACCEPTED,
and reports it. **An empty matrix is not a passing one.** Nothing in this
repository may cite that verdict as a result.

## Honest-claim note

The claim this repository makes today is *"the brief has been read and split"*.
It does not claim the board is feasible, manufacturable, routable, or that the
extracted requirements are complete — only that each one quoted is in the brief,
and that the digest recorded in `requirements.json` says which bytes were read.
