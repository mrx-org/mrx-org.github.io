---
title: MR-zero Simulation
---

> [!summary]
> Exposes the tried and tested PDG simulation of MR-zero as MRX tool.

### Demo and Tool URL

https://tool-mr0sim.fly.dev/

```url
wss://tool-mr0sim.fly.dev/tool
```

### Inputs

| Input                             | Description                 |
| --------------------------------- | --------------------------- |
| `sequence: List[InstantSeqEvent]` | MRI sequence for simulation |
| `phantom: SegmentedPhantom`       | Phantom data for simulation |


### Output

A `List[Complex]` containing the simulated signal.
