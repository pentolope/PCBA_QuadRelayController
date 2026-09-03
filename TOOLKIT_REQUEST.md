# Toolkit requests from 03_PCBA_QuadRelayController

What the toolkit would have to contain for this board to have been built with
less reinvention, for the gates it cannot turn on to become available, and for
the three claims it currently reports as UNKNOWN to become answerable.

Everything here is asked for board-agnostically: no request names this board,
its parts or its net names, and each is written as a capability any board
would use. Where a request is grounded in something that happened here, the
specific number is given so the request can be judged rather than taken on
trust.

Board state at the time of writing: 26 gates PASS, 10 NOT_APPLICABLE, 0 FAIL;
78 claims, of which 75 PASS and 3 are UNKNOWN.

---

## 1. A machine-readable manifest schema

**The single largest cost of this board.** Every manifest declaration made in
this session was reverse-engineered by reading gate source and toolkit tests:
`simulation.models`, `simulation.extracted_models`, `timing.interfaces`,
`release_generation.cpl_orientation`, `release_generation.fab_format`,
`via_mask`, `reports.source_closure`. `schemas/` contains only KiCad's own DRC
and ERC schemas, and no document lists manifest keys.

Two concrete failures this caused:

- `timing.interfaces.<name>` needs its paths wrapped in a `routes` object. I
  declared `template`/`bindings` at the interface level, which is well-formed
  JSON, produces no schema error, and fails four gates with
  `PathError: declares no routes`. One full validation cycle to discover a
  key name.
- `release_generation.fab_format` is not mentioned anywhere outside
  `build.py`. Without it the orientation registry silently does nothing (see
  §3 below).

**Request:** a JSON Schema for the manifest, published in `schemas/`, and a
`run.py validate` preflight that checks the manifest against it before any
gate runs. A declaration that names a key the toolkit does not implement
should be refused rather than ignored — the same fail-closed rule the model
registry already applies to unknown model keys.

Secondary, and cheap: `run.py gates --requires <key>` or a generated table of
gate → required manifest keys → link to the schema node. `run.py gates`
already prints the `requires` tuples; what is missing is the shape behind each
key.

---

## 2. Thermal, at all

Section 24 of the architecture asks for thermal as a first-class verification
domain. The toolkit has no thermal gate, no dissipation model, no ambient
declaration and no junction-temperature discipline. I built all of it in the
board (`design/thermal.py`), and every board will build it differently.

Three pieces, in order of value:

### 2a. A declared maximum ambient, and derating from it

The manifest should carry the board's maximum ambient as a first-class
constraint, and there should be a gate that refuses a package rating used at
an ambient the rating was not quoted at.

This caught a real defect here. A driver was judged against its datasheet's
0.9 W figure; that figure is quoted against the part's **ten-second**
junction-to-ambient resistance, so it is a transient rating and the driver is
on continuously. The steady-state limit at the declared ambient is 0.88 W,
derived from the same datasheet's junction limit and steady-state resistance.
The rule generalises: *a power limit applied to a continuously-conducting part
must come from a steady-state thermal resistance, and must be re-derived at
the board's declared ambient rather than read at the datasheet's.*

### 2b. A gate that refuses an unsupported junction-temperature claim

Section 24 already states the rule — a board should not claim a junction
temperature from a generic θJA when the boundary conditions do not match its
validity — and nothing enforces it. The datasheet figures used here are
measured on one square inch of two-ounce copper in still air; this board is
two-layer one-ounce.

**Request:** let a thermal parameter record carry its measurement boundary
conditions, and let a gate compare them against the board's actual stackup and
copper. A mismatch should force the claim to be reported as conditional rather
than as a junction temperature. The pattern this board fell back to — report
the *factor* by which the board's thermal path could be worse than the
datasheet's test board before the limit is reached — is a reasonable default
for the conditional form.

### 2c. A geometry-derived thermal model

**This one closes two of this board's three UNKNOWN claims**, so it is the
highest-value item in this document for verifying reliability:

