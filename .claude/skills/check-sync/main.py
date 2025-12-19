#!/usr/bin/env python3
"""Check sync status between outline, Zotero collections, and Scrivener structure."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.sync_checker import SyncChecker


def main():
    """Check and report sync status."""
    checker = SyncChecker()
    status = checker.check_sync_status()
    report = checker.format_sync_report(status)
    print(report)


if __name__ == "__main__":
    main()
