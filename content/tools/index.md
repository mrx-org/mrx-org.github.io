---
title: Tools
---

Tools are called using `toolapi::call`. Look at its documentation for details; view the tool pages for information about expected parameters and return values.

# [`tool-phantomlib`](phantomlib)

Provides easy loading of phantoms: any slice, any orientation, any resolution. Specify an affine matrix (rotation + translation), a resolution and a phantom ID in order to quickly load a segmented or voxel grid phantom. This tool eliminates the need to ship apps with example data by providing a database of quantified phantoms.

# [`tool-conseq`](conseq)

Currently a very basic tool which converts a Pulseq .seq file (contents passed as string) into a ToolAPI sequence, ready to be simulated by the simulation tool.

# [`tool-trajex`](trajex)

Automatic k-space trajectory extraction of arbitrary MRI sequences. Works by accurately determining the encoding of the generated signal.

# [`tool-rapisim`](rapisim)

Takes a ToolAPI phantom and sequence as input and simulates an accurate MRI signal from it. Exact implementation is subject to change; aims to produce quantitative exact (and physically accurate) results which can be reconstructed with the same tools to deliver the same images as in-vivo measurements.

# [`tool-spinsim`](spinsim)

A very basic isochromat simulation, programmed in Rust. Meant as ground-truth with as little space for bugs as possible; performance is not a priority.