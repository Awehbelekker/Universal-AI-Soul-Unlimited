"""
Simple test for HRM engine
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.engines.hrm_engine import HRMEngine

async def test_hrm():
    print("Testing HRM engine...")
    engine = HRMEngine()
    await engine.initialize()
    print("HRM initialized successfully!")

if __name__ == "__main__":
    asyncio.run(test_hrm())