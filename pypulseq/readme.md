# PyPulseq RARE 2D Interactive (Pyodide)

A web-based interface for interactive MR sequence design using **Pyodide**, **pypulseq**, and **Matplotlib**.

## General Implementation

1.  **Dynamic UI via `inspect`:** Python's `inspect.signature` automatically detects the arguments of `seq_RARE_2D`, which are then dynamically mapped to HTML sliders, checkboxes, and text inputs.
2.  **Delayed Rendering:** Uses `seq.plot(plot_now=False)` followed by `plt.show()` to ensure the plotting loop doesn't block the main browser thread, keeping the UI responsive.
3.  **Interactive Mode:** `plt.ion()` enables the interactive zoom/pan features provided by the patched `WebAgg` backend in Pyodide 0.28.0+.

## The Fuckery (Workarounds)

1.  **"UFO" Div Capture (MutationObserver):** The Matplotlib `WebAgg` backend frequently bypasses `document.pyodideMplTarget` and appends figure `div`s directly to the end of the `<body>`. A `MutationObserver` watches for these "ufo" nodes and instantly "teleports" them into the intended `#plot-output` container.
2.  **Backend Redirects:** Both `document.pyodideMplTarget` and `window.pyodideMplTarget` are set simultaneously to maximize the chance of Matplotlib respecting the target container.

## Requirements
- Pyodide v0.28.0+
- pypulseq (installed via micropip)
- Matplotlib (wasm-compatible backend)