- `board_temperature_rise_above_ambient` — UNKNOWN. Needs the board's thermal
  resistance to ambient.
- `switched_copper_temperature_rise` — UNKNOWN. Needs a conductor-sizing
  basis. IPC-2152 is copyrighted and cannot be frozen into a repository, but
  a first-principles model — I²R into a copper-and-laminate spreading model
  with a stated convection assumption — is derivable, freezable, and would
  produce a bounded claim where there is currently none.

The toolkit already has everything this needs as inputs: `pcbqa.extract`
traverses real copper, the fabricator catalog supplies finished copper
thickness and board thickness as approved-evidence parameters, and
`pcbqa.claim` can express the result as a bound with its assumptions attached.
What is missing is the solver between them. Even a crude one — 2-D copper
spreading, one convection coefficient declared as an assumption, no radiation
— converts two "we cannot say" claims into "at most N degrees, under these
stated assumptions", which is the difference the evidence model exists to
make.

A third UNKNOWN (parts whose datasheets state no operating temperature range)
is not something the toolkit can fix.

---

## 3. `release_generation.fab_format` silently skips orientation

A genuine trap, and the only one in this session that would have shipped a
wrong board rather than merely costing time.

`Build.orient_cpl` is only reachable from `Build.format_for_fab`, which
returns immediately when the manifest declares no `fab_format`. A board can
therefore declare a complete, reviewed, evidence-backed `cpl_orientation`
registry, and the build will apply none of it. The placement file ships with
raw layout angles.

`CPL.ORIENTATION` does catch it afterwards, which is why this is a trap and
not a hole. But the build reports success, logs nothing, and the failure
surfaces at a gate that names a different cause.

**Request:** a build that has `release_generation.cpl_orientation` and no
`fab_format.cpl` should refuse with a message naming the missing key. More
generally: any declared capability whose application step is unreachable
should be a build blocker, not a silent skip.

---

## 4. A reference implementation for library-zero orientation

`CPL.ORIENTATION` requires the board to supply `tools/jlc_orientation.py` with
`HERE`/`FIXTURES`/`BOARD` globals and a `derive()` that returns
`{part number: {best_offset_deg, best_worst_deg, margin_deg, decisive,
evidence_sha256, evidence_problems}}`. Nothing in the toolkit, its tests or
its documentation says what that script should compute, and no example exists
anywhere in the bench.

Keeping the script inside the project is right — that is what puts it in the
source closure and lets `PROV.SOURCE_CLOSURE` check the content that actually
ran. The *algorithm*, however, is board-agnostic, and getting it wrong is
silent: I had to reason through the y-up/y-down handedness of two libraries,
and through the fact that pairing pads by position cannot distinguish a
polarised two-pad part from the same part reversed. On this board that
distinction was not academic — the LED needs a 180° correction and the diode
beside it needs none, and position matching would have called them the same.

**Request:** ship a reference derivation as a vendorable file (`examples/` or
`profiles/jlcpcb/`) that a board copies in, plus a schema for the frozen
evidence record. Two properties the reference should carry, because both are
easy to get wrong and neither is checkable after the fact:

- pairing by pad number where the two libraries agree on numbering, falling
  back to positional matching only where they do not, **and recording which
  was used** — positional matching decides only what the geometry decides;
- scoring from the raw response body rather than from any normalised extract,
  so that editing the extract produces a visible mismatch rather than a
  different answer.

A `Registry` review status of `reviewed` currently cannot distinguish "a human
compared the part against the library" from "a script derived it from frozen
evidence and re-derives it every release". The second is what an autonomous
agent can honestly produce, and arguably the stronger of the two, but the
field cannot say so. A `review_basis` field with a controlled vocabulary would
let the distinction be recorded rather than argued in a commit message.

---

## 5. Router and placer friction that every board will hit

### 5a. The router reads clearance from the project, not from `--clearance`

