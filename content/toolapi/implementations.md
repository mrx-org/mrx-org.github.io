---
title: Implementations
tags:
  - toolapi
  - rust
  - python
  - wasm
  - javascript
---

ToolAPI aims to connect tools and clients written in any language. It should be possible to call a Rust tool from a Python optimization script, or a Python tool from a JavaScript web app, without worrying about language-specific details.

The **Rust crate** is the single source of truth -- it defines all [[toolapi/values/index|value types]], the wire protocol, and both server and client logic. The **Python** and **JavaScript/WASM** packages wrap this core with language-idiomatic APIs.

| Implementation                         | Package                                                           | Role                                           |
| -------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------- |
| [Rust](#rust)                          | [toolapi on crates.io](https://crates.io/crates/toolapi)          | Core: defines types, protocol, server + client |
| [Python](#python)                      | [toolapi on PyPI](https://pypi.org/project/toolapi/)              | Client with idiomatic Python value classes     |
| [JavaScript / WASM](#javascript--wasm) | [toolapi-wasm on npm](https://www.npmjs.com/package/toolapi-wasm) | Client-only, async `call()` for web apps       |

---

## Rust

> [GitHub](https://github.com/mrx-org/toolapi) | [crates.io](https://crates.io/crates/toolapi) | version `0.4.5` | License: AGPL-3.0

The canonical ToolAPI implementation. All other implementations depend on this crate. It provides:

- The complete [[toolapi/values/index|Value]] type system
- MessagePack + zstd serialization (pure Rust, WASM-compatible)
- A WebSocket server framework for writing tools (`run_server`)
- A WebSocket client for invoking tools (`call`)

### Feature Flags

| Feature  | Description                                                        |
| -------- | ------------------------------------------------------------------ |
| `server` | Axum-based WebSocket server (native only)                          |
| `client` | WebSocket client (tungstenite on native, ws_stream_wasm on wasm32) |
| `pyo3`   | PyO3 `FromPyObject` / `IntoPyObject` impls for all Value types     |

Both `server` and `client` are enabled by default.

### Installation

```toml
[dependencies]
toolapi = "0.4"
```

For client-only usage (e.g. in a CLI or script):

```toml
[dependencies]
toolapi = { version = "0.4", default-features = false, features = ["client"] }
```

### Writing a Tool (Server)

A tool is a function with the signature `fn(Value, &mut MessageFn) -> Result<Value, ToolError>`. It receives the client's input as a `Value`, can send progress messages via the `MessageFn`, and returns a result.

```rust
use toolapi::{run_server, Value, MessageFn, ToolError};

fn my_tool(input: Value, send_msg: &mut MessageFn) -> Result<Value, ToolError> {
    // Extract parameters from input (a Dict)
    let iterations: i64 = input.get("iterations")?.try_into()?;

    send_msg(format!("Running {iterations} iterations..."))?;

    // ... perform computation ...

    Ok(Value::Float(42.0))
}

fn main() -> Result<(), std::io::Error> {
    run_server(my_tool, None)
}
```

`run_server` starts an Axum WebSocket server on `0.0.0.0:8080`:

- `GET /` serves an optional static HTML page (pass `Some(INDEX_HTML)` as second argument)
- `/tool` accepts WebSocket connections from clients

### Calling a Tool (Client)

```rust
use toolapi::{call, Value};

fn main() {
    let input = Value::Dict(/* ... build input parameters ... */);

    let result = call("wss://tool-example.fly.dev/tool", input, |msg| {
        println!("[tool] {msg}");
        true // return false to abort
    });

    match result {
        Ok(output) => println!("Result: {output:?}"),
        Err(err) => eprintln!("Error: {err}"),
    }
}
```

The `on_message` callback receives progress strings from the tool. Returning `false` sends an `Abort` signal.

### Key Types

| Type            | Description                                                                   |
| --------------- | ----------------------------------------------------------------------------- |
| `Value`         | Dynamic typed enum -- the core data type exchanged between tool and client    |
| `MessageFn`     | `dyn FnMut(String) -> Result<(), AbortReason>` -- send progress, detect abort |
| `ToolFn`        | `fn(Value, &mut MessageFn) -> Result<Value, ToolError>` -- tool signature     |
| `ToolError`     | Error returned by a tool: `Extraction`, `Abort`, or `Custom(String)`          |
| `ToolCallError` | Client-side error from `call()`: connection, protocol, or tool errors         |

---

## Python

> [GitHub](https://github.com/mrx-org/toolapi-py) | [PyPI](https://pypi.org/project/toolapi/) | version `0.4.5` | License: AGPL-3.0

Python bindings wrapping the Rust `toolapi` crate via [PyO3](https://pyo3.rs/) and [Maturin](https://www.maturin.rs/). Provides a native `call()` function and pure-Python dataclass wrappers for all Value types.

### Installation

```bash
pip install toolapi
```

> [!note]
> The package is named `toolapi` on PyPI (not `toolapi-py`). It ships a compiled native extension for the platform -- no Rust toolchain needed at install time.

### Calling a Tool

```python
from toolapi import call

def on_message(msg: str) -> bool:
    print(f"[tool] {msg}")
    return True  # return False to abort

result = call(
    "wss://tool-phantomlib-flyio.fly.dev/tool",
    {
        "fov": [0.3, 0.3, 0.3],
        "resolution": [128, 128, 1],
    },
    on_message,
)
```

The function signature is:

```python
def call(
    address: str,
    input: Value,
    on_message: Callable[[str], bool] | None = None,
) -> Value
```

- `address`: WebSocket URL of the tool server
- `input`: Any Python object that maps to a ToolAPI `Value` (see below)
- `on_message`: Optional callback for progress messages; return `False` to abort

The call blocks until the tool finishes. The GIL is released during the WebSocket communication, so other Python threads can run concurrently.

### Value Type Mapping

Primitive Python types map directly to ToolAPI values:

| Python    | ToolAPI Value                                       |
| --------- | --------------------------------------------------- |
| `None`    | `None`                                              |
| `bool`    | `Bool`                                              |
| `int`     | `Int`                                               |
| `float`   | `Float`                                             |
| `str`     | `Str`                                               |
| `complex` | `Complex`                                           |
| `dict`    | `Dict` (heterogeneous) or `TypedDict` (homogeneous) |
| `list`    | `List` (heterogeneous) or `TypedList` (homogeneous) |

For homogeneous `list` and `dict` values, the Rust side automatically infers `TypedList` / `TypedDict` for efficient packing. Heterogeneous containers use `List` / `Dict`.

### Structured Types

For MRI-specific structured types, the `toolapi.value` module provides Python dataclasses that mirror the Rust types:

```python
from toolapi.value import Vec3, Vec4, Volume, PhantomTissue, SegmentedPhantom, InstantSeqEvent
```

#### `Vec3` / `Vec4`

```python
v3 = Vec3([1.0, 2.0, 3.0])
v4 = Vec4([0.0, 0.0, 0.0, 1.0])
```

#### `Volume`

A 3D voxel volume with an affine transform:

```python
vol = Volume(
    shape=[128, 128, 1],
    affine=[
        [0.002, 0.0, 0.0, -0.128],
        [0.0, 0.002, 0.0, -0.128],
        [0.0, 0.0, 0.002, 0.0],
    ],
    data=[0.0] * (128 * 128),  # TypedList inferred as Float
)
```

#### `PhantomTissue`

A single tissue with density and off-resonance volumes, plus scalar relaxation parameters:

```python
tissue = PhantomTissue(
    density=density_volume,
    db0=db0_volume,
    t1=0.8,
    t2=0.05,
    t2dash=0.02,
    adc=0.001,
)
```

#### `SegmentedPhantom`

A multi-tissue phantom with B1 transmit/receive maps:

```python
phantom = SegmentedPhantom(
    tissues={"white_matter": wm_tissue, "gray_matter": gm_tissue},
    b1_tx=[b1_tx_volume],
    b1_rx=[b1_rx_volume],
)
```

#### `InstantSeqEvent`

A tagged union constructed via factory methods:

```python
pulse = InstantSeqEvent.Pulse(angle=3.14, phase=0.0)
fid = InstantSeqEvent.Fid(kt=[0.0, 0.0, 0.0, 0.01])
adc = InstantSeqEvent.Adc(phase=0.0)
```

---

## JavaScript / WASM

> [GitHub](https://github.com/mrx-org/toolapi-wasm) | [npm](https://www.npmjs.com/package/toolapi-wasm) | version `0.4.5` | License: AGPL-3.0

A client-only WASM wrapper around the Rust `toolapi` crate, compiled via [wasm-pack](https://rustwasm.github.io/wasm-pack/) and [wasm-bindgen](https://rustwasm.github.io/wasm-bindgen/). Exposes a single async `call()` function for use in browser and other web-compatible environments.

WASM tool servers are not planned -- tools should be hosted natively (in Rust or Python) and accessed from JavaScript as a client.

### Installation

```bash
npm install toolapi-wasm
```

Or build from source:

```bash
wasm-pack build --target web
```

### Calling a Tool

```javascript
import init, { call } from "toolapi-wasm"

await init() // initialize WASM module

const input = {
  Dict: {
    resolution: { List: [{ Int: 128 }, { Int: 128 }, { Int: 1 }] },
    flip_angle: { Float: 0.26 },
  },
}

const result = await call("wss://tool-example.fly.dev/tool", input, (msg) => {
  console.log(`[tool] ${msg}`)
  return true // return false to abort
})
```

The function signature is:

```typescript
async function call(
  addr: string,
  input: Value,
  on_message: (msg: string) => boolean,
): Promise<Value>
```

- Returns a `Promise` that resolves to the result or rejects with an `Error`
- The `on_message` callback is called for each progress message; return `false` to abort
- If the callback throws or returns a falsy value, the tool is aborted

### Value Serialization

Values are serialized via `serde_wasm_bindgen`, using **tagged objects** where the key is the type name:

| ToolAPI type | JavaScript representation                 |
| ------------ | ----------------------------------------- |
| `None`       | `{ "None": null }`                        |
| `Bool`       | `{ "Bool": true }`                        |
| `Int`        | `{ "Int": 42 }`                           |
| `Float`      | `{ "Float": 3.14 }`                       |
| `Str`        | `{ "Str": "hello" }`                      |
| `Complex`    | `{ "Complex": { "re": 1.0, "im": 2.0 } }` |
| `Vec3`       | `{ "Vec3": [1.0, 2.0, 3.0] }`             |
| `Dict`       | `{ "Dict": { "key": <Value>, ... } }`     |
| `List`       | `{ "List": [<Value>, ...] }`              |

This tagged format matches Serde's default enum serialization and is used for both input and output.
