"""Read the deployed source for a narrowly scoped, separately recorded hotfix."""
import pathlib
import sys

sys.stdout.write(pathlib.Path('/app/a2a_server/database.py').read_text())