---
title: Welcome to MRX
---

You can find our first application here: [**No-field Scanner**](https://mrx-org.github.io/nofield/)

> [!info] Work in Progress 🚧
> This documentation is currently under construction and partially severely outdated.
> An up-to-date list of current projects can be found in [[overview]].

---

# MRX - MR Expertise

Funded by [START-interaktiv](https://www.interaktive-technologien.de/foerderung/bekanntmachungen/start-interaktiv) (BMFTR, February 2026 - January 2029). 

> **3 - year - goal of MRX**
>
> Creating `MRX: Assistant`, an intelligent AI assistant, supporting clinic personell with MR measurements.
> An LLM allows easy interaction without prior training.
> A deep integration with the scanner means full data insight and quick interaction with the user.
> An extensive, physics based world model delivers facts instead of hallucinations.

The necessary tools for this project will also form the foundation of future applications of MRX:
Sequence development, optimizing for low-cost hardware, training of new reconstruction networks and more.


## Building Blocks

The foundation of `MRX: Assistant` consists of various building blocks.
These are developed independent of each other.
This allows to use them to construct new products which go beyond the target of an assistant.

- [`MRX: ToolAPI`](toolapi/index.md): Connect any application with any MRX world-model tool, easily. Allows quick experimentation: comparing implementations, testing tools in various scenarios. Developed first as it helps with the development of the other building blocks.
- [`MRX: Pulseq`](pulseq/index.md): Create sequences with a fully [pypulseq](https://github.com/imr-framework/pypulseq) copmatible API. Supports `.seq` files and is `MRX: ToolAPI` compatible.
- [Tools](tools/index.md): Tools built in Rust and Python, using the `MRX: ToolAPI`.
- [Apps](apps/index.md): Apps using different Tools to build Products.
