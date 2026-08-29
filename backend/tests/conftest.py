"""
pytest configuration for ThermaSense backend tests.

Sets asyncio mode to auto so all async test functions work
without needing @pytest.mark.asyncio decorators.
"""

import sys
import os

# Add the backend directory to the path so `app` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
