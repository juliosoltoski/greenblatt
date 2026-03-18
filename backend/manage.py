#!/usr/bin/env python
import os
import sys
from pathlib import Path


for candidate in (Path("/opt/greenblatt/src"), Path(__file__).resolve().parents[1] / "src"):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django. Is it installed and available on your PYTHONPATH?") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
