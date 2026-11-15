#!/usr/bin/env python
"""
Management script of the example project.

The repository root is put on sys.path, so that both the library (htmx_datatable)
and the example apps are imported with the same module paths used by the tests
(e.g. "example.books").
"""
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
