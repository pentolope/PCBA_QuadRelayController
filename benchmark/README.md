# Benchmark entry — board 3 of 32

[metadata.json](metadata.json) is the supplied catalogue entry for this board,
preserved byte for byte from the seed pack. It is the same record that appears
in `boards_index.json` in
[PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench), and the two must agree.

| | |
|---|---|
| Repository | `PCBA_QuadRelayController` |
| Board id | `quad_relay_controller` |
| Category | industrial-control |
| Difficulty | 2 / 5 |
| Brief detail | 2 / 5 |
| Likely layer count | 2 |
| Primary stressors | high/low voltage partition, relay flyback, creepage/clearance, terminal placement |

`difficulty` is how hard the board is. `detail` is how much of it the brief
states — and a low `detail` is not a low bar. A detail-1 brief leaves the
architecture open on purpose, and an agent that fills the silence with invented
user requirements has failed the board more thoroughly than one that designs it
badly.

At difficulty 2 and detail 2 in the industrial-control category, this board tests whether an agent can execute a conventionally-shaped circuit while getting the physical discipline right rather than the component novelty. The listed stressors — high/low voltage partition, relay flyback, creepage/clearance, terminal placement — are all layout and rating problems, and the brief deliberately withholds the switched-side voltage rating so the agent must select one, choose clearances that are conservative and appropriate to it, and live with the consequences in the floorplan. The real test is whether the separation barrier and the clearance numbers rest on a stated basis or are merely asserted.

## What goes here

Compact results only: metrics, verdicts, and the commit each was measured at.
The evidence for a result is the artefact the toolkit recomputes, not a summary
of it.

Routing search output, candidate pools, build trees and field-solver dumps do
**not** go here. They are ignored by [.gitignore](../.gitignore) and are
regenerated from what is committed. Thirty-two repositories share one benchmark
clone; weight here is paid thirty-two times.

## Protocol

The attempt protocol is defined once, in the umbrella repository, so that
thirty-two boards cannot drift into thirty-two protocols. See
[PCBA_AutoDesignAndTest_Bench/BENCHMARK.md](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench/blob/main/BENCHMARK.md).
