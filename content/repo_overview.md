---
title: Repository overview
---

This page is a list of all repositories that were created to achieve the goals of MRX.
It is meant as an overview and to keep track of our efforts so far.
All repositories are hosted in the [mrx-org](https://github.com/mrx-org/) GitHub organization.

---

# ToolAPI

Language implementations of the [MRX ToolAPI](toolapi/index).

| Project                                                                                                                                                                                                        | Description                                    |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| [![github](https://badgen.net/badge/icon/toolapi?icon=github&label)](https://github.com/mrx-org/toolapi) [![crates.io](https://badgen.net/crates/v/toolapi)](https://crates.io/crates/toolapi)                 | Rust implementation: `cargo add toolapi`       |
| [![github](https://badgen.net/badge/icon/toolapi-py?icon=github&label)](https://github.com/mrx-org/toolapi-py) [![pypi](https://badgen.net/pypi/v/toolapi)](https://pypi.org/project/toolapi/)                 | Python wrapper: `pip install toolapi`          |
| [![github](https://badgen.net/badge/icon/toolapi-wasm?icon=github&label)](https://github.com/mrx-org/toolapi-wasm) [![npm](https://badgen.net/npm/v/toolapi-wasm)](https://www.npmjs.com/package/toolapi-wasm) | JavaScript wrapper: `npm install toolapi-wasm` |

# Organization

MRX organization repositories for documentation and project management.

| Project                                                                                                                      | Description                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [![github](https://badgen.net/badge/icon/mrx-org.github.io?icon=github&label)](https://github.com/mrx-org/mrx-org.github.io) | **[MRX Website](https://mrx-org.github.io/)**: The website you are currently on. Contains examples and documentation, tracks the current progress and captures the goals of MRX.                                                                       |
| [![github](https://badgen.net/badge/icon/nofield?icon=github&label)](https://github.com/mrx-org/nofield)                     | **[No-field Scanner](https://mrx-org.github.io/nofield/)**: Virtual scanner interface with parameter configuration, FOV selection and simulated measurement of MRI sequences defined by [pypulseq](https://github.com/imr-framework/pypulseq) scripts. |
| [![github](https://badgen.net/badge/icon/mrx-board?icon=github&label)](https://github.com/mrx-org/mrx-board)                 | _confidential_                                                                                                                                                                                                                                         |

# Tools

Building blocks for MRX apps. These tools are built using the [MRX ToolAPI](toolapi/index) and provide different functionalities, which have to be connected by apps or scripts.

| Project | Description |
| ------- | ----------- |
| [![github](https://badgen.net/badge/icon/tool_phantomlib_flyio?icon=github&label)](https://github.com/mrx-org/tool_phantomlib_flyio) | **[Phantom Library](https://tool-phantomlib-flyio.fly.dev/)**: Retrieve a segmented BrainWeb phantom at any resolution and FOV. |
| [![github](https://badgen.net/badge/icon/tool-conseq?icon=github&label)](https://github.com/mrx-org/tool-conseq) | **[Sequence Loader](https://tool-conseq.fly.dev/)**: Load a Pulseq .seq file into a ToolAPI sequence. |
| [![github](https://badgen.net/badge/icon/tool-trajex?icon=github&label)](https://github.com/mrx-org/tool-trajex) | **[Trajectory Extractor](https://tool-trajex.fly.dev/)**: Highly accurate k-space trajectory (encoding) extractor using a PDG simulation. |
| [![github](https://badgen.net/badge/icon/tool-rapisim?icon=github&label)](https://github.com/mrx-org/tool-rapisim) | **[Simulation](https://tool-rapisim.fly.dev/)**: Fastest, state-of-the-art MRI simulation. |
| [![github](https://badgen.net/badge/icon/tool-mr0sim?icon=github&label)](https://github.com/mrx-org/tool-mr0sim) | **[Simulation MR-zero](https://tool-mr0sim.fly.dev/)**: MRI simulation using the Python MR-zero PDG simulator. |
| [![github](https://badgen.net/badge/icon/tool-spinsim?icon=github&label)](https://github.com/mrx-org/tool-spinsim) | **[Isochromat Simulation](https://tool-spinsim.fly.dev/)**: Simple isochromat-based MRI simulation. |

# Outdated

There is one outdated repository: [mrx-org/mrx](https://github.com/mrx-org/mrx). This was a monorepo for the first iteration. It contains an outdated version / prototype of the toolapi, as well as a couple of tools. Some of them should be extracted into their own tool repos:

- [x] `tool_basic_bloch_sim`: A purposefully simple isochromat simulation, useful a ground-truth
- [x] `tool_kspace_extract`: Automatic k-space trajectory extraction, to be replaced with new `trajex` tool
- [x] `tool_mr0sim`: Provides MR-zero PDG simulation as MRX tool (first toolapi-py server impl)
- [ ] `tool_pulseq_loader`: Converts pulseq into ToolAPI block seq - which is not yet provided in current ToolAPI
- [x] `tool_spdg`: State-of-the-art simulation (should be renamed)
