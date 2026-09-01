# PCBA_QuadRelayController — Four-Channel Relay Controller
## Design brief

Design a four-channel relay controller operated by a small MCU. Logic power is 5 V; each relay switches an external load through screw terminals. Include input protection, transistor/MOSFET relay drivers, flyback suppression, status indication, and a programming interface. Keep the switched side physically separated from the logic side and choose conservative clearances appropriate to the voltage rating you select and document.

## Functional requirements

- The four channels shall be independently commandable; changing one shall not disturb the others.
- All coils shall be de-energised at power-on, in MCU reset, while a programmer holds reset, and on loss of logic power.
- Status indication shall show each channel's commanded state, driven from the logic side only.

## Power and rails

- The board shall run from an external 5 V logic input; any further rail shall be derived on-board or given its own documented input.
- With all coils energising at once at worst-case supply tolerance, the logic rail shall stay inside the MCU's operating range and above brown-out.
- The 5 V input shall tolerate reverse polarity, and every logic-side conductor entering the board shall withstand ESD and hot connection.

## Relay drive and flyback suppression

- Each coil shall be driven by a transistor or MOSFET stage fully on at the drive level the chosen MCU guarantees, with dissipation and total pin current within ratings when all four channels are on at maximum ambient.
- Each driver input shall be resistively held de-energised whenever the MCU pin is high-impedance or unprogrammed.
- Each coil shall have its own flyback device in a small turn-off loop, rated for the coil current and clamping below the driver's breakdown voltage.

## Connectors and programming interface

- Switched circuits shall reach the outside world only through the screw terminals, which shall be rated at or above the documented switched voltage and current.
- Terminals shall take load wiring away from the logic side and be identified on the silkscreen by channel and contact function.
- The programming interface shall program the chosen MCU in circuit on an assembled board, with no part removed, from the logic side of the boundary.

## Separation, clearance and markings

- The switched/logic boundary shall be continuous on every layer; nothing conductive shall cross it but the relay contact pins and their terminals.
- Clearance and creepage across the boundary, and between switched-side conductors, shall meet the figure derived from the documented rating; solder mask shall not count toward it.
- That rating, the standard used to derive the clearance and the resulting minimum dimension shall be documented, and the per-channel maximum voltage and current marked on the board.

## Test and bring-up

- Each channel shall be exercisable individually with no load fitted, with contact transfer verifiable at the terminals.
- Logic-side test access shall expose the 5 V rail, ground, the coil supply, and each driver input and coil node.

## Open choices

- MCU: any part with enough I/O for the drivers, the indication and the programming interface, a defined reset state, and adequate guaranteed drive.
- Relay coil voltage and contact configuration, whether coils share the 5 V logic rail or take a separate supply, and the switched-side rating the clearances depend on.
- Where channel commands originate — firmware, local inputs, or a host interface — and whether that interface is isolated.
