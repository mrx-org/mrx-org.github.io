---
title: sPDG Simulation
---

> [!summary]
> State-of-the art MRI simulation, subject to continuous improvement.

### Demo and Tool URL
https://tool-spdg-flyio.fly.dev/ 
```url
wss://tool-spdg-flyio.dev/tool
```

### Inputs

| Input                             | Description                 |
| --------------------------------- | --------------------------- |
| `sequence: List[InstantSeqEvent]` | MRI sequence for simulation |
| `phantom: SegmentedPhantom`       | Phantom data for simulation |

### Output

A `toolapi::SegmentedPhantom` containing gray matter, white matter, csf, fat and vessels.