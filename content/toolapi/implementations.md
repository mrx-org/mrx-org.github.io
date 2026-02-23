---
title: Available implementations
---

ToolAPI aims to connect tools and clients written in any language. It should be possible to call a Rust tool from an LLM that executes in a Python environment or a Python tool from a JavaScript web app without any having to worry about any language specific details.

- Rust toolapi: The core implementation, defines value types and the communication protocol between server and client (which is never exposed to the user - makes future upgrades easy).
- Python: Wrapper around Rust which defines python classes for all Value types for ideomatic programming and type checking. Convertes from / to Rust on tool calls.
- JavaScript: Highly dynamic wrapper; constructs JS types via `serde_wasm_bindgen`