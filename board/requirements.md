# Requirements — Four-Channel Relay Controller

Two lists. The difference between them is the whole point of this file.

A **fixed requirement** is something [BRIEF.md](../BRIEF.md) asks for. Each one
below quotes the brief text that substantiates it; if a statement cannot be
quoted, it is not a requirement here. An **open decision** is a choice the brief
deliberately left to whoever designs this board.

> Missing details are design freedom, not permission to fabricate unstated user
> requirements.

Promoting a decision into a requirement is the failure this file exists to
prevent. Record a choice under the decision it answers, with the reasoning that
made it — never by adding it to the list above.

Bound to `BRIEF.md` SHA-256 `7ed0a0647777bf47b7bdb843b795a63dda5a91aa048535087b107b13f95b585d`.

## Fixed by the brief

### REQ-01 — The board is a four-channel relay controller — four relay channels, no more and no fewer.

Brief text:

> Design a four-channel relay controller operated by a small MCU.

### REQ-02 — The relay channels are operated by a small MCU on the board.

Brief text:

> relay controller operated by a small MCU. Logic power is 5 V

### REQ-03 — Logic power is 5 V.

Brief text:

> Logic power is 5 V; each relay switches an external load through screw terminals.

### REQ-04 — Each relay switches an external load, and that load connects through screw terminals.

Brief text:

> each relay switches an external load through screw terminals

### REQ-05 — The design includes input protection.

Brief text:

> Include input protection, transistor/MOSFET relay drivers

### REQ-06 — The relay drivers are transistor or MOSFET drivers.

Brief text:

> transistor/MOSFET relay drivers, flyback suppression

### REQ-07 — The design includes flyback suppression.

Brief text:

> flyback suppression, status indication, and a programming interface.

### REQ-08 — The design includes status indication.

Brief text:

> status indication, and a programming interface.

### REQ-09 — The design includes a programming interface.

Brief text:

> and a programming interface. Keep the switched side physically separated

### REQ-10 — The switched side is kept physically separated from the logic side.

Brief text:

> Keep the switched side physically separated from the logic side

### REQ-11 — Clearances are conservative and appropriate to a voltage rating that the design agent selects and documents.

Brief text:

> choose conservative clearances appropriate to the voltage rating you select and document.

### REQ-12 — Stated brief requirements are authoritative; open choices are to be made and documented as engineering decisions, never converted into invented user requirements.

Brief text:

> Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements.

### REQ-13 — This repository stays a consumer of the shared PCBA_AutoDesignAndTest toolkit; board-specific logic must not accumulate in the toolkit.

Brief text:

> The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.

## Open — the design agent decides

### OPEN-01 — MCU selection — family, core, package, memory, I/O count, operating voltage, and whether it runs directly at the 5 V logic rail or from a derived rail.

The brief says only "a small MCU" and names no device, vendor, architecture or package.

*Decision:* **not yet made.**

### OPEN-02 — Programming interface — which standard, how it is physically presented (connector, header, or bare pads), and its pinout, footprint, keepout and whether it also serves as a debug or console port.

The brief requires "a programming interface" but names no protocol and no physical form for it.

*Decision:* **not yet made.**

### OPEN-03 — Relay selection — coil voltage and current, contact form (SPST/SPDT/DPDT), contact rating and material, mounting style, and coil-to-contact dielectric rating.

The brief names no relay and states no contact rating; it only says each relay switches an external load.

*Decision:* **not yet made.**

### OPEN-04 — Relay coil supply — whether coils run from the 5 V logic rail or a separate coil rail, and how that rail is generated, sequenced and decoupled against four simultaneous coil inrushes.

The brief fixes only that "Logic power is 5 V"; it is silent on the coil supply.

*Decision:* **not yet made.**

### OPEN-05 — Driver stage topology — discrete transistors versus an integrated driver array, low-side versus high-side switching, base/gate drive network values, and the commanded-off behaviour of the stage.

The brief fixes the driver class as transistor/MOSFET but not the device, topology or drive network.

*Decision:* **not yet made.**

### OPEN-06 — Whether galvanic isolation (opto or digital isolator) is placed between MCU and driver stage, or whether separation is achieved by spacing alone.

The brief asks for physical separation of switched and logic sides but does not say whether the control path itself must be isolated.

*Decision:* **not yet made.**

### OPEN-07 — Flyback suppression method — plain diode, diode plus series resistor, RC snubber, TVS, bidirectional clamp — and the release-time penalty accepted.

The brief requires "flyback suppression" without specifying the element or the clamp voltage.

*Decision:* **not yet made.**

### OPEN-08 — Switched-side voltage and current rating the board is designed to, including whether it is AC or DC.

The brief hands the voltage rating to the design agent in so many words — it is one "you select and document" — and never mentions the current rating or AC versus DC at all, leaving those open by silence.

*Decision:* **not yet made.**

### OPEN-09 — The basis for the clearance and creepage numbers — which safety standard or spacing table is used, if any, and at what pollution degree, material group, overvoltage category and altitude.

The brief asks for "conservative clearances" but names no standard, prescribes no derivation method and gives no numeric spacing.

