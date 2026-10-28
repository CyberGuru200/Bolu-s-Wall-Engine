"""WSGI entry point.

Defaults to production settings; override with DJANGO_SETTINGS_MODULE when a
different environment is genuinely intended.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
