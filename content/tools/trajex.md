---
title: Trajectory Extractor
---

> [!summary]
> Automatic k-space trajectory extraction of arbitrary MRI sequences. Works by accurately determining the encoding of the generated signal.

> [!info] Work In Progress 🚧
> This tool will get extended support for $T_1$ / $T_2$ weighting analysis, non-ADC trajectory samples, multi-state trajectories.

### Demo and Tool URL

https://tool-trajex.fly.dev/

```url
wss://tool-trajex.fly.dev/tool
```

### Inputs

| Input                            | Description                                                                                                |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `sequence: Vec<InstantSeqEvent>` | List of instantaneous sequence events, typically produced by [conseq](conseq.md)                           |
| `t1: f64{:rust}`                 | Longitudinal relaxation time $T_1$ in seconds                                                              |
| `t2: f64{:rust}`                 | Transverse relaxation time $T_2$ in seconds                                                                |
| `min_mag: f64{:rust}`            | Minimum magnetization magnitude threshold; states below this are pruned to control complexity vs. accuracy |

### Output

A list of 4D k-space positions, returned as `toolapi::TypedList::Vec4`. Each entry is `[k_x, k_y, k_z, tau]` corresponding to the dominant magnetization pathway at each ADC readout.
