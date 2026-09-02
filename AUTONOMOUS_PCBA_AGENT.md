# Autonomous PCBA Agent — Architecture and Development Plan

**Status:** Working architecture / roadmap  
**Scope:** Board-agnostic autonomous PCBA development using KiCad and the `PCBA_AutoDesignAndTest` toolkit  
**Manufacturing target:** JLCPCB unless the toolkit's scope is deliberately changed in the future  
**Primary goal:** Enable an AI agent to turn a product brief into a defensible, manufacturable PCBA with minimal human interaction, while keeping every machine-readable claim inside the evidence actually established.

---

# 1. Mission

The system is intended to develop real PCBAs, not merely produce plausible schematics or visually convincing layouts.

The long-term autonomous flow is:

```text
product brief
    ↓
requirements + assumptions
    ↓
architecture + component selection
    ↓
schematic
    ↓
static schematic verification
    ↓
pre-layout electrical / functional simulation
    ↓
fabrication process + stackup
    ↓
placement + routing constraints
    ↓
placement
    ↓
routing
    ↓
physical validation
    ↓
parasitic extraction
    ↓
post-layout electrical / functional simulation
    ↓
targeted SI / PI / EM / thermal analysis where required
    ↓
design iteration
    ↓
fabrication + assembly outputs
    ↓
release gates
```

The objective is not an AI that merely "draws a PCB." The objective is an autonomous electrical-design system that can:

- interpret an incomplete human brief;
- derive reasonable engineering requirements;
- make and record assumptions;
- select defensible components and architectures;
- build and verify a schematic;
- simulate what can be simulated before spending effort on PCB layout;
- express physical intent as machine-readable constraints;
- use search/optimization for placement and routing;
- extract geometry-dependent electrical behavior;
- repeat simulations with the physical interconnect included;
- diagnose failures in terms of design variables;
- revise the design until the available evidence supports the required claims;
- generate reproducible fabrication and assembly outputs;
- refuse claims that the available evidence does not support.

The system should optimize for **conservative autonomy**: proceed autonomously when a decision is reversible and sufficiently supported, but never convert missing evidence into an implicit PASS.

---

# 2. Implementation context and architectural boundaries

This document describes both current foundations and future target capabilities.

The existing `PCBA_AutoDesignAndTest` toolkit already provides important pieces of the architecture, including:

- KiCad-centered validation;
- fail-closed result handling;
- board-owned declarative policy;
- fabrication and release evidence;
- routing provenance and candidate isolation;
- electrical-path analysis;
- parasitic-related analysis;
- component delay/model concepts;
- simulation scenario, fidelity, digital, and ngspice infrastructure;
- JLCPCB process evidence;
- reproducible release checks.

Not every capability described in this roadmap exists yet.

A future backend or solver must not be represented as implemented merely because the architecture anticipates it. Production code should expose a capability only when there is a real implementation and a defined result contract.

The architecture therefore distinguishes:

```text
implemented capability
planned capability
unsupported capability
```

An unsupported capability is not a degraded PASS.

---

# 3. Roles and authority

The system should divide responsibilities deliberately.

## 3.1 AI agent

The AI is the electrical engineer and iteration controller.

It is responsible for:

- interpreting the product brief;
- deriving requirements;
- recording assumptions;
- selecting architectures;
- selecting components;
- locating and interpreting source evidence;
- choosing which simulations and analyses are necessary;
- defining electrical intent;
- defining placement and routing constraints;
- interpreting failures;
- deciding which design variables to modify;
- deciding when additional analysis is warranted;
- explaining unresolved uncertainty.

The AI should normally specify **intent and constraints**, not manually choose every trace vertex or component coordinate.

---

## 3.2 KiCad project

Native KiCad files are authoritative for the realized electrical and physical design.

They are the authority for things such as:

- schematic connectivity;
- assigned symbols and footprints;
- PCB geometry;
- copper;
- pads;
- vias;
- zones;
- board outline;
- stackup representation;
- net classes;
- design rules.

A generator may be the source of the intended design, as in a generated-board workflow, but the generated KiCad design still must be independently checked for parity with that source.

Nothing is considered physically true merely because a planning document or Python object says it is true.

---

## 3.3 PCBA_AutoDesignAndTest toolkit

The toolkit is the machine-facing authority for:

- validation;
- evidence provenance;
- constraint interpretation;
- model coverage and fidelity;
- physical measurements derived from authoritative design data;
- routing provenance;
- simulation result contracts;
- fail-closed behavior;
- manufacturing validation;
- fabrication artifact binding;
- release gates.

The toolkit should measure and judge declared policy. It should not silently invent board-specific policy.

Board-specific requirements belong in the board repository.

---

## 3.4 Optimization and geometry engines

Numerical/search engines should handle problems where explicit coordinate generation by a language model is weak or unnecessarily brittle.

Examples:

- component placement;
- placement legalization;
- ordinary routing;
- differential routing;
- length or time tuning;
- routing candidate generation;
- candidate ranking;
- geometric optimization.

The AI defines what a good solution means. Search engines explore the geometric solution space.

---

## 3.5 Simulation and extraction backends

Simulation backends establish modeled electrical or functional behavior.

Extraction backends establish physical quantities from PCB geometry.

They must report:

- what was analyzed;
- with what model;
- at what fidelity;
- under what conditions;
- with what omissions;
- with what provenance;
- whether the result is exact, bounded, approximate, unknown, or unsupported where applicable.

A simulator completing successfully does not by itself establish that its models were adequate for the claim being made.

---

## 3.6 Git

Git is the authority for design history and release identity.

Use Git for:

- immutable history;
- branches;
- comparison;
- rollback;
- submodule pins;
- release tags.

Do not invent a parallel revision-control state machine.

A substantial design alternative should be an isolated branch or reproducible candidate, not an undocumented mutation of the accepted board.

---

# 4. Engineering statement types

The autonomous agent should preserve the origin and status of important engineering statements.

At minimum, distinguish:

## 4.1 User requirement

