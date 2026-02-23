
> [!warning] Outdated
> This tool existed in [mrx-org/mrx](https://github.com/mrx-org/mrx) but is not ported to the current iteration of tools. If that is done, this documentation needs to be updated.
# Basic Bloch simulation

```bash
basic_bloch_sim.exe
```

Very simple, isochromat-based simulation written in Rust.
This tool is purposely simple, trying to provide a ground truth implementation of a Bloch simulation and an example for a `MRX: ToolAPI` tool.

The simulation currently has the following limitations:
- no GPU support
- box voxels: voxel shape of phantom is ignored, leads to aliasing in combination with gradient spoiling, high spin count needed
- not differentiable
- only single-coil acquisition is supported

| Input | Type |
| ----- | ---- |
| `sequence` | [DiscreteEventSeq](../toolapi/values/index.md#discreteeventseq) |
| `phantom` | [VoxelPhantom](../toolapi/values/index.md#voxelphantom) |
| `spins_per_voxel` | [Int](../toolapi/values/index.md#int) |
| `multithreaded` | [Bool](../toolapi/values/index.md#bool) |

If the `multithreaded` parameter is set, the phantom is split into _N_ parts with identical number of spins where _N_ is the number of _logical_ processors on the system.

Returns the measured **single-coil** [Signal](../toolapi/values/index.md#signal).