Requesting 0.15 mm produced 0.114 mm of actual clearance. The figure the
router honours comes from the project's Default netclass, not from the
`--clearance` argument. The workaround — write a throwaway project with the
Default clearance raised to a margin value, route against it, then restore the
authoritative project and judge against that — is about forty lines that every
board will now carry.

**Request:** either honour `--clearance`, or state in the routing record what
clearance was actually applied so a board can check it rather than measure it.
The margin-project dance belongs in the toolkit if it belongs anywhere.

### 5b. Netclass patterns in `.kicad_pro` are not honoured by `kicad-cli pcb drc`

Every net resolves to Default. I confirmed this by probing, then moved the
board's two insulation clearances into `.kicad_dru` as net-name wildcard rules
and deleted the netclasses, which were judging nothing.

This is KiCad behaviour, not toolkit behaviour, but it is exactly the kind of
silent no-op a validator should refuse to let a board rely on.

**Request:** a check that fails when a project declares netclass membership
patterns and the DRC path in use ignores them — i.e. when a board's design
rules are less strict in practice than the manifest says they are.

### 5c. The placer refuses a board with copper

Correct behaviour — moving a footprint does not move copper — but it means a
board must be able to generate a copper-free variant of itself for placement,
and then regenerate everything conductive from the accepted poses. That is a
workflow every board needs and each will invent. Worth a documented pattern,
or a `run.py place` that manages the seed/optimise/adopt cycle the way
`run.py build` manages the export cycle.

---

## 6. A fast board-integrity preflight

Twice in this session the routed board in the tree was replaced by an
unrouted regeneration — 444 track segments down to 66 — with no command of
mine writing it. On the second occasion a stray `.kicad_prl` belonging to a
*different* board appeared in this directory at the same second, and another
session was demonstrably working in the bench at the time. `ROUTE.PROVENANCE`
caught it, but only at the end of a full validation run, and the first
symptom was an unrelated-looking extraction error.

I added a board-local unit test that hashes the board against
`generated/routing.json`'s `adopted_sha256`. It costs a hash and it is
board-agnostic.

**Request:** `run.py check-board <manifest>` — a sub-second preflight that
verifies the tree's board is the accepted routing candidate and that the
source closure digests still hold, without running DRC, extraction or
simulation. Useful as a pre-commit hook and as the first thing a long
autonomous run does after any external tool touches the tree.

Related, and worth considering separately: the toolkit has no notion of two
processes working in one bench. A lock file keyed on the project root, or a
refusal when a KiCad artifact naming a different project appears beside the
board, would have turned a confusing hour into an immediate error.

---

## 7. Statement kinds and verification methods belong on the requirement

`claim.requirement()` accepts exactly `{name, source, assertion}` and
`_validate_requirement` refuses anything else. Sections 4 and 26 of the
architecture ask for more than that: a requirement should say whether it is a
user requirement, a derived requirement, an assumption or a design decision,
and it should name the verification methods that establish it.

With no field to carry either, this board built a side register
(`constraints/requirements.json`) and encoded the kind into the source string
as `"<kind>:<origin>"`. It works, it is checked in both directions, and it is
a board-local convention that the next board will reinvent differently.

**Request:** first-class `kind` and `verification_methods` fields on a
requirement record, with the §4 and §26 vocabularies as the accepted values,
and validation rules per kind — a derived requirement states what it was
derived from, a design decision states its alternatives, an assumption states
what would invalidate it.

**Request, related:** a gate that joins the claim set to a requirement
register in both directions. A claim judged against an unregistered
requirement and a registered requirement nothing is judged against are both
defects, and neither is currently detectable. This board implements the join
itself; the check is entirely generic.

---

## 8. Evidence documents are cited but never verified

`evidence/index.json` records each datasheet's sha256. The index is in the
source closure; **the documents are not**, and no gate compares a document on
disk against the digest the index claims for it. A datasheet can be replaced
with a different revision and nothing objects, while every claim citing it
continues to look fresh.

The orientation work shows the shape of the fix, because it already does this
properly: the raw library response and its extract are both committed, both
are in the closure, and the extract is re-derived from the body on every read.

