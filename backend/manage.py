#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def main():
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "config.settings.development"
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django is not available. Activate backend/.venv and install "
            "backend/requirements.txt."
        ) from exc
    execute_from_command_line()


if __name__ == "__main__":
    main()
