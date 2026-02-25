---
title: Phantom Library
---

> [!summary]
> Load one of the BrainWeb phantoms: any FOV (arbitrary rotation) at any resolution.

> [!info] Work In Progress 🚧
> The name of this tool might still change. Still missing: returning combined phantoms, support for non-BrainWeb data, more (and maybe freely selectable) field strengths, better reslicing.

### Demo and Tool URL
https://tool-phantomlib-flyio.fly.dev/ 
```url
wss://tool-phantomlib-flyio.dev/tool
```

### Inputs

| Input                     | Description                                                            |
| ------------------------- | ---------------------------------------------------------------------- |
| `res_x: i64`              | Resolution, x-axis, `1..=512`                                          |
| `res_y: i64`              | Resolution, y-axis, `1..=512`                                          |
| `res_z: i64`              | Resolution, z-axis, `1..=512`                                          |
| `affine: List[List[f64]]` | 3x4 affine matrix (3 rows with 4 items each)                           |
| `subject: i64`            | One of the [BrainWeb](https://brainweb.bic.mni.mcgill.ca/) subject IDs |

### Output

A `toolapi::SegmentedPhantom` containing gray matter, white matter, csf, fat and vessels.

---

The phantom library currently contains the [BrainWeb: 20 Anatomical Models of 20 Normal Brains](https://brainweb.bic.mni.mcgill.ca/anatomic_normal_20.html), which means the following subject IDs are available:
```rust
const SUBJECT_IDS: &[i64] = &[
    4, 5, 6, 18, 20, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54,
];
```