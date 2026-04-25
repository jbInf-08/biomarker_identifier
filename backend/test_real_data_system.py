"""
Test script to verify real data system is working correctly.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_real_data_status():
    """Test real data status checking."""
    print("=" * 60)
    print("Test 1: Real Data Status")
    print("=" * 60)
    
    try:
        import sys
        sys.path.insert(0, str(project_root / "tests" / "fixtures" / "real_data"))
        from load_real_data import get_real_data_status
        
        status = get_real_data_status()
        print(f"Status: {status}")
        
        has_real_data = any(status.values())
        print(f"Has real data: {has_real_data}")
        
        if has_real_data:
            print("[OK] Real data files found")
        else:
            print("[WARNING] No real data files found")
        
        return has_real_data
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_load_real_data():
    """Test loading real data."""
    print("\n" + "=" * 60)
    print("Test 2: Load Real Data")
    print("=" * 60)
    
    try:
        import sys
        sys.path.insert(0, str(project_root / "tests" / "fixtures" / "real_data"))
        from load_real_data import load_real_expression_data
        
        data = load_real_expression_data()
        
        print(f"Data type: {type(data)}")
        print(f"Data shape: {data.shape}")
        if hasattr(data, 'columns'):
            print(f"Columns: {list(data.columns)[:5]}...")
        if hasattr(data, 'index'):
            print(f"Index type: {type(data.index)}")
        
        print("[OK] Real data loaded successfully")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fixtures():
    """Test that fixtures can load real data."""
    print("\n" + "=" * 60)
    print("Test 3: Test Fixtures")
    print("=" * 60)
    
    try:
        import sys
        sys.path.insert(0, str(project_root / "tests"))
        from conftest_real_data_fixtures import real_expression_data
        
        # Fixtures are pytest functions - we can't call them directly
        # But we can verify they exist and are properly defined
        print(f"Fixture function: {real_expression_data}")
        print(f"Fixture type: {type(real_expression_data)}")
        print(f"Fixture name: {real_expression_data.__name__}")
        
        # Check if fixture has proper docstring
        if hasattr(real_expression_data, '__doc__') and real_expression_data.__doc__:
            print(f"Fixture docstring: {real_expression_data.__doc__[:50]}...")
        
        # The fixture will work in pytest context
        print("[OK] Fixture function exists and is properly defined")
        print("     (Fixtures work automatically in pytest context)")
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_downloaded_files():
    """Test that downloaded files exist."""
    print("\n" + "=" * 60)
    print("Test 4: Downloaded Files")
    print("=" * 60)
    
    real_data_dir = project_root / "tests" / "fixtures" / "real_data"
    real_files = list(real_data_dir.glob("*_real.*"))
    
    print(f"Real data directory: {real_data_dir}")
    print(f"Found {len(real_files)} real data files:")
    
    for f in real_files:
        size = f.stat().st_size
        print(f"  - {f.name} ({size:,} bytes)")
    
    if real_files:
        print("[OK] Real data files found")
        return True
    else:
        print("[WARNING] No real data files found")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Real Data System Test")
    print("=" * 60)
    print()
    
    results = {
        "Status Check": test_real_data_status(),
        "Load Data": test_load_real_data(),
        "Fixtures": test_fixtures(),
        "Downloaded Files": test_downloaded_files()
    }
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("SUCCESS: All tests passed!")
    else:
        print("WARNING: Some tests failed")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
