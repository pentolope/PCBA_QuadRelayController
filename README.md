# Four-Channel Relay Controller

Four-channel relay controller run by a small MCU on 5 V logic, switching external loads through screw terminals with the switched side kept apart from logic.

This repository seeds the design of a four-channel relay controller operated by a small MCU, with 5 V logic power and each relay switching an external load through screw terminals. The brief fixes the functional block list — input protection, transistor/MOSFET relay drivers, flyback suppression, status indication, and a programming interface — and imposes one layout-level constraint: the switched side must be physically separated from the logic side, with conservative clearances appropriate to a voltage rating the design agent selects and documents. Beyond those items nothing is pinned down. No relay, MCU, driver device, terminal block, protection part, programming standard, board outline, or stackup is named. The switched-side voltage rating is explicitly delegated — it is one "you select and document" — while the switched-side current rating and whether the load is AC or DC are never mentioned at all, and so are open by silence. Most of the architecture therefore belongs to the design agent; the brief supplies the block list and the separation constraint, not the implementation.

> **This board has not been designed.** There is no schematic, no layout and no
> part selection here — only the brief, a reading of the brief, and the
> scaffolding a design run needs. That is the intended state of this repository,
> not a gap in it.

## What the brief fixes, and what it leaves open

The brief pins down 13 requirements and deliberately leaves
20 decisions to whoever designs the board. The `Source` column says
which is which: `brief` is quoted from [BRIEF.md](BRIEF.md), `metadata` comes
from the benchmark catalogue, and `open` means the brief does not fix it.

| Aspect | Value | Source |
|---|---|---|
| Channel count | Four relay channels | brief |
| Controller | A small MCU; no family, part, package or core named | brief |
| Logic supply | 5 V | brief |
| Load connection | Each relay switches an external load through screw terminals | brief |
| Relay driver stage | Transistor/MOSFET relay drivers required; device and topology unspecified | brief |
| Flyback suppression | Required; suppression method not specified | brief |
| Input protection | Required; protected nodes and scheme not specified | brief |
| Status indication and programming interface | Both required; indication form, programming standard and the physical form of the interface all unspecified | brief |
| High/low voltage partition | Switched side physically separated from logic side | brief |
| Switched-side voltage rating, current rating and clearance values | Not fixed by the brief; the design agent selects and documents the voltage rating and chooses conservative clearances appropriate to it. The current rating and whether the load is AC or DC are not mentioned at all and are equally the agent's to decide. | open |
| Relay selection (coil voltage, contact form and rating, mounting style) | Design agent's choice; the brief names no relay | open |
| Board outline, size, mounting and terminal pitch | Design agent's choice; the brief states no mechanical envelope | open |
| Likely layer count | 2 | metadata |
| Category / difficulty / brief detail | industrial-control; difficulty 2; detail 2 | metadata |

The full split, with the verbatim brief text substantiating every fixed
requirement, is in [board/requirements.md](board/requirements.md) and
machine-readably in [board/requirements.json](board/requirements.json).

**Missing details are design freedom, not permission to fabricate unstated user
requirements.** A choice the brief left open is recorded as a decision, with its
reasoning — never promoted into a requirement.

## Benchmark position

| | |
|---|---|
| Benchmark id | 3 of 32 |
| Category | industrial-control |
| Difficulty | 2 / 5 |
| Brief detail | 2 / 5 |
| Likely layer count | 2 |
| Primary stressors | high/low voltage partition, relay flyback, creepage/clearance, terminal placement |

At difficulty 2 and detail 2 in the industrial-control category, this board tests whether an agent can execute a conventionally-shaped circuit while getting the physical discipline right rather than the component novelty. The listed stressors — high/low voltage partition, relay flyback, creepage/clearance, terminal placement — are all layout and rating problems, and the brief deliberately withholds the switched-side voltage rating so the agent must select one, choose clearances that are conservative and appropriate to it, and live with the consequences in the floorplan. The real test is whether the separation barrier and the clearance numbers rest on a stated basis or are merely asserted.

This repository is one of thirty-two. The suite, the protocol and the results
live in [PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench).

## Repository layout

| Path | Contents |
|---|---|
| `BRIEF.md` | the supplied brief — authoritative, preserved byte for byte, never edited |
| `board/requirements.md` | what the brief fixes, what it leaves open, and where decisions get recorded |
| `board/requirements.json` | the same split, machine-readable, each fixed requirement bound to brief text |
| `board/manifest.template.json` | the toolkit's minimum manifest, pre-filled for this board |
| `board/toolchain.json` | where this board's build finds KiCad and the router |
| `benchmark/metadata.json` | the supplied catalogue entry — category, difficulty, detail, stressors |
| `docs/architecture.md` | the decisions this board must make, as questions, unanswered |
| `docs/sources.md` | the classes of evidence the design will have to cite |
| `docs/status.md` | what exists, what does not, and what is deliberately absent |
| `candidates/` | disposable search output, ignored by Git |
| `.claude/skills/` | the accountability-review skill [CLAUDE.md](CLAUDE.md) requires before a push |
| `tooling/PCBA_AutoDesignAndTest` | the shared verification/routing/release toolkit, as a pinned submodule |

## Getting the repository

The toolkit is a submodule and carries KiCad Routing Tools as a submodule of its
own, so clone recursively:

```bash
git clone --recursive https://github.com/pentolope/PCBA_QuadRelayController.git
```

```bash
git submodule update --init --recursive
```

## Designing the board

Generic verification, routing and release logic is **not** written here. It is
consumed from `tooling/PCBA_AutoDesignAndTest`, which is board-agnostic by
construction and must stay that way; this repository owns the board and nothing
else. Start from
[the toolkit's onboarding guide](tooling/PCBA_AutoDesignAndTest/examples/onboarding.md),
and see [CLAUDE.md](CLAUDE.md) for the rules a design run works under.

```bash
python3 tooling/PCBA_AutoDesignAndTest/run.py preflight
```

## Brief integrity

`BRIEF.md` SHA-256 `7ed0a0647777bf47b7bdb843b795a63dda5a91aa048535087b107b13f95b585d`

Every quotation in `board/requirements.json` is bound to those exact bytes. If
the brief ever changes, the bindings are stale by construction — which is the
point of recording the digest.
