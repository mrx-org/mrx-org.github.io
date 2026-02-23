---
title: ToolAPI
---

# MRX: ToolAPI
_aka "Universal Simulation Interface"_

<div class="warning">

**TODO** \
For consistency and better naming, all MRX projects should be named `MRX: xyz`.
This means that USI changes to `MRX: ToolAPI`, which makes the goals of USI clearer as well.

Replace all occurences in the book and in the whole `mrx` repo, then delete this warning.

</div>

---

This projects makes it possible to easily:
- switch tools (e.g: different simulations) in an application with little code changes
- use a tool in many applications.

Therefore alternative implementations of a tool can be compared, which is helpful in development.
Tools can also be shared and reused, as well as get tested in many environments.
This is made possible through an interface, which is coded intependently of tools and applications.
It is the "contract" between those two, a simple API that is quickly implemented on both ends and reduces communication to a fixed set of easy to understand value types.