A requirement explicitly stated by the product brief or human stakeholder.

Example:

```yaml
kind: user_requirement
statement: board shall operate from a 5 V host supply
source: product_brief
```

---

## 4.2 Derived engineering requirement

A requirement the agent derives because it is necessary to satisfy a user requirement, safety condition, interface contract, manufacturing constraint, or established engineering limit.

Example:

```yaml
kind: derived_requirement
statement: USB data traces require controlled differential routing
derived_from:
  - USB 2.0 interface requirement
rationale: interface electrical requirements
```

Derived requirements should state their rationale and evidence.

---

## 4.3 Assumption

A fact the brief did not establish but the design currently depends on.

Example:

```yaml
kind: assumption
statement: relay contacts will switch 24 VDC loads
reason: load voltage was not specified
revisable: true
```

Assumptions must remain visible because later evidence may invalidate them.

---

## 4.4 Design decision

A choice among multiple valid implementations.

Example:

```yaml
kind: design_decision
statement: use a star-point current-sense return
alternatives_considered:
  - shared return plane
  - dedicated sense return
rationale: reduce load-current error coupling
```

A design decision must not be presented as though it were a user requirement.

---

## 4.5 Verification requirement

A statement that defines what evidence is needed to establish another requirement.

Example:

```yaml
kind: verification_requirement
requirement: output rail transient droop
method:
  - pre_layout_spice
  - post_layout_spice_with_extracted_pdn
```

This separation makes failures diagnosable. A board can fail because the AI derived the wrong requirement, made a bad assumption, implemented a valid requirement incorrectly, or failed to verify it adequately.

---

# 5. Evidence and claim discipline

The architecture should converge on one conservative evidence vocabulary rather than creating independent notions of "quality" in every subsystem.

A produced quantity should carry, where relevant:

- phenomenon;
- scope;
- value and units;
- knowledge form:
  - exact value;
  - lower bound;
  - upper bound;
  - interval;
  - approximate;
  - unknown;
- evidence class;
- source/provenance;
- applicability;
- operating conditions;
- assumptions;
- omissions;
- requirement being evaluated;
- verdict.

Core rules:

1. **Unknown is not PASS.**
2. **An omitted contribution is not zero.**
3. **A reason for omitting a contribution is not a measurement.**
4. **A lower bound can prove that a maximum is exceeded, but cannot prove that the maximum is met.**
5. **A model that does not cover the required phenomenon cannot be upgraded by another strong model elsewhere in the simulation.**
6. **Simulator convergence is not model adequacy.**
7. **A nominal-design result is not automatically a fabrication or release result.**
8. **A report must not claim more than its dependency closure supports.**

Where the toolkit already has an evidence/claim representation, new producers should migrate into it rather than defining another parallel verdict system.

---

# 6. Repository architecture

## 6.1 PCBA repository

A board repository should own the physical hardware contract and board-level verification intent.

A representative target layout is:

```text
PCBA/
├── schematic/
├── pcb/
├── constraints/
│   ├── requirements.*
│   ├── assumptions.*
│   ├── electrical_paths.*
│   ├── placement.*
│   └── routing.*
├── components/
│   ├── selection.*
│   ├── pin_mappings.*
│   ├── models.*
│   └── provenance.*
├── interfaces/
│   ├── signals.*
│   ├── pins.*
│   ├── clocks.*
│   ├── protocols.*
│   └── electrical_limits.*
├── simulation/
│   ├── scenarios/
│   ├── spice/
│   ├── digital/
│   └── fixtures/
├── extracted/
│   ├── parasitics/
│   ├── sparameters/
│   └── power/
├── fabrication/
├── assembly/
├── generated/
├── docs/
└── tooling/
    └── PCBA_AutoDesignAndTest/
```

This is an architectural organization, not a requirement to rename an existing consumer repository.

The board repository should own:

- product and derived requirements;
- assumptions;
- architecture decisions;
- selected components;
- source provenance;
- schematic and PCB;
- physical/mechanical constraints;
- JLCPCB process and selected stackup;
- pin and electrical interface contracts;
- placement/routing intent;
- timing, impedance, power, safety, thermal, and signal-integrity requirements;
- board-level behavioral models;
- simulation scenarios;
- extracted PCB parasitics and S-parameters;
- model assumptions and fidelity;
- fabrication/assembly decisions;
- release evidence.

---

## 6.2 Generated-board workflows

The architecture must support boards whose schematic and PCB are generated.

A generated design may use a board-owned design source such as:

```text
netlist + component declarations + placement intent
        ↓
schematic generator
        ↓
KiCad schematic
        ↓
PCB generator
        ↓
KiCad PCB
```

This is acceptable only if the generated result is checked.

Useful independent parity gates include:

- design-source netlist ↔ KiCad schematic;
- KiCad schematic ↔ KiCad PCB;
- intended placement constraints ↔ realized PCB placement;
- declared critical-route topology ↔ realized copper.

The generator does not exempt the generated board from ERC, DRC, model mapping, or physical verification.

---

## 6.3 Firmware / software repository

The firmware/software repository should own implementation software.

```text
firmware/
├── hardware/
│   └── pcba/      # submodule pinned to a PCBA revision
├── fpga/
│   ├── rtl/
│   └── tests/
├── mcu/
├── host/
└── integration/
```

The firmware repository may consume machine-readable PCBA artifacts such as:

- pin assignments;
- clocks;
- voltage domains;
- FPGA constraints;
- protocol definitions;
- generated headers;
- board-level behavioral interfaces;
- simulation fixtures.

Do not maintain two independently edited copies of the same board contract.

---

## 6.4 Optional product-integration repository

For larger systems:

```text
product/
├── hardware/
├── firmware/
└── integration/
```

This repository may pin a known-good combination of:

```text
PCBA revision
+ FPGA revision
+ MCU firmware revision
+ host software revision
```

---

# 7. Controlled source acquisition

Autonomous design often requires external evidence:

- datasheets;
- application notes;
- SPICE models;
- IBIS models;
- package drawings;
- reference designs;
- manufacturer process rules;
- assembly capabilities;
- part availability.

The design agent may acquire such evidence during design exploration.

However, **live network state must not determine a release verdict**.

Before an external fact is allowed to support a release-grade claim, it should be frozen or referenced in a reproducible way with appropriate provenance, such as:

- source;
- document identity;
- revision/date;
- retrieval date where relevant;
- applicable device/process;
- units;
- conditions and exceptions;
- content digest where practical.

JLCPCB process data used by the toolkit should follow the toolkit's committed-evidence policy. Manufacturer-independent physics should remain separate from manufacturer-specific capability data.

---

# 8. Component selection is a first-class design stage

Component selection is not a clerical step between architecture and schematic capture.

The agent should evaluate candidate parts against:

- electrical requirements;
- absolute maximum ratings;
- operating conditions;
- package suitability;
- thermal capability;
- supply chain and lifecycle information where available;
- JLCPCB assembly availability when relevant;
- manufacturability;
- footprint confidence;
- documentation quality;
- model availability;
- simulation fidelity;
- interface compatibility;
- cost where the product brief makes cost relevant.

Model availability is an engineering advantage, but absence of a detailed model does not automatically make a part invalid.

The important rule is honesty:

> If a design depends on behavior that cannot be established for the selected component, the resulting claim remains unsupported or provisional.

The agent may prefer a part with a strong vendor model over an otherwise equivalent part with no usable model when that materially improves design confidence.

---

# 9. Symbol, footprint, package, and model correspondence

A critical autonomous-design gate is the mapping:

```text
datasheet package pin
        ↕
schematic symbol pin
        ↕
PCB footprint pad
        ↕
physical package terminal
        ↕
SPICE / IBIS / behavioral model terminal
```

These correspondences must be established independently.

A simulation cannot validate the manufactured implementation if the simulated terminal mapping and physical package mapping can both be wrong in the same way.

The system should record, where applicable:

- manufacturer part number;
- package designation;
- package drawing source;
- symbol source;
- footprint source;
- pad numbering;
- exposed-pad handling;
- no-connect pins;
- power-pad requirements;
- model node order;
- model-to-symbol mapping;
- confidence/provenance.

Hard release blockers should include unresolved contradictions such as:

- footprint pad numbers disagree with package drawing;
- model terminal order is unknown;
- schematic symbol pin type or numbering is incompatible with the selected part;
- selected package variant does not match the footprint;
- required exposed pad is omitted or assigned incorrectly.

---

# 10. Single machine-readable hardware contract

Long term, duplicate declarations across PCB, simulation, firmware, and verification should be minimized.

Example:

```yaml
signals:
  HOST_CLK:
    direction: device_input
    voltage_domain: 3V3
    max_frequency_hz: 25000000
    timing_group: host_bus

  SENSOR_CLK:
    direction: device_output
    nominal_frequency_hz: 3072000
    electrical_path_group: sensor_clock_tree
```

The hardware contract should eventually generate or validate:

- EDA constraints;
- firmware constants;
- FPGA constraints;
- testbench interfaces;
- SPICE stimuli;
- timing constraints;
- ElectricalPath declarations;
- board validation rules;
- simulation scenarios.

The architecture should avoid requiring the agent to keep multiple independent descriptions synchronized by prose.

---

# 11. Design-stage gates

The autonomous workflow should use explicit stages rather than one final "board passes" decision.

A stage may have outcomes such as:

```text
PASS
PROVISIONAL
NOT_APPLICABLE
UNSUPPORTED
BLOCKED
ERROR
```

Exact names should follow the toolkit's implemented result vocabulary; the architectural point is that uncertainty must remain distinct from success.

---

## 11.1 Stage A — brief interpretation

Inputs:

- product brief;
- mechanical attachments;
- interface requirements;
- explicit constraints.

Outputs:

- user requirements;
- derived requirements;
- open questions;
- assumptions;
- verification plan;
- candidate architectures.

The agent should not receive hidden information such as benchmark difficulty or intended failure mode.

---

## 11.2 Stage B — architecture and component selection

Outputs:

- functional block diagram;
- power architecture;
- interface architecture;
- major components;
- risk register;
- component-model inventory;
- preliminary electrical budgets.

The agent should identify high-risk requirements early.

Examples:

- µV-level analog accuracy;
- high-current switching loops;
- controlled-impedance serial links;
- DDR timing;
- RF matching;
- isolation;
- thermals.

---

## 11.3 Stage C — schematic generation and static verification

Before PCB placement, the schematic should undergo static verification.

At minimum, where applicable:

- KiCad ERC;
- required pin connectivity;
- intentional no-connect audit;
- power-domain compatibility;
- regulator input/output limits;
- device absolute maximum checks;
- passive voltage/current/power ratings;
- connector pinout verification;
- interface voltage compatibility;
- reset/strap configuration;
- pull-up/pull-down sanity;
- output-contention checks;
- power-sequencing constraints;
- symbol/package/model mapping checks;
- netlist parity for generated designs.

A schematic with known blocking electrical errors should not proceed into detailed PCB layout merely because it can be routed.

---

# 12. Pre-layout electrical and functional simulation

**Pre-layout simulation is an explicit design gate.**

Before detailed PCB placement and routing, the agent should execute every meaningful electrical or functional scenario that can be evaluated from the schematic and the available models.

The purpose is to catch circuit-level failures before investing substantial effort in physical design.

---

## 12.1 What pre-layout simulation should test

Depending on the board:

### Power

- DC operating point;
- nominal rail voltages/currents;
- input-voltage corners;
- startup;
- shutdown;
- sequencing;
- load steps;
- transient droop;
- regulator stability where the available model supports it;
- current limiting;
- modeled fault cases.

### Analog

- bias points;
- gain;
- bandwidth;
- filtering;
- common-mode range;
- headroom;
- stability;
- noise where model fidelity supports it;
- input/output loading;
- sensor-conditioning behavior.

### Switching power and motor drive