**Request:** a `PROV.EVIDENCE_INTEGRITY` gate — every document an evidence
index names exists, matches its recorded digest, and is inside the source
closure; and every document id cited by a parameter record or a claim resolves
to an index entry. The second half of that is what this board implements in
`design/requirements.py::check_origins`, and it is generic.

---

## 9. Two missing simulation primitives

Both were hit deriving the coil turn-off transient, and both are generic to
any board with an inductive load — relays, solenoids, motors, buck converters.

### 9a. No current source

`_ELEMENT_KEYS` offers resistor, capacitor, inductor, `vsource_dc`,
`vsource_pulse` and `model_instance`. There is no current source, so forcing a
known current requires a Thevenin stand-in: a large voltage source and a
series resistance sized against a voltage the measured node provably cannot
reach, so the delivered current is never short. That works and is defensible,
but it is a workaround for a missing primitive and it puts an arithmetic
argument in the board where an element kind would do.

### 9b. No initial condition on an inductor

An inductor's element record is `{kind, name, nodes, value}` with no initial
current, and no analysis kind emits `.ic`. This is why the turn-off scenario
here establishes only the clamp *level* at the instant of switching, and says
nothing about the decay time or the energy the flyback device absorbs. With an
initial condition, the same frozen models would answer both.

**Request:** an `isource_dc` element kind, and an optional `ic` on the
inductor with `.ic` emitted by the ngspice backend.

---

## 10. Inductance extraction

`claim.PHENOMENA` includes `loop_inductance`, and nothing in the toolkit
produces it. `pcbqa.extract` traverses real copper and returns DC resistance
only.

The consequence here: this board declares a flyback turn-off **loop area**
target and checks the geometry against it. Area is a proxy. The quantity that
actually stresses the driver is the loop's inductance, through L·di/dt, and it
is the quantity the claim would rather be about. Because no extractor produces
it, the requirement is registered as a design decision — a self-imposed
numeric target — rather than as a derived requirement with a physical basis.

**Request:** a geometry-derived loop-inductance extraction over a declared
current loop, at the same evidence class the DC-resistance extraction already
carries (`geometry-derived`, board digest embedded, omissions stated). Any
board with a switching element and a commutation loop wants this, and it is
the same copper traversal that already exists.

---

## 11. Fabricator catalog: the via-to-mask process limit

`VIA.MASK_CLEARANCE_PROCESS` and `VIA.NATIVE_GERBER_AGREEMENT` both require
`via_mask.process.limit_mm`. The approved JLCPCB catalog carries via hole and
diameter minima but no via-annulus-to-solder-mask-opening figure — I checked
the normalised catalog and the raw evidence pages. Declaring the number from
memory would be inventing a process limit, so this board declares only its own
0.15 mm design target and two gates stay NOT_APPLICABLE.

**Request:** capture the fabricator's mask-registration and
via-to-mask-opening limits into the approved catalog. One number turns on two
gates for every board.

---

## Not requested

Recorded so the list above is not read as exhaustive of what was noticed.

- `ROUTE.ANGLE_STYLE` staying NOT_APPLICABLE is this board's decision, not a
  toolkit gap. The routing is 252-of-270 corners on multiples of 45°; the
  census is recorded and no angle style is declared, because nothing in the
  brief, the insulation standard or the fabricator's capabilities asks for
  one.
- `TIMING.INTERCONNECT_DELAY` and `TIMING.INTERCONNECT_SKEW` reporting
  measurements and asserting nothing, where a board declares no limit, is
  correct. A relay command has no picosecond budget and inventing one would be
  inventing a requirement.
- `TIMING.SETUP_HOLD`, `FAB.LAYER_IDENTITY` and `PROV.FIXTURE_INTEGRITY` are
  genuinely not this board's: no synchronous interface at speed, no
  net-named inner copper, no frozen fixture.
- The model registry's `CONDITIONS` tuple carrying only `temperature_c` was
  sufficient here, and its own comment already says what it is waiting for.
