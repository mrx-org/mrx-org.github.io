# MR-zero PDG simulation

```bash
python mr0sim/main.py
```

Exposes the MR0 PDG simulation as a python script that is `MRX: ToolAPI` compatible.

| Input | Type |
| ----- | ---- |
| min_state_mag | [Float](../toolapi/values/index.md#float) |
| max-state_count | [Int](../toolapi/values/index.md#int) |
| min_latent_signal | [Float](../toolapi/values/index.md#float) |
| min_emitted_signal | [Float](../toolapi/values/index.md#float) |
| `use_gpu` | [Bool](../toolapi/values/index.md#bool) |
| `phantom` | [VoxelPhantom](../toolapi/values/index.md#voxelphantom) |
| `sequence` | [DiscreteEventSeq](../toolapi/values/index.md#discreteeventseq) |

If the `use_gpu` parameter is set, the simulation will use [CUDA](https://de.wikipedia.org/wiki/CUDA) to run on the GPU selected by [PyTorch](https://pytorch.org/).
This might crash if the current hardware does not support CUDA (e.g.: no compatible NVIDIA graphics card was detected).

Returns the measured [Signal](../toolapi/values/index.md#signal).