- switch-node behavior;
- duty-cycle range;
- gate drive;
- dead time;
- inductor current;
- current-limit behavior;
- startup;
- load transients;
- control-loop behavior where models permit.

### Digital / mixed-signal boundaries

- reset sequencing;
- logic thresholds;
- voltage-domain compatibility;
- representative transactions;
- clock generation;
- basic timing relationships;
- contention;
- startup state.

---

## 12.2 Interconnect before layout

Pre-layout simulation does not yet have authoritative routed geometry.

Interconnect may therefore be represented as:

- ideal wires;
- explicitly estimated lumped R/L/C;
- nominal transmission lines;
- bounded analytic estimates;
- declared placeholder interconnect models.

The scenario must state which representation was used.

An ideal-wire pre-layout PASS does not establish post-layout signal integrity.

---

## 12.3 Pre-layout simulation policy

Do **not** require an impossible transistor-level whole-board model.

The correct rule is:

> Run all meaningful pre-layout simulations supported by available evidence, and explicitly report what could not be established.

A missing model can produce:

```text
unsupported
unknown
provisional
```

depending on the claim and policy.

It should not silently produce PASS.

Whether PCB work may proceed despite an unevaluated scenario is a policy question.

A reversible design may proceed provisionally when the missing evidence does not invalidate the architecture. A claim required for fabrication or release may remain blocking until adequate evidence exists.

---

## 12.4 Pre-layout iteration

A pre-layout failure should return to the responsible design variables:

```text
failure
  ├── component selection
  ├── topology
  ├── passive value
  ├── bias point
  ├── protection network
  ├── termination
  ├── power architecture
  └── model/assumption
```

The agent should correct the schematic-level problem before detailed PCB design.

---

# 13. Model registry and fidelity

Every simulated component or extracted quantity should identify its source and validity.

Possible model/evidence classes include:

```text
vendor-spice
vendor-ibis
rtl
datasheet-behavioral
assumed-behavioral
measured-behavioral
analytic-interconnect
quasi-static-extracted
full-wave-extracted
measured
unsupported
```

Do not treat these as a universal scalar quality ladder. Fidelity is phenomenon-dependent.

A model record should include, where relevant:

- identity/version;
- source/provenance;
- applicable component/package;
- terminal mapping;
- modeled phenomena;
- validity domain;
- reference temperature;
- voltage/current range;
- frequency range;
- consumed parameters;
- omissions;
- uncertainty or bounds if established;
- whether it may support nominal design;
- whether it may support a particular release claim.

---

## 13.1 Contributor-scoped model coverage

A mixed-fidelity simulation must not let one high-quality model "bless" a weak or missing contributor.

For each asserted measurement, the system should determine the dependency/contribution closure and report the coverage of each relevant model.

Example:

```text
measurement: 3V3 transient minimum
contributors:
    regulator vendor model        supported
    output capacitor ESR/ESL      bounded analytic
    load model                    datasheet behavioral
    PCB supply path               ideal in pre-layout run
```

This makes clear what the result actually establishes.

---

# 14. Primary SPICE backend

Use **ngspice** as the preferred automated SPICE backend.

Reasons:

- open;
- scriptable;
- suitable for CI;
- compatible with deterministic generated decks;
- practical for batch simulation;
- suitable for mixed-fidelity board scenarios.

LTspice or another simulator may be useful for:

- vendor-model compatibility;
- independent comparison;
- debugging a model that ngspice cannot evaluate.

No single simulator should define "whole-board verification."

---

# 15. Digital simulation

## 15.1 FPGA

When production RTL exists, use Verilator or another deterministic RTL backend where practical.

The PCBA repository may initially contain a simpler behavioral contract that captures only what the board requires.

```text
board simulation scenario
        │
        ├── board-owned behavioral model
        │
        └── production RTL
                │
                ▼
          digital simulator
```

Desired invariant:

> Production RTL must satisfy the board-level behavioral contract assumed by the electrical design.

---

## 15.2 MCU / SoC

Do not attempt transistor-level MCU simulation.

For PCBA verification, model the boundary behavior that affects the board:

- pin switching;
- voltage levels;
- source impedance;
- edge rate;
- timing;
- thresholds;
- pin capacitance;
- reset/startup sequence;
- protocol behavior;
- approximate load/current behavior when justified.

Possible levels:

1. board-owned behavioral stimulus;
2. emulator/virtual platform;
3. production firmware connected to a simulation harness;
4. hardware-in-the-loop after prototypes exist.

---

## 15.3 Simple digital logic

Use, in preference order where applicable:

- vendor electrical model;
- IBIS;
- SPICE/XSPICE;
- datasheet-derived behavioral model;
- explicit unsupported state.

A functional digital model must not silently imply accurate analog pin behavior.

---

# 16. ElectricalPath as a first-class concept

Routers operate on nets.

Electrical requirements often operate on a complete source-to-receiver path:

```text
driver package
    ↓
copper
    ↓
series resistor
    ↓
copper
    ↓
via transition
    ↓
receiver package
```

The toolkit therefore needs a first-class **ElectricalPath** representation independent of net boundaries.

ElectricalPath may carry requirements such as:

- maximum propagation delay;
- skew relative to another path;
- impedance;
- insertion loss;
- component traversal delay;
- allowed layer transitions;
- via count;
- topology;
- source/receiver identities.

Component traversals must not be assigned zero delay merely because their delay is unknown.

---

# 17. Fabrication process and stackup selection

The current manufacturing scope is JLCPCB.

The board should deliberately select a fabrication process and stackup before physical constraints that depend on them are frozen.

Selection may consider:

- layer count;
- finished thickness;
- copper weights;
- dielectric construction;
- controlled-impedance capability;
- via process;
- minimum track/space;
- minimum holes;
- solder-mask constraints;
- surface finish;
- assembly capability;
- cost;
- availability of required process options.

The selected stackup becomes an input to:

- impedance calculations;
- propagation estimates;
- via models;
- power resistance;
- plane geometry;
- future field solving.

