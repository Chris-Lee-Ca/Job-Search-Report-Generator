import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Exclude the standalone diagnostic scraping tool — not a pytest test suite
collect_ignore = ["test_scrape.py"]
