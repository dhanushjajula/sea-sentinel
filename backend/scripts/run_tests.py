"""Sea Sentinel Automated Test Runner."""
import sys
import unittest
from pathlib import Path

<<<<<<< HEAD:backend/scripts/run_tests.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

=======
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f:scripts/run_tests.py

def main():
    print("=" * 70)
    print("           SEA SENTINEL 2.0 - AUTOMATED TEST SUITE")
    print("=" * 70)
    
    loader = unittest.TestLoader()
<<<<<<< HEAD:backend/scripts/run_tests.py
    suite = loader.discover(start_dir=str(BACKEND_DIR / "tests"), pattern="test_*.py")
=======
    suite = loader.discover(start_dir=str(PROJECT_ROOT / "tests"), pattern="test_*.py")
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f:scripts/run_tests.py
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 70)
    if result.wasSuccessful():
        print(f"ALL {result.testsRun} TESTS PASSED SUCCESSFULLY!")
        return 0
    else:
        print(f"TEST RUN COMPLETED: {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
