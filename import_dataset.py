"""Root command: import data/registered/ into MongoDB.

Usage:
    .\\.venv\\Scripts\\python.exe import_dataset.py [--root PATH]
"""
import sys
import os

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.import_command import main

if __name__ == "__main__":
    sys.exit(main())
