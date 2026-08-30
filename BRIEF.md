# PCBA_QuadRelayController — Four-Channel Relay Controller

**Benchmark ID:** 03  
**Difficulty:** 2/5  
**Brief detail:** 2/5  
**Category:** industrial-control  
**Likely layer count:** 2  
**Primary stressors:** high/low voltage partition, relay flyback, creepage/clearance, terminal placement

## Design brief

Design a four-channel relay controller operated by a small MCU. Logic power is 5 V; each relay switches an external load through screw terminals. Include input protection, transistor/MOSFET relay drivers, flyback suppression, status indication, and a programming interface. Keep the switched side physically separated from the logic side and choose conservative clearances appropriate to the voltage rating you select and document.

## Benchmark intent

This brief is intentionally one member of a heterogeneous PCBA-autodesign benchmark. Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements. The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.
