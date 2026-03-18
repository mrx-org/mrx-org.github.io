---
title: Repository overview
---

This page is a list of all repositories that were created to achieve the goals of MRX.
It is meant as an overview and to keep track of our efforts so far.
All repositories are hosted in the [mrx-org](https://github.com/mrx-org/) GitHub organization.

---

# ToolAPI

Language implementations of the [MRX ToolAPI](toolapi/index).

| Repo | Description |
| ---- | ----------- |
| [`toolapi`](https://github.com/mrx-org/toolapi) | Rust implementation, published on [crates.io](https://crates.io/crates/toolapi) |
| [`toolapi-py`](https://github.com/mrx-org/toolapi-py) | Python implementation, published on [PyPI](https://pypi.org/project/toolapi/) |
| [`toolapi-wasm`](https://github.com/mrx-org/toolapi-wasm) | JS (WASM) implementation, published on [npmjs](https://www.npmjs.com/package/toolapi-wasm) |

# Organization

MRX organization repositories for documentation and project management.

| Repo                                                                | Description                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`mrx-org.github.io`](https://github.com/mrx-org/mrx-org.github.io) | **[MRX Website](https://mrx-org.github.io/)**: The website you are currently on. Contains examples and documentation, tracks the current progress and captures the goals of MRX.                                                                       |
| [`nofield`](https://github.com/mrx-org/nofield)                     | **[No-field Scanner](https://mrx-org.github.io/nofield/)**: Virtual scanner interface with parameter configuration, FOV selection and simulated measurement of MRI sequences defined by [pypulseq](https://github.com/imr-framework/pypulseq) scripts. |
| [`mrx-board`](https://github.com/mrx-org/mrx-board)                 | Organization management (private)                                                                                                                                                                                                                      |

# Tools

Building blocks for MRX apps. These tools are built using the [MRX ToolAPI](toolapi/index) and provide different functionalities, which have to be connected by apps or scripts.

| Repo | Description |
| ---- | ----------- |
| [`tool_phantomlib_flyio`](https://github.com/mrx-org/tool_phantomlib_flyio) | **[Phantom Library](https://tool-phantomlib-flyio.fly.dev/)**: Retrieve a segmented BrainWeb phantom at any resolution and FOV. |
| [`tool-conseq`](https://github.com/mrx-org/tool-conseq) | **[Sequence Loader](https://tool-conseq.fly.dev/)**: Load a Pulseq .seq file into a ToolAPI sequence. |
| [`tool-trajex`](https://github.com/mrx-org/tool-trajex) | **[Trajectory Extractor](https://tool-trajex.fly.dev/)**: Highly accurate k-space trajectory (encoding) extractor using a PDG simulation. |
| [`tool-rapisim`](https://github.com/mrx-org/tool-rapisim) | **[Simulation](https://tool-rapisim.fly.dev/)**: Fastest, state-of-the-art MRI simulation. |
| [`tool-mr0sim`](https://github.com/mrx-org/tool-mr0sim) | **[Simulation MR-zero](https://tool-mr0sim.fly.dev/)**: MRI simulation using the Python MR-zero PDG simulator. |
| [`tool-spinsim`](https://github.com/mrx-org/tool-spinsim) | **[Isochromat Simulation](https://tool-spinsim.fly.dev/)**: Simple isochromat-based MRI simulation. |

# Outdated

There is one outdated repository: [mrx-org/mrx](https://github.com/mrx-org/mrx). This was a monorepo for the first iteration. It contains an outdated version / prototype of the toolapi, as well as a couple of tools. Some of them should be extracted into their own tool repos:

- [x] `tool_basic_bloch_sim`: A purposefully simple isochromat simulation, useful a ground-truth
- [x] `tool_kspace_extract`: Automatic k-space trajectory extraction, to be replaced with new `trajex` tool
- [x] `tool_mr0sim`: Provides MR-zero PDG simulation as MRX tool (first toolapi-py server impl)
- [ ] `tool_pulseq_loader`: Converts pulseq into ToolAPI block seq - which is not yet provided in current ToolAPI
- [x] `tool_spdg`: State-of-the-art simulation (should be renamed)
