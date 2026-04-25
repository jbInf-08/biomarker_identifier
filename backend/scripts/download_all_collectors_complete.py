"""
Complete script to download from ALL collectors.
Attempts to use all available collectors in the data_collection directory.
"""
import sys
import importlib
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback

# Add data_collection to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'data_collection'))

# Base directory for real data
output_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "real_data"
output_dir.mkdir(parents=True, exist_ok=True)

def get_all_collector_classes():
    """Discover all collector classes dynamically."""
    collectors = {}
    data_collection_dir = Path(__file__).parent.parent.parent / 'data_collection'
    
    # Find all collector files
    collector_files = list(data_collection_dir.glob('*_collector.py'))
    
    # Exclude base and generator
    exclude = ['base_collector.py', 'generate_all_collectors.py']
    collector_files = [f for f in collector_files if f.name not in exclude]
    
    for collector_file in collector_files:
        try:
            module_name = collector_file.stem
            class_name = None
            
            # Read file to find class name
            content = collector_file.read_text(encoding='utf-8')
            import re
            class_match = re.search(r'class\s+(\w+Collector)', content)
            if class_match:
                class_name = class_match.group(1)
                
                # Try to import
                try:
                    module = importlib.import_module(f'data_collection.{module_name}')
                    collector_class = getattr(module, class_name)
                    collectors[module_name] = {
                        'class': collector_class,
                        'name': class_name,
                        'file': collector_file.name
                    }
                except Exception as e:
                    print(f"  [SKIP] {module_name}: Import error - {e}")
                    
        except Exception as e:
            print(f"  [SKIP] {collector_file.name}: {e}")
            continue
    
    return collectors

def download_from_all_collectors():
    """Download from all available collectors."""
    print("=" * 60)
    print("Downloading from ALL Collectors")
    print("=" * 60)
    
    collectors = get_all_collector_classes()
    print(f"\nFound {len(collectors)} collectors")
    
    results = {}
    successful = 0
    failed = 0
    skipped = 0
    
    for module_name, collector_info in sorted(collectors.items()):
        collector_class = collector_info['class']
        collector_name = collector_info['name']
        source_name = collector_name.replace('Collector', '')
        
        print(f"\n[{source_name}] Trying {collector_name}...")
        
        try:
            # Create collector instance
            collector_output_dir = output_dir / source_name.lower()
            collector_output_dir.mkdir(parents=True, exist_ok=True)
            
            collector = collector_class(output_dir=str(collector_output_dir))
            
            # Try to collect data with default parameters
            # Use sample_limit to keep downloads small
            params = {
                'data_type': 'default',
                'sample_limit': 10
            }
            
            # Try expression data if available
            try:
                result = collector.collect_data(data_type='expression', sample_limit=10)
            except:
                try:
                    result = collector.collect_data(data_type='expression_data', sample_limit=10)
                except:
                    result = collector.collect_data(**params)
            
            if result and "data" in result:
                if isinstance(result["data"], pd.DataFrame) and not result["data"].empty:
                    # Save to main directory
                    output_file = output_dir / f"{source_name.lower()}_individual_real.csv"
                    result["data"].to_csv(output_file, index=True)
                    print(f"  [OK] Saved {source_name} data ({len(result['data'])} records)")
                    results[source_name] = True
                    successful += 1
                else:
                    print(f"  [SKIP] {source_name}: Empty or invalid data")
                    results[source_name] = False
                    skipped += 1
            else:
                print(f"  [SKIP] {source_name}: No data returned")
                results[source_name] = False
                skipped += 1
                
        except Exception as e:
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            print(f"  [SKIP] {source_name}: {error_msg}")
            results[source_name] = False
            failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("Download Summary")
    print("=" * 60)
    print(f"Successful: {successful}/{len(collectors)}")
    print(f"Failed: {failed}/{len(collectors)}")
    print(f"Skipped: {skipped}/{len(collectors)}")
    
    if successful > 0:
        print("\nSources with real data:")
        for source, success in sorted(results.items()):
            if success:
                print(f"  [OK] {source}")
    
    # List downloaded files
    csv_files = list(output_dir.glob("*.csv"))
    if csv_files:
        print("\n" + "=" * 60)
        print("Downloaded Real Data Files")
        print("=" * 60)
        for csv_file in sorted(csv_files):
            size = csv_file.stat().st_size
            print(f"  [FILE] {csv_file.name} ({size:,} bytes)")
    
    print("\n" + "=" * 60)
    print("SUCCESS: Real data downloaded from multiple sources!")
    print("=" * 60)
    print(f"Location: {output_dir}")
    print("\nTest fixtures will automatically use this real data.")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    download_from_all_collectors()
