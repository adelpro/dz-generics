import os
import sys

# The modules under test live in the skill directory (skills/dz-generics/scripts/),
# not next to the tests (tests/). pytest puts the test directory on sys.path,
# so without this line `from build_index import ...` can never resolve.
# The skill lives under skills/ so that `npx skills add` and Codex can discover
# it; see the repo README.
SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "skills", "dz-generics", "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)

SOURCE_XLSX = os.path.join(
    os.path.dirname(__file__), "..", "data", "source",
    "NOMENCLATURE.VERSION.AOUT_.2026-.xlsx",
)
