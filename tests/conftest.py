import os
import sys

# The modules under test live in the skill directory (dz-generics/scripts/),
# not next to the tests (tests/). pytest puts the test directory on sys.path,
# so without this line `from build_index import ...` can never resolve.
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "dz-generics", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

SOURCE_XLSX = os.path.join(
    os.path.dirname(__file__), "..", "data", "source",
    "NOMENCLATURE.VERSION.AOUT_.2026-.xlsx",
)