*Decision:* **not yet made.**

### OPEN-10 — Separation-barrier construction — clearance alone, a routed slot or milled barrier, solder-mask and silkscreen treatment, conformal coating, or a combination.

The brief requires physical separation but prescribes no mechanism for achieving it.

*Decision:* **not yet made.**

### OPEN-11 — Input protection scheme — which inputs are protected (logic supply, control inputs, switched side), and against what (reverse polarity, overvoltage, ESD, overcurrent/fusing).

The brief requires "input protection" without naming the threat model, the protected nodes or any device.

*Decision:* **not yet made.**

### OPEN-12 — How 5 V logic power arrives at the board and through what kind of entry point, and whether any on-board regulation or additional rails exist.

The brief states the logic rail voltage but not the power-entry arrangement or any regulation.

*Decision:* **not yet made.**

### OPEN-13 — How the relays are commanded in normal operation, and whether the board carries any control path beyond the programming interface — an external control bus, local inputs, or firmware-resident logic only.

The brief names a programming interface and states no host or control interface, so both providing a control path and omitting one are engineering decisions for the design agent to make and document.

*Decision:* **not yet made.**

### OPEN-14 — Status indication form — per-channel indicators versus aggregate, indicator technology, drive method, current, and placement relative to the terminals and the barrier.

The brief requires "status indication" but does not say what is indicated, by what device, or how it is driven.

*Decision:* **not yet made.**

### OPEN-15 — Screw terminal selection — pitch, pole count, current and voltage rating, wire gauge range, wire-entry orientation, and whether contacts are commoned or fully independent per channel.

The brief specifies screw terminals as the load connection but names no part, pitch or rating.

*Decision:* **not yet made.**

### OPEN-16 — Board outline, dimensions, mounting hole pattern, placement of the wiring entry points, and any enclosure or rail-mounting scheme.

The brief states no mechanical envelope, dimensions, mounting method or placement rule beyond keeping the switched side separated from the logic side.

*Decision:* **not yet made.**

### OPEN-17 — Stackup details — layer count, copper weight, base material and its CTI/material group, surface finish, minimum trace/space, and whether two layers actually suffice once the partition is drawn.

Metadata records 2 as the likely layer count, not a fixed requirement, and the brief says nothing about materials or copper weight.

*Decision:* **not yet made.**

### OPEN-18 — Switched-side copper sizing and thermal treatment for the selected contact current, including trace width, clearance-versus-width trade-off, and any thermal relief.

The switched-side current follows from the rating the design agent chooses, which the brief leaves open.

*Decision:* **not yet made.**

### OPEN-19 — Power-up and fault state of the four channels, which state is chosen as the safe one, and whether hardware rather than firmware enforces it at reset and during programming.

The brief is silent on default state, on fail-safe behaviour, and on behaviour while the programming interface is active.

*Decision:* **not yet made.**

### OPEN-20 — Manufacturing and test provisions — through-hole versus surface-mount assembly mix, soldering process implied by relays and terminals, test points, and fixture access across the separation barrier.

The brief states no process or test requirements beyond remaining a consumer of the shared toolkit.

*Decision:* **not yet made.**

## Where a decision gets recorded

1. Answer it under its `OPEN-nn` heading above, with the reasoning and the
   evidence that made the choice.
2. Set `chosen` and `rationale` on the matching entry in
   [requirements.json](requirements.json).
3. Cite the datasheet or standard in [docs/sources.md](../docs/sources.md).

A choice recorded this way stays visibly a choice. That is what lets a later
reader tell this board's engineering apart from its brief.

## Where this board is most likely to be faked

Places where a design run would be tempted to assert something it cannot
substantiate:

- Asserting a switched-side voltage rating as if it were given. The brief hands the rating to the design agent; it must appear as a stated, documented decision together with the clearances it drives, never as an unexamined "assume mains" or "assume 24 V".
- Quoting creepage and clearance numbers with no stated basis behind them — no standard or table, pollution degree, material group or working voltage. Spacing is the single most falsifiable claim on this board and the easiest to fabricate.
- Claiming a separation the layout does not deliver — a barrier drawn only in silkscreen, a "separated" ground that still has one crossing trace, or a mounting hole, thermal relief or via that bridges the partition.
- Dropping in a habitual flyback diode without checking coil current, repetitive peak reverse voltage, clamp voltage or the release-time penalty it imposes on the relay.
- Sizing the driver stage without real coil inrush and steady-state figures from a relay datasheet, and without confirming the MCU pin stays inside its absolute maximum ratings at the rail it actually drives from.
- Inventing screw terminal footprints, pitch or ratings instead of taking them from an actual part, and ignoring wire-entry direction, screwdriver access and board-edge keepout until it is too late to fix.
- Treating the metadata's "2" layers as a hard requirement, or silently going to four layers without stating what in the partition or current-carrying copper forced it.
- Presenting an added interface as something the brief asked for. The brief names a programming interface and nothing else, so any further control path — local inputs, a fieldbus, USB, wireless — is legitimate only as a documented engineering decision, never written up as a user requirement; the converse error is treating the brief's silence as a ban on one.
