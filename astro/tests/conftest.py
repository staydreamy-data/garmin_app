from __future__ import annotations

import os
import sys
from pathlib import Path


ASTRO_ROOT = Path(__file__).resolve().parents[1]

# Keep Airflow logs/state inside the repo during local test discovery.
os.environ.setdefault("AIRFLOW_HOME", str(ASTRO_ROOT))

# Allow imports like `include.*` and `dags.*` from tests.
if str(ASTRO_ROOT) not in sys.path:
    sys.path.insert(0, str(ASTRO_ROOT))
