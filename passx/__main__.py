"""Direct module execution entry point (python -m passx)"""
import sys
from passx.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