Manufacturer process limits and conservative board design targets must remain distinct.

---

# 18. Placement strategy

## 18.1 Constraint-driven placement

The AI should normally generate:

- fixed anchors;
- functional blocks;
- grouping;
- relative relationships;
- orientation preferences;
- signal-flow order;
- power-flow order;
- keepouts;
- thermal restrictions;
- high-current-loop relationships;
- sensitive/noisy separation;
- mechanical restrictions.

A numerical optimizer should search the remaining freedom.

---

## 18.2 Semantic placement constraints

Examples:

- connector must lie on a specified edge;
- ESD protection must sit between connector and protected circuitry;
- decoupling must be electrically and geometrically close to target power pins;
- series termination must be near the driver when source termination is intended;
- switching hot loop must be compact;
- crystal/oscillator loop must be compact;
- current-sense routing must avoid load-current error;
- RF matching parts must form a controlled short structure;
- antenna keepout must be preserved;
- sensor exposure must remain mechanically valid;
- heat sources must be separated from temperature-sensitive circuitry;
- assembly access must be preserved.

The optimizer searches **inside** these constraints rather than trying to rediscover their meaning from wire length.

---

## 18.3 Placement objective

Placement should not be optimized by wire length alone.

Candidate scoring may include:

- route feasibility;
- congestion;
- critical-path geometry;
- estimated loop area;
- PDN path length;
- decoupling relationship;
- sensitive/aggressor proximity;
- predicted via count;
- thermal spacing;
- assembly margin;
- mechanical margin.

---

# 19. Routing strategy

Use a hybrid routing architecture.

## 19.1 Critical topology planner

Reserve deterministic/special treatment for structures whose topology itself matters:

- clock trees;
- controlled source termination;
- switching loops;
- current-sense Kelvin paths;
- differential pairs;
- BGA/QFN escapes;
- RF launches;
- matched electrical paths;
- sensitive analog routes;
- unusual mechanical geometry.

Critical routes may be explicitly generated when there is effectively no useful search freedom.

---

## 19.2 General autorouter

Use the routing engine for ordinary connectivity under declared constraints.

Routing attempts should:

- operate on candidate boards;
- never silently alter the authoritative board;
- record the source digest;
- record the routing plan;
- record tool identity/version;
- record configuration;
- record output candidates;
- record DRC;
- record acceptance metrics;
- avoid hidden retry loops.

---

## 19.3 Length and time tuning

Length matching is only a proxy for electrical timing.

The toolkit should prefer:

```text
electrical path delay / skew requirement
        ↓
router-level length targets where valid
        ↓
post-route electrical-path measurement
```

The final verification applies to the electrical requirement, not merely to a net-length number.

---

# 20. Physical PCB verification before extraction

After placement/routing and before expensive simulation, run cheap deterministic checks first.

Examples:

- KiCad DRC;
- schematic parity;
- unconnected nets;
- topology rules;
- placement constraints;
- routing-layer constraints;
- via budgets;
- copper-to-edge;
- creepage/clearance where applicable;
- package spacing;
- courtyard/interference checks;
- mask rules;
- manufacturing constraints;
- critical-net topology;
- reference-plane continuity proxies;
- assembly restrictions.

There is no reason to run expensive EM on a board that still has a basic DRC or topology failure.

---

# 21. Parasitic extraction

Parasitic analysis should proceed in increasing fidelity and cost.

## 21.1 Tier 1 — geometry and closed-form/analytic extraction

From authoritative PCB geometry and the physical stackup:

- conductor length;
- cross-section;
- DC resistance;
- approximate capacitance;
- approximate inductance;
- characteristic impedance;
- propagation delay;
- via transitions;
- reference-plane context;
- parallel-run geometry;
- unreferenced length.

Every result must state the model used and unsupported geometry.

---

## 21.2 Tier 2 — quasi-static extraction

A higher-fidelity backend should eventually extract:

- resistance per unit length;
- capacitance per unit length;
- inductance per unit length;
- mutual capacitance;
- mutual inductance;
- odd/even-mode impedance;
- differential/common-mode behavior;
- coupling;
- via parasitics;
- arbitrary cross-section effects.

Results should use the same claim/evidence interface as analytic extraction.

---

## 21.3 Tier 3 — targeted full-wave extraction

Use a full-wave backend such as openEMS only where the simpler model is insufficient and the answer may change a design decision.

Do not begin with whole-board full-wave simulation.

Good candidates:

- connector launches;
- via transitions;
- high-speed differential discontinuities;
- RF structures;
- coupled aggressor/victim regions;
- unusual return-path transitions;
- package-to-connector paths.

Flow:

```text
authoritative PCB geometry
        ↓
region / ElectricalPath selection
        ↓
EM submodel
        ├── traces
        ├── vias
        ├── nearby copper
        ├── planes
        ├── dielectric
        └── ports
        ↓
solver
        ↓
Touchstone / field data
        ↓
analysis
        ├── TDR
        ├── impedance
        ├── group delay
        ├── insertion loss
        ├── return loss
        └── crosstalk
        ↓
claim / gate
```

The hard problem is not calling the solver; it is trustworthy geometry translation, meshing, port definition, reference definition, boundary conditions, frequency range, and de-embedding.

The backend must refuse release-grade claims when those cannot be established.

---

# 22. Post-layout simulation

After parasitic extraction, applicable pre-layout scenarios should be rerun with the physical interconnect substituted.

This is a second simulation stage, not merely another unrelated report.

The useful comparison is:

```text
pre-layout model
        vs
post-layout model
```

The agent should be able to ask:

- Did PCB resistance materially change the rail margin?
- Did via inductance create ringing?
- Did trace delay reduce setup/hold margin?
- Did real clock-tree skew exceed the original budget?
- Did coupling inject unacceptable error into an analog channel?
- Did the decoupling-loop geometry degrade transient behavior?
- Did the routed impedance invalidate the nominal termination?
- Did a switching loop become too inductive?

Post-layout simulation can therefore expose failures that were impossible to see at schematic stage.

