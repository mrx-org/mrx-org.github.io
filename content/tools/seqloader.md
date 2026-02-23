---
title: Sequence Loader
---

> [!summary]
> Load a sequence from a pulseq .seq file.

> [!info] Work In Progress 🚧
> This tool will be renamed into `trajex` and will have added support for pulseq 1.5.0 and `toolapi::BlockSeq`

### Demo and Tool URL

https://tool-seqloader-flyio.fly.dev/
```url
wss://tool-seqloader-flyio.fly.dev/tool
```

### Inputs

| Input                           | Description                                                                               |
| ------------------------------- | ----------------------------------------------------------------------------------------- |
| `seq_file: String{:rust}`       | Contents of the Pulseq .seq file                                                          |
| `exact_trajectory: bool{:rust}` | Return gradient shape between RF pulses and ADC blocks for accurate diffusion calculation |

### Output

A list of instant events, returned as `toolapi::TypedList::InstantEvent`. This type is ideal for basic simulation but is missing details for off-resonance calculation. It will change in the future.