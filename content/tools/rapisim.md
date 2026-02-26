---
title: Rapid MRI Simulation
---

> [!summary]
> State-of-the art MRI simulation, subject to continuous improvement.

### Demo and Tool URL

https://tool-rapisim.fly.dev/

```url
wss://tool-rapisim.fly.dev/tool
```

### Inputs

| Input                             | Description                 |
| --------------------------------- | --------------------------- |
| `sequence: List[InstantSeqEvent]` | MRI sequence for simulation |
| `phantom: SegmentedPhantom`       | Phantom data for simulation |

### Output

A `List[Complex]` containing the simulated signal.
