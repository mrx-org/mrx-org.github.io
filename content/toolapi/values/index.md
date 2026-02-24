---
title: Value Types
tags:
  - toolapi
  - values
---

The [[toolapi/index|ToolAPI]] exchanges data between clients and tools using a canonical set of typed values. Upon calling a tool, the client sends a `Value` as input; when finished, the tool returns a `Value` as output.

The type system is intentionally limited to a small, well-defined set. This promotes interoperability: tools with similar purposes can be exchanged freely, because they all speak the same types. Structured types exist to give values that could be expressed with `Dict`s and `List`s a known structure and semantic meaning that tools and clients can rely on.

> [!info] Design principle
> The number of structured types is kept low to maximize reusability. For niche applications, it is preferred that tool and client agree on a structure using dynamic types (`Dict`, `List`) rather than extending the ToolAPI with new structured types.

## Overview

| Category       | Type                                    | Description                                           |
| -------------- | --------------------------------------- | ----------------------------------------------------- |
| **Atomic**     | [`None`](#none)                         | Absence of a value                                    |
|                | [`Bool`](#bool)                         | `true` or `false`                                     |
|                | [`Int`](#int)                           | 64-bit signed integer                                 |
|                | [`Float`](#float)                       | 64-bit IEEE 754 double                                |
|                | [`Str`](#str)                           | UTF-8 string                                          |
|                | [`Complex`](#complex)                   | Complex number (real + imaginary `Float`)             |
|                | [`Vec3`](#vec3)                         | 3-element float vector `[f64; 3]`                     |
|                | [`Vec4`](#vec4)                         | 4-element float vector `[f64; 4]`                     |
| **Structured** | [`InstantSeqEvent`](#instantseqevent)   | Instantaneous MRI sequence event (Pulse, Fid, or Adc) |
|                | [`Volume`](#volume)                     | 3D voxel grid with affine transform                   |
|                | [`SegmentedPhantom`](#segmentedphantom) | Multi-tissue MRI phantom                              |
|                | [`PhantomTissue`](#phantomtissue)       | Single tissue with relaxation parameters              |
| **Dynamic**    | [`Dict`](#dict)                         | String-keyed map of heterogeneous values              |
|                | [`List`](#list)                         | Ordered sequence of heterogeneous values              |
| **Typed**      | [`TypedList`](#typedlist)               | Homogeneous list (one variant per value type)         |
|                | [`TypedDict`](#typeddict)               | Homogeneous dict (one variant per value type)         |

---

## Atomic Types

### None

Absence of a value. Maps to `None` in Python, `null` in JavaScript.

### Bool

Boolean value: `true` or `false`.

### Int

64-bit signed integer. Ranges from \\(-2^{63}\\) to \\(2^{63} - 1\\).

### Float

Double-precision (64-bit) IEEE 754 floating point value.

### Str

UTF-8 encoded string.

### Complex

Complex number, encoded as two `Float`s (real and imaginary part). Uses `num_complex::Complex64` in Rust, `complex` in Python, and `{ re, im }` in JavaScript.

### Vec3

A 3-element float vector: `[f64; 3]`. Used for spatial positions, FOV sizes, and similar 3D quantities.

### Vec4

A 4-element float vector: `[f64; 4]`. Used for k-space encoding `[kx, ky, kz, t]` and similar quantities.

---

## Structured Types

These types carry MRI-specific semantic meaning. They have a fixed structure that tools and clients can rely on.

### InstantSeqEvent

An instantaneous MRI sequence event. This is a tagged union with three variants:

| Variant | Fields                         | Description                                          |
| ------- | ------------------------------ | ---------------------------------------------------- |
| `Pulse` | `angle: Float`, `phase: Float` | An instantaneous RF pulse                            |
| `Fid`   | `kt: Vec4`                     | Free induction decay with encoding `[kx, ky, kz, t]` |
| `Adc`   | `phase: Float`                 | An ADC sample capturing the current signal           |

This type is used for discrete-event sequence representations, optimized for simulations that operate on gradient moments and timing rather than continuous pulse shapes.

### Volume

A 3D voxel grid with an affine transform describing its position and orientation in physical space.

| Field    | Type            | Description                                                             |
| -------- | --------------- | ----------------------------------------------------------------------- |
| `shape`  | `[u64; 3]`      | Number of voxels in each dimension                                      |
| `affine` | `[[f64; 4]; 3]` | 3x4 affine matrix mapping voxel indices to physical coordinates         |
| `data`   | `TypedList`     | Flattened voxel data (type depends on content, e.g. `Float`, `Complex`) |

The `data` field uses a `TypedList` for efficient, homogeneous storage. The element type depends on the context -- a density map might use `Float`, while a coil sensitivity map might use `Complex`.

### SegmentedPhantom

A multi-tissue segmented MRI phantom. Unlike classical voxel phantoms where each voxel has independent tissue parameters, a segmented phantom groups voxels by tissue type.

| Field     | Type                             | Description                                             |
| --------- | -------------------------------- | ------------------------------------------------------- |
| `tissues` | `HashMap<String, PhantomTissue>` | Named tissues (e.g. `"white_matter"`, `"gray_matter"`)  |
| `b1_tx`   | `Vec<Volume>`                    | B1 transmit sensitivity maps (one per transmit channel) |
| `b1_rx`   | `Vec<Volume>`                    | B1 receive sensitivity maps (one per receive coil)      |

### PhantomTissue

A single tissue within a `SegmentedPhantom`, containing spatially-varying maps and scalar relaxation parameters.

| Field     | Type     | Description                                             |
| --------- | -------- | ------------------------------------------------------- |
| `density` | `Volume` | Proton density map \\([a.u.]\\)                         |
| `db0`     | `Volume` | \\(\Delta B_0\\) off-resonance map \\([Hz]\\)           |
| `t1`      | `Float`  | \\(T_1\\) relaxation time \\([s]\\)                     |
| `t2`      | `Float`  | \\(T_2\\) relaxation time \\([s]\\)                     |
| `t2dash`  | `Float`  | \\(T_2'\\) dephasing time \\([s]\\)                     |
| `adc`     | `Float`  | Apparent diffusion coefficient \\([10^{-3}\\ mm^2/s]\\) |

---

## Dynamic Collections

### Dict

A string-keyed map where each value can be a different `Value` type. This is the standard way to pass named parameters to tools and return named results.

```
Dict { "flip_angle": Float(0.26), "resolution": List([Int(128), Int(128), Int(1)]) }
```

### List

An ordered sequence where each element can be a different `Value` type.

```
List [Float(1.0), Int(42), Str("hello")]
```

---

## Typed Collections

For performance, homogeneous collections are stored as `TypedList` and `TypedDict` instead of `List` and `Dict`. They avoid the overhead of wrapping every element in a `Value` enum.

### TypedList

A homogeneous list with one variant per value type. For example, `TypedList::Float(Vec<f64>)` stores a list of floats without per-element tagging.

In Python and JavaScript, typed lists are represented as regular `list` / `Array` -- the type is inferred automatically from the element types during serialization.

### TypedDict

A homogeneous string-keyed map, analogous to `TypedList`. For example, `TypedDict::Int(HashMap<String, i64>)`.

---

## Extracting Values

Values can be indexed using a path-based syntax. The `Value::get(pointer)` method (Rust) accepts a `/`-separated path to navigate nested structures:

```rust
// Extract from nested Dict / List
let val = input.get("tissues/white_matter/t1")?;
let val = input.get("events/0/angle")?;

// Convert to a concrete Rust type
let t1: f64 = input.get("tissues/white_matter/t1")?.try_into()?;
```

Path segments that parse as integers index into `List` / `TypedList`; string segments index into `Dict` / `TypedDict`.

See also: [[toolapi/implementations|Implementations]] for language-specific value handling.
