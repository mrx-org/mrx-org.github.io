# Tool

A tool is a standalone program, which can be executed from the command line.
Examples are a combined library (`"bloch_sim.exe"`) or a python script (`"python sar_calc.py"`).

The tool retrieves its inputs via the `MRX: ToolAPI`, does its computations (optionally reporting progress) returns the output via the same API, then shuts down.
This makes writing tools very simple: It can be written in any language supported by MRX (currently Rust and Python).
A short, self contained file or script is sufficient, the result is a small, independent executable program or script.


# Host

The host can be any environment that executes tools. Examples are:
- A self-contained program like a viewer or GUI for MR tasks
- A shim between the tools and LLMs, exposing the capabilities of the tools via MCP
- A python script, optimizing a sequence using simulation and reconstruction tools
- A jupyter notebook session, interactively experimenting with MR ideas with the help of tools.

The `MRX: ToolAPI` makes it easy to define all input parameters, call the tool, poll progress and retrieve its output.
Errors of the tool are passed to the Host.
From a programming point of view, calling a tool feels very similar to calling a function.
The limited set of possible parameter types makes it possible to easily exchange tools with similar purposes, even if they were programmed completely independently from different people.

# Connection

The exact method of communication between Host and Tool is deliberately opaque.
This avoids lock-in into a specific host-tool combination, exposing the exchange of values as the only observable effect of `MRX: ToolAPI`.
It also makes it possible to iterate and improve the exchange method without requring any code changes to the Host or the Tool.

Currently, the project opens an inter-process channel (Windows named pipe or UNIX domain socket), serializes all values to json and passes it over the channel.