---

## 22.1 Electrical/digital bridge

Long-term target:

```text
RTL / behavioral transition
        ↓
electrical output-driver model
        ↓
package model where available
        ↓
extracted PCB interconnect
        ↓
receiver electrical model
        ↓
threshold-crossing event
        ↓
digital timing assertion
```

Timing assertions should use receiver threshold-crossing time when the required models exist, not ideal RTL edge time.

---

# 23. Power integrity

Power integrity deserves an explicit analysis path.

Possible quantities:

- source-to-load DC resistance;
- distribution voltage drop;
- via/current bottlenecks;
- plane spreading resistance;
- decoupling-loop inductance;
- plane inductance;
- local supply impedance;
- PDN impedance versus frequency;
- anti-resonances;
- transient droop.

PI results should eventually feed both simulation and placement/routing optimization.

---

# 24. Thermal analysis

Thermal behavior should be a first-class verification domain rather than only a placement heuristic.

Depending on capability and available evidence:

- component dissipation;
- copper spreading;
- via thermal conductance;
- junction-to-board/package thermal paths;
- ambient assumptions;
- airflow assumptions;
- heat-source proximity;
- temperature-sensitive component error;
- regulator/MOSFET thermal margin.

A simple thermal estimate must be labeled as such.

A board should not claim a specific maximum junction temperature merely from a generic package θJA number when the actual boundary conditions do not match its validity.

Physical prototype testing may remain necessary for release confidence on thermally demanding designs.

---

# 25. Assembly and DFA

The target is a **PCBA**, not only a bare PCB.

The architecture should have explicit assembly checks or board-owned constraints for items such as:

- component spacing;
- courtyards;
- pick-and-place access;
- placement side;
- package orientation;
- paste-mask design;
- thermal-pad paste segmentation;
- via-in-pad process;
- hand-soldered parts;
- DNP handling;
- component height;
- fiducials;
- board handling;
- reflow compatibility;
- moisture-sensitive components;
- acoustic/optical openings;
- connector insertion access.

JLCPCB's online assembly preview may expose information that cannot be fully validated locally. Such steps should be recorded as external/manual release dependencies rather than silently assumed.

---

# 26. Verification-method classification

Every significant requirement should identify the strongest verification method currently available.

Useful classes include:

```text
STATIC
GEOMETRY
ANALYTIC
CIRCUIT_SIM
DIGITAL_SIM
EXTRACTED
EM_SIM
THERMAL_SIM
MANUFACTURING_CHECK
PHYSICAL_TEST
DOCUMENTATION
```

A requirement may require more than one class.

Examples:

```text
USB differential impedance
    → GEOMETRY + EXTRACTED
    → EM_SIM for suspicious discontinuities

buck converter control-loop stability
    → CIRCUIT_SIM
    → PHYSICAL_TEST if model fidelity is inadequate

IEC ESD survival
    → GEOMETRY / protection review
    → PHYSICAL_TEST for compliance claim
```

The agent should be rewarded for correctly saying **physical validation is still required** when simulation cannot establish the requirement.

---

# 27. Design iteration

A failure should identify the design variables most likely responsible.

Possible variables:

- component;
- topology;
- resistor/capacitor/inductor value;
- regulator;
- termination;
- decoupling;
- placement;
- orientation;
- stackup;
- trace width;
- trace spacing;
- routing layer;
- via type;
- via count;
- routing corridor;
- return-path geometry;
- power-plane geometry;
- thermal copper;
- requirement assumption.

The iteration controller should route the failure upstream to the earliest stage that can actually fix it.

Example:

```text
post-layout clock overshoot
        ↓
is routing topology wrong?
        ├── yes → reroute / replace physical candidate
        └── no
              ↓
is source termination inadequate?
        ├── yes → schematic value change
        │         ↓
        │       rerun pre-layout simulation
        │         ↓
        │       regenerate PCB
        └── no → improve model / targeted extraction
```

Do not force every post-layout failure into a routing-only fix.

---

# 28. Electrical quality as optimization feedback

The long-term closed loop is:

```text
candidate
    ↓
route
    ↓
cheap physical checks
    ↓
analytic extraction
    ↓
selected simulation
    ↓
score
    ├── poor → modify candidate/design variable
    └── good → retain
```

Potential hard constraints:

- schematic connectivity;
- DRC;
- mechanical constraints;
- fabrication constraints;
- required topology;
- safety constraints;
- mandatory timing;
- mandatory power limits.

Potential soft objectives:

- congestion;
- via count;
- route length;
- electrical-path delay;
- skew;
- impedance error;
- coupling;
- loop inductance;
- PDN impedance;
- thermal margin;
- manufacturing margin;
- assembly margin.

The optimizer should improve **electrical quality**, not merely connectivity.

---

# 29. Generic electrical-quality metrics

The toolkit should report comparable revision-to-revision metrics.

## 29.1 Interconnect

Per critical ElectricalPath:

- total copper length;
- layer distribution;
- via count;
- via vertical length;
- DC resistance;
- capacitance;
- inductance;
- characteristic impedance;
- propagation delay;
- skew;
- reference-plane changes;
- unreferenced length;
- model completeness.

---

## 29.2 Coupling

For sensitive structures:

- nearest-neighbor spacing;
- parallel-run length;
- mutual capacitance;
- mutual inductance;
- NEXT/FEXT;
- S31/S41 where extracted.

---

## 29.3 Power

Per rail:

- distribution resistance;
- distribution inductance;
- decoupling-loop inductance;
- regulator-to-load impedance;
- PDN impedance versus frequency;
- transient droop;
- current bottlenecks.

---

## 29.4 Signal integrity

For selected interfaces:

- receiver rise/fall time;
- overshoot;
- undershoot;
- ringing;
- threshold-crossing time;
- setup/hold margin;
- TDR discontinuities;
- return loss;
- insertion loss;
- eye margin where meaningful.

---

## 29.5 Implementation quality

