---
title: Spin Simulation
---

> [!summary]
> Simplistic Isochromat simulation with focus on correctnes, not speed

### Demo and Tool URL

https://tool-spinsim.fly.dev/

```url
wss://tool-spinsim.fly.dev/tool
```

### Inputs

| Input                             | Description                           |
| --------------------------------- | ------------------------------------- |
| `sequence: List[InstantSeqEvent]` | MRI sequence for simulation           |
| `phantom: SegmentedPhantom`       | Phantom data for simulation           |
| `spins_per_voxel: Int`            | Isochromats (spins) per phantom voxel |

### Output

A `List[Complex]` containing the simulated signal.
