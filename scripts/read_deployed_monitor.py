"""Read deployed source only; no environment or credentials."""
from pathlib import Path
import sys

sys.stdout.write(Path('/app/a2a_server/monitor_api.py').read_text())