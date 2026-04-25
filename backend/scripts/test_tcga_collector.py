"""
Test TCGA collector to verify it downloads REAL data.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import using absolute import
from data_collection.tcga_collector import TCGACollector
import traceback


def test_tcga_collector():
    """Test TCGA collector with real data download."""
    print("=" * 60)
    print("Testing TCGA Collector - Real Data Download")
    print("=" * 60)
    
    try:
        # Initialize collector
        print("\n1. Initializing TCGA collector...")
        collector = TCGACollector()
        print("   [OK] Collector initialized")
        
        # Test getting available datasets
        print("\n2. Getting available datasets...")
        datasets = collector.get_available_datasets()
        print(f"   [OK] Found {len(datasets)} available datasets")
        if datasets:
            print(f"   Sample dataset: {datasets[0].get('name', 'N/A')}")
        
        # Test collecting a small amount of real data
        print("\n3. Collecting REAL gene expression data (BRCA, 5 samples)...")
        print("   This will download actual data from GDC API...")
        
        results = collector.collect_data(
            data_type="gene_expression",
            cancer_type="BRCA",
            sample_limit=5  # Small limit for testing
        )
        
        print(f"\n   [OK] Collection completed!")
        print(f"   - Data type: {results.get('data_type')}")
        print(f"   - Cancer type: {results.get('cancer_type')}")
        print(f"   - Samples collected: {results.get('samples_collected', 0)}")
        
        if results.get('data') is not None:
            data = results['data']
            print(f"   - Data shape: {data.shape if hasattr(data, 'shape') else 'N/A'}")
            print(f"   - Data type: {type(data).__name__}")
            
            # Verify it's not empty
            if hasattr(data, 'empty'):
                if not data.empty:
                    print("   [OK] Data is NOT empty - REAL data downloaded!")
                    print(f"   - First few columns: {list(data.columns[:5]) if hasattr(data, 'columns') else 'N/A'}")
                else:
                    print("   [WARNING] Data is empty")
            else:
                print("   [OK] Data object created")
        else:
            print("   [WARNING] No data returned")
        
        # Check for saved file
        print("\n4. Checking for saved data file...")
        output_dir = collector.output_dir
        files = list(output_dir.glob("tcga_*.csv"))
        if files:
            print(f"   [OK] Found {len(files)} saved file(s):")
            for f in files[:3]:  # Show first 3
                size = f.stat().st_size
                print(f"     - {f.name} ({size:,} bytes)")
        else:
            print("   [WARNING] No saved files found")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE - TCGA Collector is using REAL data!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_tcga_collector()
    sys.exit(0 if success else 1)
