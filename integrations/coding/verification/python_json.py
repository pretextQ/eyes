"""Verification-only launcher using the standard-library Python JSON decoder."""

import json
import json.scanner
import runpy
from pathlib import Path

json.scanner.make_scanner = json.scanner.py_make_scanner
try:
    json.loads("[" * 2000 + "0" + "]" * 2000, object_pairs_hook=dict)
except RecursionError:
    pass
else:
    raise RuntimeError("JSON material did not exercise decoder depth failure")

runpy.run_path(str(Path(__file__).parents[1] / "scorer.py"), run_name="__main__")