- unrouted nets;
- routing retries;
- via count;
- routed copper;
- congestion;
- DRC margin;
- fabrication-rule margin;
- assembly margin;
- optimizer effort;
- simulation cost;
- extraction cost;
- unresolved assumptions;
- unsupported claims.

---

# 30. Autonomous action policy

A result should carry enough policy for the agent to know what it permits.

Representative policy states:

```text
nominal-design-allowed
provisional-layout-allowed
analysis-only
requires-additional-evidence
requires-human-review
fabrication-ready
release-ready
blocked
```

The policy should answer questions such as:

- may the agent choose a nominal track width?
- may it reserve routing space?
- may it continue placement?
- may it continue routing?
- may it select a JLCPCB process?
- may it mark an electrical requirement satisfied?
- may it generate fabrication outputs?
- may the release gate pass?

A positive result at one stage should not automatically authorize all later stages.

---

# 31. Branches, candidates, and reproducibility

Substantial alternatives should remain isolated.

Principles:

- `main` represents a deliberately accepted state;
- architecture changes occur on branches;
- routing/placement attempts may use reproducible candidates;
- the authoritative board is not silently modified by an optimizer;
- every candidate records its source state and tool provenance;
- accepted candidates are promoted deliberately;
- generated evidence belongs to the state that produced it;
- submodule pins must resolve to commits available from their configured remotes before the parent state is considered portable.

A later failure should be reproducible from the recorded design state.

---

# 32. Release and fabrication closure

The current toolkit treats a release as a Git tag over a validated commit.

The autonomous agent may prepare a release, but release identity and engineering proof should remain distinct.

A design becomes release-ready only when:

- required schematic checks pass;
- required PCB checks pass;
- required electrical constraints are evaluated;
- mandatory unresolved assumptions are closed;
- required simulation/extraction evidence exists;
- required JLCPCB process constraints are established;
- fabrication selections are bound;
- assembly constraints are addressed;
- generated outputs correspond to the validated design state;
- model/tool/process provenance is adequate;
- the working tree and submodules satisfy release policy;
- unresolved unsupported claims are either explicitly permitted or blocking according to board policy.

Fabrication artifacts should be reproducible and tied to the exact design source closure.

A release should never depend on a live web lookup changing the verdict.

---

# 33. Parallel development strategy for the toolkit

The toolkit self-test is valuable but should not dominate every isolated change.

Use focused workstreams.

## Track A — unified evidence model

- migrate remaining timing/simulation producers into the shared claim model;
- preserve exact/bound/approximate/unknown semantics;
- remove duplicate verdict logic where possible.

## Track B — component and package provenance

- package pin mapping;
- symbol/footprint consistency;
- simulation-model terminal mapping;
- component-source registry;
- part-selection evidence.

## Track C — pre-layout simulation

- schematic-derived scenario generation;
- ngspice scenario expansion;
- power and analog scenarios;
- schematic-stage model coverage;
- iteration results suitable for the agent.

## Track D — digital simulation

- behavioral board contracts;
- Verilator execution;
- FPGA/MCU/host/peripheral boundary models;
- substitution of production RTL.

## Track E — parasitic extraction

- geometry extraction;
- R/L/C;
- propagation;
- via models;
- coupling;
- ElectricalPath integration.

## Track F — placement optimization

- semantic placement schema;
- candidate generator;
- optimization;
- legalization;
- route-aware scoring.

## Track G — routing modernization

- differential routing;
- buses;
- fanout;
- propagation-time-aware tuning;
- ElectricalPath-to-router constraint mapping.

## Track H — power integrity

- DC network extraction;
- decoupling-loop analysis;
- PDN impedance;
- transient scenario integration.

## Track I — targeted EM

- geometry exporter;
- ports;
- meshing;
- fixtures;
- Touchstone import;
- TDR/crosstalk/S-parameter claims.

## Track J — thermal / assembly

- basic thermal estimates;
- thermal provenance;
- assembly constraints;
- JLCPCB assembly validation where locally establishable.

## Track K — autonomous integration

- end-to-end board-development scenarios;
- failure-to-design-variable mapping;
- branch/candidate orchestration;
- release evidence.

---

# 34. Test cadence

Preferred cadence:

```text
focused unit tests
    ↓
workstream integration tests
    ↓
consumer-board tests
    ↓
cross-workstream integration
    ↓
full toolkit selftest
    ↓
end-to-end autonomous design validation
```

Independent simulations, extraction jobs, and candidate evaluations should run concurrently where doing so is deterministic and safe.

The full self-test should run at coherent integration points, not after every local edit.

---

# 35. Capability roadmap

## Phase 1 — evidence and policy convergence

Stabilize:

- one claim/evidence model;
- provenance;
- bounds/unknown semantics;
- design-stage vs release-stage policy.

---

## Phase 2 — component and schematic confidence

Add or strengthen:

- part-selection records;
- package/pin verification;
- symbol/footprint/model correspondence;
- schematic static gates;
- generated-design parity.

---

## Phase 3 — pre-layout simulation gate

Build out:

- generic scenario generation;
- ngspice coverage;
- power scenarios;
- analog scenarios;
- mixed behavioral scenarios;
- agent-readable failure diagnosis.

This phase should make **schematic simulation occur before detailed PCB design** whenever the models support meaningful evaluation.

---

## Phase 4 — analytic parasitic extraction

Expand:

- resistance;
- capacitance;
- inductance;
- propagation delay;
- impedance;
- vias;
- coupling approximations;
- ElectricalPath totals.

Make these results directly consumable by post-layout simulation.

---

## Phase 5 — placement and routing optimization

Introduce:

- semantic placement;
- search-based placement;
- route-in-loop scoring;
- differential/bus routing;
- time-aware tuning.

---

## Phase 6 — post-layout mixed-fidelity simulation

Connect:

- functional digital models;
- SPICE;
- package models where available;
- extracted PCB interconnect;
- timing assertions;
- SI assertions;
- power assertions.

Reuse applicable pre-layout scenarios so physical effects are measurable as deltas.

---

## Phase 7 — higher-fidelity PI / quasi-static / EM

