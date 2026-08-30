# Architecture — Four-Channel Relay Controller

**A worksheet, not a design.** Every line below is a question this board has to
answer, and none of them is answered here. Nothing in this file is a
recommendation, and the order of the sections carries no preference.

The questions were derived from [the brief](../BRIEF.md) and from what this
board is meant to stress in the benchmark:

- high/low voltage partition
- relay flyback
- creepage/clearance
- terminal placement

Those are the places where a wrong answer shows up in copper.

Answer them in this file as the design is made, each answer carrying the
evidence that supports it, and record the corresponding choice against its
`OPEN-nn` entry in [board/requirements.md](../board/requirements.md). An answer
without evidence is a guess wearing a document's clothes — and this benchmark is
allowed to refuse an unsupported claim rather than invent one.

## Switched-side rating and the clearance budget it drives

- What voltage rating is this board designed to, is it AC or DC, and what is the maximum continuous contact current?
- On what basis are creepage and clearance derived — which standard or spacing table, if any, and at what pollution degree, material group and overvoltage category?
- What creepage and clearance numbers result, and what makes them conservative for the selected rating rather than merely adequate?
- If a material group is assumed in that derivation, does the chosen base material's CTI actually support it, and is that confirmed from a fabricator or laminate source?
- Where on the board is the worst-case spacing, and what is the measured value there in the finished layout?
- If the rating were raised one step, which specific feature would fail first?

## High/low voltage partition and the separation barrier

- Where exactly does the barrier run, and is it a straight line the whole way across the board?
- Is the barrier enforced by clearance alone, by a routed slot or milled cutout, or by coating — and what does each contribute?
- Does any copper, plane, thermal relief, mounting hole, fiducial or via cross the barrier on any layer of the stackup?
- Do the relay coil-to-contact spacing and the relay's own datasheet isolation rating meet or exceed the board's barrier?
- Are silkscreen and solder mask treated correctly at the barrier, and is the barrier visible to an assembler and an inspector?
- How is the barrier verified — a DRC rule, a scripted check, or manual measurement — and where is that evidence recorded?

## Relay drive chain from MCU pin to coil

- Is the driver a discrete transistor/MOSFET per channel or an integrated array, and why?
- What is the relay's coil inrush and steady-state current, taken from which datasheet parameter?
- At what voltage do the MCU's I/O pins actually drive the base or gate, and do the pin current and voltage stay inside the MCU's absolute maximum ratings there?
- What state is each driver in during reset, brownout and while the programming interface is active, and what enforces that state?
- What happens to the rail feeding the coils if all four energise simultaneously, and what bulk and local decoupling covers that?
- If the coil rail differs from the 5 V logic rail, how is the level shift handled and what is the sequencing?

## Flyback and switching transient suppression

- Which suppression element is used across each coil, and what is its reverse standoff or repetitive peak reverse voltage relative to the coil rail?
- What clamp voltage results, and what release-time penalty does it impose on the relay?
- Is the suppression element placed physically adjacent to the coil pins so the current loop is small, and how large is that loop?
- What is the peak coil current the element must absorb, and is its surge rating adequate for the expected switching duty?
- Does contact-side arcing or load inductance need separate treatment, and does the chosen rating imply a snubber on the switched side?
- How is the transient path kept off the logic-side ground reference?

## Input protection

- Which nodes count as "inputs" for this board — the 5 V supply entry, any control inputs, the programming interface — and which of them are protected?
- What threats are in scope: reverse polarity, overvoltage, ESD, overcurrent?
- For each protection device, what is the standoff voltage relative to the 5 V rail, and what is the clamping voltage relative to the MCU's absolute maximum rating?
- Is there an overcurrent element, and what does it protect against and at what interrupt rating?
- Do protection elements sit at the point where the protected rail or signal enters the board, before anything they are meant to protect?
- Does adding protection to the programming interface interfere with programming, and has that been checked?

## MCU, logic power and programming interface

- What MCU is chosen, and what specifically makes it a fit for four channels plus indication plus programming?
- Does the MCU run at 5 V directly, or is a lower rail derived — and if derived, from what and with what decoupling?
- Which programming standard is used, how is it physically presented — connector, header or bare pads — and what guards against a reversed or misaligned connection?
- Does the programming interface sit entirely on the logic side, with adequate probe and adapter access clearance from the barrier?
- What is the reset and brownout arrangement, and what channel state does it produce through a power dip?
- Which state do the four channels arrive at on power-up, why that state, and is it enforced in hardware or only in firmware?

## Terminal placement and mechanical layout

- What screw terminal part is chosen, at what pitch, rating and wire gauge range, and from which datasheet?
- Where on the board do the switched-side terminals sit, and which way does the wire enter?
- Is there enough clearance for a screwdriver, for the wire bend radius, and between adjacent terminal blocks at working voltage?
- Where do the switched-side and logic-side wiring entries sit relative to each other and to the barrier, and what keeps field wiring from being run across the partition?
- What is the board outline, and where do mounting holes sit relative to the barrier and to switched-side copper?
- Do the relays, terminals and any barrier slot leave a routable logic-side region for the MCU and its support parts?

## Status indication

- What does the indication actually indicate — coil energised, commanded state, contact state, power present, fault?
- Is indication per-channel, aggregate, or both, and what does an operator infer from it?
- What indicator technology is used, how is it driven, and does the resulting current fit the rail and driver budget already committed?
- Are indicators placed so they are readable in the intended mounting orientation, and is each one legibly labelled?
- Which side of the barrier does each indicator and its drive circuitry sit on, and what does that placement cost in clearance and creepage terms?

## Stackup, routing and current-carrying copper

- Do two layers actually suffice once the barrier, the terminals and the coil returns are placed — and if not, what specifically forced more?
- What copper weight is chosen, and what switched-side trace width does the selected contact current require at what temperature rise?
- Is there tension between the trace width the current needs and the clearance the rating needs, and how is it resolved?
- How are logic-side and switched-side returns arranged so coil and contact currents do not share the MCU's reference?
- What minimum trace/space, drill and slot capability does the chosen fabricator support at this layer count?
- Where do the highest-di/dt loops run, and are they contained away from the MCU and the programming interface?

## Verification, test and toolkit integration

- How are the barrier and clearance rules confirmed in the finished layout, and which of those checks are automated rather than visual?
- What test points exist for bring-up, and are any of them on the switched side — if so, how is safe fixture access handled?
- How is each channel exercised end to end during test, and what is the pass criterion?
- What in this repository is board-specific configuration versus something that would belong in the shared toolkit?
- Which claims in the design documentation are backed by a cited datasheet page or standard clause, and which are still assertions?

## Answers still owed

All of them. See [status.md](status.md).
