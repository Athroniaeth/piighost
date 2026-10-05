"""What the interpreter piighost runs in can and cannot do."""

import sys

EMSCRIPTEN = sys.platform == "emscripten"
"""Whether piighost runs under Emscripten, which is what Pyodide in a browser is.

Emscripten has neither threads nor sockets. asyncio.to_thread does not raise
there, it runs the callable inline and blocks the event loop, and urllib cannot
open a connection. The code that would rely on either checks this instead.
"""
