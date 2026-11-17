"""The desktop app's backend: everything the window calls, without the window.

Each call takes and returns plain JSON-friendly values, so the web front end
(pywebview) can use it directly and it can all be tested headless.
"""
