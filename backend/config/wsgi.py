import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

for candidate in (Path("/opt/greenblatt/src"), Path(__file__).resolve().parents[2] / "src"):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

application = get_wsgi_application()
