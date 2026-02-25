---
title: Development overview
---
This page is a list of all repositories that were created to achieve the goals of MRX.
It is meant as an overview and to keep track of our efforts so far.
All repositories are hosted in the [mrx-org](https://github.com/mrx-org/) GitHub organization.

---

# Apps

At the current point in time, the goal of applications is to demonstrate the capabilities of MRX. These demos can be used as building blocks or tutorials for future applications. They do not necessarily reflect what will be available at later stages of MRX.

| App                                                    | Description                                                                                                                                                                               | Repository                                    |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| [No-field Scanner](https://mrx-org.github.io/nofield/) | Virtual scanner interface with parameter configuration, FOV selection and simulated measurement of MRI sequences defined by [pypulseq](https://github.com/imr-framework/pypulseq)scripts. | [nofield](https://github.com/mrx-org/nofield) |

# Infrastructure

These projects help development and presentation of MRX apps.

| Project                                                          | Description                                                                                                                       | Repository                                                        |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| [MRX Website](https://mrx-org.github.io/)                        | The website you are currently on. Contains examples and documentation, tracks the current progress and captures the goals of MRX. | [mrx-org.github.io](https://github.com/mrx-org/mrx-org.github.io) |
| [toolapi · crates.io](https://crates.io/crates/toolapi)          | Rust implementation of the [MRX ToolAPI](toolapi/index).                                                                          | [toolapi](https://github.com/mrx-org/toolapi)                     |
| [toolapi · PyPI](https://pypi.org/project/toolapi/)              | Python implementation of the [MRX ToolAPI](toolapi/index).                                                                        | [toolapi-py](https://github.com/mrx-org/toolapi-py)               |
| [toolapi-wasm · npm](https://www.npmjs.com/package/toolapi-wasm) | JavaScript / WASM implementation of the [MRX ToolAPI](toolapi/index). Currently client-only as WASM tool servers are not planned. | [toolapi-wasm](https://github.com/mrx-org/toolapi-wasm)           |
| GitHub org profile                                               | Special repository that contains the mrx-org readme (in `profile/README.md`)                                                      | [.github](https://github.com/mrx-org/.github)                     |
| Organization                                                     | `private`                                                                                                                         | [mrx-board](https://github.com/mrx-org/mrx-board)                 |

# Tools

Building blocks for MRX apps. These tools are built using the [MRX ToolAPI](toolapi/index) and provide different functionalities, which have to be connected by apps or scripts.

| Tool                                                      | Description                                                                               | Repository                                                                |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| [Phantom Library](https://tool-phantomlib-flyio.fly.dev/) | Retrieve a segmented BrainWeb phantom at any resolution and FOV.                          | [tool_phantomlib_flyio](https://github.com/mrx-org/tool_phantomlib_flyio) |
| [Sequence Loader](https://tool-conseq.fly.dev/)           | Load a Pulseq .seq file into a ToolAPI sequence.                                          | [tool-conseq](https://github.com/mrx-org/tool-conseq)                     |
| [Simulation](https://tool-spdg-flyio.fly.dev/)            | Simulate the signal of an MRI sequence from a phantom (loaded with the respective tools). | [tool_spdg_flyio](https://github.com/mrx-org/tool_spdg_flyio)             |
| [Trajectory Extractor](https://tool-trajex.fly.dev/)      | Highly accurate k-space trajectory (encoding) extractor using a PDG simulation.           | [tool-trajex](https://github.com/mrx-org/tool-trajex)                     |

# Outdated

There is one outdated repository: [mrx-org/mrx](https://github.com/mrx-org/mrx). This was a monorepo for the first iteration. It contains an outdated version / prototype of the toolapi, as well as a couple of tools. Some of them should be extracted into their own tool repos:
- [ ] `tool_basic_bloch_sim`: A purposefully simple isochromat simulation, useful a ground-truth
- [x] `tool_kspace_extract`: Automatic k-space trajectory extraction, to be replaced with new `trajex` tool
- [ ] `tool_mr0sim`: Provides MR-zero PDG simulation as MRX tool (first toolapi-py server impl)
- [ ] `tool_pulseq_loader`: Converts pulseq into ToolAPI block seq - which is not yet provided in current ToolAPI
- [x] `tool_spdg`: State-of-the-art simulation (should be renamed)