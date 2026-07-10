"""Keep the Python 3.12 project out of older repository-level test runs."""

import sys

collect_ignore_glob = ["tests/test_*.py"] if sys.version_info < (3, 12) else []
