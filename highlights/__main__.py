"""Enable `python -m highlights`.

Delegates to the CLI so the package can be run as a module, matching the
installed `highlights` console command.
"""

from highlights.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