Add stronger solvers only for problems where the simpler evidence is inadequate.

Do not add a backend dispatch abstraction until a real backend exists.

---

## Phase 8 — optimization against electrical simulation

Use extraction/simulation results to modify:

- component selection;
- placement;
- routing;
- stackup;
- termination;
- decoupling;
- topology.

---

## Phase 9 — PCBA closure

Add stronger:

- thermal validation;
- assembly validation;
- test-point/access checks;
- production evidence;
- release closure.

---

# 36. Long-term autonomous PCBA development loop

```text
1. Product brief
        ↓
2. Interpret brief
        ├── user requirements
        ├── derived requirements
        ├── assumptions
        └── verification plan
        ↓
3. Architecture exploration
        ↓
4. Component selection + source/model acquisition
        ↓
5. Package / symbol / footprint / model mapping
        ↓
6. Schematic generation
        ↓
7. Static schematic verification
        ├── ERC
        ├── connectivity
        ├── ratings
        ├── voltage domains
        ├── pin mappings
        └── generated-design parity
        ↓
8. Pre-layout simulation
        ├── SPICE
        ├── digital / behavioral
        ├── power
        └── functional scenarios
        ↓
9. Schematic/architecture acceptable?
        │
        ├── no → modify architecture/components/values/models
        │         and return upstream
        │
        └── yes or explicitly provisional
                  ↓
10. Select JLCPCB process + stackup
                  ↓
11. Freeze physical electrical intent
                  ├── ElectricalPaths
                  ├── impedance
                  ├── timing
                  ├── topology
                  ├── PI
                  ├── thermal
                  └── assembly
                  ↓
12. Functional floorplan
                  ↓
13. Placement optimization
                  ↓
14. Critical topology / fanout generation
                  ↓
15. General routing
                  ↓
16. Length / time tuning
                  ↓
17. Cheap physical checks
                  ├── DRC
                  ├── parity
                  ├── topology
                  ├── placement
                  ├── manufacturing
                  └── assembly
                  ↓
18. Analytic parasitic extraction
                  ↓
19. Post-layout simulation
                  ├── extracted interconnect
                  ├── power
                  ├── analog
                  ├── digital timing
                  └── mixed-signal
                  ↓
20. Higher-fidelity analysis required?
        │
        ├── yes → quasi-static / PI / targeted EM / thermal
        │
        └── no
                  ↓
21. Requirements established?
        │
        ├── no
        │    ↓
        │  classify responsible variable
        │    ├── assumption/requirement → return to interpretation
        │    ├── component/topology/value → return to schematic
        │    ├── stackup → return to process selection
        │    ├── placement → regenerate candidate
        │    ├── routing → regenerate candidate
        │    └── model/evidence → improve verification
        │
        └── yes
                  ↓
22. Build fabrication + assembly outputs
                  ↓
23. Validate exact outputs
                  ↓
24. Release-check
                  ↓
25. Deliberate Git release tag
```

The board should graduate from one confidence level to the next only when the corresponding evidence exists.

---

# 37. Guiding principles

1. **The AI owns engineering intent; search engines own most geometric search.**
2. **Native KiCad files are authoritative for the realized schematic and PCB.**
3. **Generated designs are allowed, but generation does not replace independent parity checks.**
4. **User requirements, derived requirements, assumptions, and design decisions must remain distinguishable.**
5. **Component selection is part of electrical design, not merely BOM filling.**
6. **Model terminals, schematic pins, footprint pads, and physical package pins must correspond before simulation can validate hardware.**
7. **Unknown is not PASS.**
8. **An omitted contribution is not zero.**
9. **Models must carry provenance, applicability, conditions, and omissions.**
10. **Simulation should use mixed fidelity rather than inventing nonexistent detailed models.**
11. **Run the strongest meaningful schematic-level simulation before detailed PCB design.**
12. **A pre-layout PASS validates only the modeled circuit under the stated interconnect assumptions.**
13. **After layout, rerun applicable scenarios using geometry-derived interconnect.**
14. **Electrical requirements belong to complete ElectricalPaths when net boundaries do not match the physical requirement.**
15. **Placement and routing should be optimized against electrical quality, not just connectivity.**
16. **Expensive physics should be targeted where it can change a decision.**
17. **Cheap deterministic failures should be found before expensive simulation.**
18. **Every failure should point toward design variables the agent can modify.**
19. **A post-layout problem may require a schematic change; do not force every failure into routing.**
20. **Fabrication and assembly constraints are distinct from nominal electrical design.**
21. **A useful provisional result is not automatically a release result.**
22. **Live network state must not change release validation.**
23. **The toolkit should remain board-agnostic; board-specific policy belongs to consumer repositories.**
24. **The current manufacturing target is JLCPCB; do not invent a multi-fabricator abstraction without a real need and implementation.**
25. **An architecture document may describe future capability, but production code must not pretend an unimplemented backend exists.**
26. **Git owns history and release identity; engineering tooling owns evidence that a tagged state is acceptable.**
27. **The final authority for behavior that simulation cannot establish is physical test, and the system should say so explicitly.**

---

# 38. Desired end state

The desired system can accept an unfamiliar PCBA brief and autonomously produce a traceable chain:

```text
human intent
    ↓
engineering requirements
    ↓
recorded assumptions
    ↓
component and architecture rationale
    ↓
verified schematic
    ↓
pre-layout electrical evidence
    ↓
physical constraints
    ↓
optimized PCB candidate
    ↓
verified physical implementation
    ↓
extracted parasitics
    ↓
post-layout electrical evidence
    ↓
targeted higher-fidelity analysis
    ↓
documented residual uncertainty
    ↓
reproducible fabrication / assembly artifacts
    ↓
release evidence
```

Success is not "the files look plausible."

Success is that the agent can explain, with machine-verifiable evidence, **what it believes about the board, why it believes it, which assumptions remain, which physical effects were evaluated, which could not be evaluated, and why the exact design state is suitable—or not suitable—for fabrication and release.**
