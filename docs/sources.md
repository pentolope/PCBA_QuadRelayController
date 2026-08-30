# Sources — Four-Channel Relay Controller

The evidence this board's design will have to cite. **Classes of document, not
documents:** the specific parts are not chosen yet, so naming a datasheet here
would be choosing one.

A number that reaches the board carries its provenance: source, document id or
URL, retrieval date, units, and the condition it applies under. A number without
that is not evidence, and no live network lookup may change a validation or
release result.

| Kind of source | What the design needs from it |
|---|---|
| Relay datasheet | Coil voltage and current, inrush, operate/release times, contact form, contact rating and material, and coil-to-contact dielectric strength — the numbers every other decision on this board depends on. |
| Safety spacing standard or creepage/clearance table for the derivation basis chosen | The brief demands conservative clearances for a self-selected voltage rating but names no standard, so whatever basis is used has to be identified — table, pollution degree, material group, overvoltage category — for the spacing to be checkable rather than merely asserted. |
| Driver device datasheet (transistor, MOSFET or driver array) | Saturation voltage or Rds(on), base/gate drive requirements, safe operating area, thermal limits, and whether an internal clamp diode is already present. |
| Flyback/clamp element datasheet (diode, TVS or snubber components) | Repetitive peak reverse voltage or standoff, forward and surge current, recovery behaviour and thermal rating against the coil's actual stored energy. |
| MCU datasheet | I/O source/sink current, absolute maximum ratings at whatever rail the MCU actually runs from, reset and brownout behaviour, package, and the pins and electrical conditions the programming interface requires. |
| Screw terminal block datasheet | Rated voltage and current, wire gauge range, pitch, torque, footprint and safety approvals — a footprint invented rather than sourced is a common failure here. |
| Protection device datasheets (TVS/ESD, reverse-polarity element, fuse or PTC) | Standoff and clamping voltage against the 5 V rail and MCU maxima, peak pulse current, hold/trip current and interrupt rating. |
| PCB fabricator capability page for the chosen layer count | Minimum trace and space, drill and slot capability for any barrier cutout, copper weights, mask web minimums, and whether the required clearances are even manufacturable as drawn. |
| Laminate/base material data | Comparative tracking index and temperature rating, which determine the material group if the creepage derivation depends on one. |
| Trace-width/temperature-rise sizing reference | Switched-side copper must carry the selected contact current; the width has to come from a stated sizing basis, not a guess. |
| Indicator device datasheet for the indication technology chosen | Forward voltage or operating current at the rail the indicator is driven from, so the limiting or drive element can be sized and the rail and driver current budget confirmed. |
| Shared PCBA_AutoDesignAndTest toolkit documentation | Expected repository layout, configuration schema and the checks a board repo must satisfy as a consumer without pushing board-specific logic into the toolkit. |

## Recording a source, once one is chosen

Replace the class with the actual document — manufacturer, part number, revision
and date — and state the fact taken from it, in the units the document uses.
Keep the class row: it says why the document was needed.

JLCPCB-wide process limits are **not** recorded here. They live in the toolkit's
`profiles/jlcpcb/`, with their own provenance; this board records only its own
tighter targets and its own selected options. A limit copied into two places is
a rival threshold, and the toolkit has a gate that says so.
