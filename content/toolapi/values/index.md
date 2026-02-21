# Value types

USI needs to exchange data between the [Host](../tool_host.md#host) and the [Tool](../tool_host.md#tool).
Namely, upon calling the tool, the host will send a bunch of inputs.
After finishing, the tool will return an output.
To facilitate the unification of USI tools, this exchange is done via a canonical list of types, which carry a semantic meaning.


| Name | Description | Example |
| ---- | ----------- | ------- |
| [`Bool`](#bool) | Can be true or false. | `use_gpu=true` |
| [`Int`](#int) | 64bit signed integer. Ranges from \\(-2^{63}\\) to \\(2^{63} - 1\\). | `spin_count=1000` |
| [`Float`](#float) | Double-precision (64 bit) IEEE 754 floating point value. | `latent_signal_threshold=0.1` |
| [`Complex`](#complex) | Encoded as real and imaginary `Float` | _Currently not exposed_ |
| [`Signal`](#signal) | List of per-coil lists of `Complex` ADC samples. | See [Signal](#signal) |
| [`Encoding`](#encoding) | Encoding of ADC samples, stored as 4 `Float`s. | See [Encoding](#encoding) |
| [`VoxelPhantom`](#voxelPhantom) | Flattened list of voxels + positions | See [VoxelPhantom](#voxelphantom) |
| [`VoxelGridPhantom`](#voxelgridphantom) | Cartesian 3D grid of voxels | See [VoxelGridPhantom](#voxelgridphantom) |
| [`DiscreteEventSeq`](#discreteeventseq) | Sequence of instantaneous events | See [DiscreteEventSeq](#discreteeventseq) |
| [`ContinuousBlockSeq`](#continuousblockseq) | Pulseq-like sequence of blocks | See [ContinuousBlockSeq](#continuousblockseq) |


## Bool

## Int

## Float

## Complex

---

## Signal

List of per-coil signals.
For every coil: List of complex ADC sample values.
Each complex value consists of two [Float](#float)'s (real and imaginary value).

Example: a measurement of a 64x64 sequence on a 8-channel system will return a list of 8 lists, each of which contains 4096 complex values.
A single-coil mesurement would return a list containing one element: a list with 4096 samples.


## Encoding

List of `[x, y, z, t]` elements: 4 [Float](#float)'s per ADC sample that store their kt - encoding.

`xyz` represents the \\(\vec{k}\\) dephasing of the measured samples (unit: \\(1 / m\\)). \
`t` is the \\(\tau\\) dephasing: effect of \\(B_0\\) inhomogeneities and \\(T'_2\\) (unit: \\(s\\)).


---

## Phantom

Phantoms consists of many voxels, each of which describe the physical properties of the spatial location they sample.
The shape of these voxels are described by their [VoxelShape](#voxelshape).
Their location is specified differently for the [VoxelPhantom](#voxelphantom) and the [VoxelGridPhantom](#voxelgridphantom).

Each sample gives the following values:

| Property | Description |
| -------- | ----------- |
| `pd` | Proton density \\([a.u.]\\) |
| `t1` | \\(T_1\\) relaxation time \\([s]\\) |
| `t2` | \\(T_2\\) relaxation time \\([s]\\) |
| `t2dash` | \\(T_2'\\) dephasing time \\([s]\\) |
| `adc` | Apparent diffusion coefficient \\([10^{-3} mm^2 / s]\\) |
| `b0` | \\(B_0\\) off-resonance frequency \\([Hz]\\) |
| `b1` | Relative \\(B_1\\) field strength |
| `coil_sens` | Coil sensitivity \\([a.u.]\\) |


## TissueProperties

Structure containing basic signal types, used by the [kspace extract tool](/src/tools/kspace_extract.md).
Contains four [Floats](/src/toolapi/values/index.md#float):

| Property | Description |
| -------- | ----------- |
| `t1` | \\(T_1\\) relaxation time \\([s]\\) |
| `t2` | \\(T_2\\) relaxation time \\([s]\\) |
| `t2dash` | \\(T_2'\\) dephasing time \\([s]\\) |
| `pd` | Proton density \\([a.u.]\\) |


### VoxelShape
Most phantoms consist of many voxels with identical shapes. Currently, the supported shapes are:
- `AASinc(size)`: An axis-aligned sinc shape where the first zero crossing is given by `size=[sx, sy, sz]`.
- `AABox(size)`: An axis-aligned box of size `size=[sx, sy, sz]`.


### VoxelPhantom

The voxel phantom is the simplest version of phantoms:
It is specified by a list of values for each [Phantom](#phantom) property, combined with a single `voxel_shape` property that is applied to all voxels, as well a list of voxel positions.
This `pos` list contains three `Float`s per voxel. All lists have the same length.
For partial volume effects, multiple voxels can coexist at the same position.

This value type makes the implementation of simulation tools very easy which operate on each voxel individually.


### VoxelGridPhantom

Phantoms are usually defined as cartesian grids of voxels.
This makes reslicing, interpolation or truncating of the phantom easy, as well as FFT transformations.

The voxel grid phantom doesn't store a list of voxel positions (`pos`), but instead has a `grid_spacing` property, which consists of three `Float`s that define the cell size in the cartesian grid.
Combined with the `grid_size` property, which is tree integers that define the resolution of the grid, the mapping of the flattened arrays of physical properties and the 3D - matrix of voxels is defined.

This phantom type is otherwise identical to the [VoxelPhantom](#voxelphantom) and has a function to convert to it.


---

## DiscreteEventSeq

This sequence type consists of a chronological list of events, which are applied sequentially and never simultaneously.
There are three event types:
- `Pulse { angle, float }`: An instantaneous RF pulse
- `Fid { kt }`: Free induction decay, which will apply relaxation and decay as given by `kt=[kx, ky, kz, t]`
- `Sample { phase }`: An ADC sample which captures the current signal while applying a roatation

This sequence type is optimized to be used by simulations which do not care about the pulse shape or exact gradient trajectory, but rather gradient moments and timings of samples / pulse centers.


## ContinuousBlockSeq

This sequence type is modelled after Pulseq, consisting of a sequence of blocks, each of which can contain multiple events which are applied in parallel.
The blocks each contain (optional) values for `min_duration`, `rf`, `gx`, `gy`, `gz` and `adc`.

This sequence type can be used for very accurate simulations, that incorporate pulse shapes, slice selection and more, as well as tools for SAR calculation and more.
Otherwise it mainly exists to construct sequences with pulseq, using it as backing data type.
It can be converted to a [DiscreteEventSeq](#discreteeventseq), as provided by `MRX: ToolAPI`.

### Pulse

Pulses are defined by their timing: `delay`, `duration` and `ringdown`, \
as well as their signal: `flip_angle`, `phase_offset` and `frequency_offset`. \
In addition, pulses have a shape, where the following exist:
- Block: no additional parameters
- Sinc: given by a `time_bandwidth_product` and `apoditzaiton` value