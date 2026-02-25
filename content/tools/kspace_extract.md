> [!info] Work In Progress 🚧
> This tool will be renamed into `trajex` and will get extended support for $T_1$ / $T_2$ weighting analysis, non-ADC trajectory samples, multi-state trajectories...

# k-Space extraction

```bash
kspace_extract.exe
```

A tool for extracting the k-space from a sequence.
Internally uses a PDG simulation based on the provided tissue properties.
Together with a rough, exponential signal fall-off estimation, the simulation determines the strongest state for every ADC sample.
The dephasing of this state is returned as the encoding of the sample.

| Input | Type |
| ----- | ---- |
| `sequence` | [DiscreteEventSeq](../toolapi/values/index.md#discreteeventseq) |
| `tissue` | [TissueProperties](../toolapi/values/index.md#tissueproperties) |
| `min_mag` | [Float](../toolapi/values/index.md#float) |

The returned output is the [Encoding](/src/toolapi/values/index.md#encoding) of the sequence.
