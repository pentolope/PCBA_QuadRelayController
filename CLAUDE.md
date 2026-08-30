# PCBA_QuadRelayController — Four-Channel Relay Controller

## Mission

Four-channel relay controller run by a small MCU on 5 V logic, switching external loads through screw terminals with the switched side kept apart from logic.

This repository seeds the design of a four-channel relay controller operated by a small MCU, with 5 V logic power and each relay switching an external load through screw terminals. The brief fixes the functional block list — input protection, transistor/MOSFET relay drivers, flyback suppression, status indication, and a programming interface — and imposes one layout-level constraint: the switched side must be physically separated from the logic side, with conservative clearances appropriate to a voltage rating the design agent selects and documents. Beyond those items nothing is pinned down. No relay, MCU, driver device, terminal block, protection part, programming standard, board outline, or stackup is named. The switched-side voltage rating is explicitly delegated — it is one "you select and document" — while the switched-side current rating and whether the load is AC or DC are never mentioned at all, and so are open by silence. Most of the architecture therefore belongs to the design agent; the brief supplies the block list and the separation constraint, not the implementation.

This repository is board **3 of 32** in the `PCBA_AutoDesignAndTest`
benchmark. The suite is catalogued in
[pentolope/PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench).

At difficulty 2 and detail 2 in the industrial-control category, this board tests whether an agent can execute a conventionally-shaped circuit while getting the physical discipline right rather than the component novelty. The listed stressors — high/low voltage partition, relay flyback, creepage/clearance, terminal placement — are all layout and rating problems, and the brief deliberately withholds the switched-side voltage rating so the agent must select one, choose clearances that are conservative and appropriate to it, and live with the consequences in the floorplan. The real test is whether the separation barrier and the clearance numbers rest on a stated basis or are merely asserted.

## Status: not designed

There is no schematic, no board, no netlist and no part selection in this
repository, and their absence is the current, correct state — not an omission to
be tidied away. What exists is the brief, the reading of the brief, and the
scaffolding a design run needs.

Nothing here should be read as a design decision already taken. See
[docs/status.md](docs/status.md).

## `BRIEF.md` is the requirement

[BRIEF.md](BRIEF.md) is supplied by the benchmark and is authoritative. It is
preserved byte for byte and **is not edited** — not to clarify it, not to record
a decision, not to fix a typo. A design run reads it and writes elsewhere.

## Do not fabricate requirements

This is the rule the benchmark exists to test, and the one most easily broken by
being helpful.

> Missing details are design freedom, not permission to fabricate unstated user
> requirements.

Where the brief is silent, **you** choose — and you record it as your choice, in
[board/requirements.md](board/requirements.md) under the open decision it
answers, with the reasoning that made it. What you must not do is write the
choice down as though the user had asked for it. A part number, a dimension, a
voltage or a layer count that appears in this repository as a *requirement* must
be traceable to a sentence in `BRIEF.md`; anything else is a *decision*, and the
two are never allowed to blur.

[board/requirements.json](board/requirements.json) holds that split in machine
-readable form: `fixed_requirements` each carry the verbatim brief text that
substantiates them, `open_decisions` are the choices still yours to make. Adding
to `fixed_requirements` without brief evidence is the failure mode, not a
shortcut.

## Authority and safety

1. Native KiCad `.kicad_sch`, `.kicad_pcb`, `.kicad_pro` and `.kicad_dru` files
   are the final design authority once they exist. A committed board is
   authoritative as committed.
2. A generator may produce the board, but a generated board is a **candidate**
   that must pass every gate before it replaces a committed one. A generator is
   not a second design authority.
3. Use KiCad Routing Tools only, to propose tracks and permitted new routing
   vias. It is a submodule of the toolkit, pinned to a commit on its
   `pcba-autonomy` branch and resolved through `pcbqa.krt`; no sibling checkout
   and no absolute path.
4. Never overwrite a source board while generating or importing a route. Route
   only into fresh candidate paths.
5. Automated tools must not move, remove, resize, redrill, re-layer, retype or
   reassign a pre-existing via. A needed change is made in the authoritative
   input and the candidate regenerated.
6. Do not run a cleanup, smoothing, repair, merge or optimisation pass that
   silently rewrites routed copper.
7. Do not weaken a check, add a waiver, suppress a finding, or change an expected
   result merely to make a test pass. A waiver is bound to exact objects and
   digests, and carries a reason.
8. Do not commit, push, create a pull request, change a remote, or update the
   toolkit submodule pointer without explicit user authorisation.
9. **Never submit an order.** JLCPCB Gerber and placement previews require human
   approval. A local release is a candidate, not an order.

## Repository boundary

Owned here:

- the brief and the reading of it — `BRIEF.md`, `board/requirements.*`
- the board itself, once designed: native KiCad files, project libraries, the
  generator chain, and checks genuinely specific to this board
- `board/` — manifest, toolchain paths, selected fabrication options
- board documentation and, once promoted, release outputs

Owned by the toolkit at `tooling/PCBA_AutoDesignAndTest`, and not to be restated
or relaxed here:

- gate implementations, rule types, measurement definitions
- JLCPCB-wide capability and process limits
- the clean-room release lifecycle, publication and coherence

Dependencies run one way. The toolkit knows nothing about this board, and
nothing board-specific may be pushed into it to make this board pass. If a rule
type genuinely cannot express what this board needs, that is a toolkit gap worth
reporting — not a reason to special-case a board name inside `pcbqa/`.

## What must not be committed

Routing search output, candidate pools, build trees, validator attempt
directories and openEMS field dumps are disposable by construction and are
ignored by [.gitignore](.gitignore). They are regenerated from what *is*
committed. A release package is committed only when a human promotes it, and
then as exact bytes — see [.gitattributes](.gitattributes).

Thirty-two repositories share one benchmark clone. Weight here is paid
thirty-two times.

## Toolkit consumption

The toolkit is used **only** from `tooling/PCBA_AutoDesignAndTest`, pinned to a
commit that exists on its remote. `PCB_TOOLKIT_PATH` exists to test against a
local toolkit checkout before a submodule bump is committed — it is a
development affordance, and nothing committed here may depend on it.

A fresh recursive clone must work with no manual setup beyond checking out
submodules.

## Publishing discipline

Before any push of design-cycle work, run `/claim-audit` on the drafted commit
message and report — every claim-bearing word binds to an artefact recomputed on
the spot, never to the process that produced it — and then
`/accountability-review`, which asks whether the work did what was asked, from a
context that does not share this session's account of what was asked.

For a board at this stage the audit is short and the discipline is not: the
honest claim about an undesigned board is that it is undesigned.

## Running

Ubuntu, and the system Python 3. KiCad is the distribution package, so `pcbnew`
imports from `/usr/lib/python3/dist-packages` and `kicad-cli` is on PATH.

```bash
git submodule update --init --recursive
```

```bash
python3 tooling/PCBA_AutoDesignAndTest/run.py preflight
```

Once a board and a manifest exist — `board/manifest.template.json` is the
starting point, and becomes `board/manifest.json` when it points at real files:

```bash
python3 tooling/PCBA_AutoDesignAndTest/run.py validate board/manifest.json
```

Every gate whose policy block is absent reports `NOT_APPLICABLE` **with a
reason** and still appears in the matrix. Absence is never a silent pass, so the
first run tells you exactly what this board has not yet opted into. See
[the toolkit's onboarding guide](tooling/PCBA_AutoDesignAndTest/examples/onboarding.md).
