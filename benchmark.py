#!/usr/bin/env python3
"""Point d'entrée : python benchmark.py run|report|analyze|compare ..."""
import sys

from ragbench.cli import main

if __name__ == "__main__":
    sys.exit(main())
