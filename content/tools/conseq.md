---
title: Sequence Converter
---

> [!summary]
> Load a sequence from a pulseq .seq file.

> [!info] Work In Progress 🚧
> This tool currently can only convert .seq file contents into `List[InstantSeqEvent]`. In the future it will be extended to support newer pulseq standards, other formats, emitting `List[SeqBlock]`.

### Demo and Tool URL

https://tool-conseq.fly.dev/
```url
wss://tool-conseq.fly.dev/tool
```

### Inputs

| Input                           | Description                                                                               |
| ------------------------------- | ----------------------------------------------------------------------------------------- |
| `seq_file: String{:rust}`       | Contents of the Pulseq .seq file                                                          |
| `exact_trajectory: bool{:rust}` | Return gradient shape between RF pulses and ADC blocks for accurate diffusion calculation |

### Output

A list of instant events, returned as `toolapi::TypedList::InstantEvent`. This type is ideal for basic simulation but is missing details for off-resonance calculation. It will change in the future.