---
title: Welcome
---

<div class="hero" markdown>

![MRX](assets/favicon.svg){ .hero-logo }

# MRX

**Physics-based MRI simulation and AI-powered clinical assistance.**

MRX builds an ecosystem of open-source MRI simulation and analysis tools, culminating in `MRX: Assistant` — an intelligent AI assistant supporting clinic personnel with MR measurements, backed by a real physics world model.

[Try Anyfield Scanner ›](https://mrx-org.github.io/anyfield/){ .md-button .md-button--primary }
[Explore the docs ›](toolapi/index.md){ .md-button }

</div>

---

## Demos & Examples

<div class="grid cards" markdown>

-   :material-monitor-shimmer:{ .lg .middle } **MRX Tool Demo**

    ---

    Interactive browser demo of the currently available MRI simulation tools. No installation required.

    <a href="/static/demo_sim/" class="md-button" data-router-ignore>Open Demo ›</a>

-   :material-head-cog:{ .lg .middle } **Phantom Library**

    ---

    Upload and browse available MRI phantoms — any slice, orientation, and resolution via an affine matrix.

    <a href="/static/phantomlib/" class="md-button" data-router-ignore>View Phantoms ›</a>

-   :material-notebook-outline:{ .lg .middle } **Colab Notebook**

    ---

    Step-by-step Python walkthrough of the ToolAPI for MRI simulation workflows.

    [Open in Colab ›](https://colab.research.google.com/github/mrx-org/mrx-org.github.io/blob/main/notebooks/toolapi_simulation_demo.ipynb){ .md-button }

</div>

---

## Building Blocks

`MRX: Assistant` is built from independently developed components, each useful on its own for sequence development, hardware optimization, reconstruction network training, and more.

<div class="grid cards" markdown>

-   :material-api:{ .lg .middle } **MRX: ToolAPI**

    ---

    A cross-language framework connecting MRI simulation tools with any client — web apps, Python scripts, or LLM agents. Strongly-typed, transport-agnostic, and easy to extend.

    [Documentation ›](toolapi/index.md){ .md-button }

-   :material-wrench:{ .lg .middle } **Simulation Tools**

    ---

    Physics-based tools built in Rust and Python: phantom loading, sequence conversion, trajectory extraction, and multiple MRI simulators.

    [Browse tools ›](tools/index.md){ .md-button }

</div>

<p class="funding-note">Funded by <a href="https://www.interaktive-technologien.de/projekte/mrx">START-interaktiv</a> (BMFTR, February 2026 – January 2029).</p>
