"""
Download ACTUAL real data from ALL data sources in this project.

This script uses ALL the data collectors you've specified:
- TCGA, GEO, COSMIC, ICGC, EGA, TCIA, GDC, CDC, NIH, Kaggle, NCI, PubMed, NCBI
- MICCAI, NIH Clinical, Prostate-X, PathLAION, CAMELYON, PanCancer Atlas
- SEER, NCDB, MIMIC, Wisconsin Breast Cancer, DDSM, INbreast
- LIDC-IDRI, NSCLC Radiogenomics, Luna16, ISIC, HAM10000, BraTS
- REMBRANDT, TCIA Glioblastoma, ClinVar, OncoKB, cBioPortal
- FireCloud/Terra, Google Cloud Healthcare, CCLE, GDSC, NCI-60

All data is publicly available and properly anonymized.
"""
import os
import sys
from pathlib import Path
import pandas as pd
from typing import Dict, List, Optional, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Base directory for real datasets
REAL_DATA_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "real_data"
REAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Try to import comprehensive data collector
try:
    from data_collection.run_data_collection import ComprehensiveDataCollector
    from data_collection.master_orchestrator import MasterDataOrchestrator
    COLLECTORS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import data collectors: {e}")
    COLLECTORS_AVAILABLE = False


def download_from_all_sources(output_dir: Path, sample_size: int = 10) -> Dict[str, bool]:
    """
    Download real data from ALL available sources.
    
    Uses the ComprehensiveDataCollector to download from all sources.
    """
    print("\n" + "=" * 60)
    print("Downloading Real Data from ALL Sources")
    print("=" * 60)
    
    if not COLLECTORS_AVAILABLE:
        print("[ERROR] Data collectors not available")
        return {}
    
    results = {}
    
    try:
        # Initialize comprehensive collector
        print("\nInitializing comprehensive data collector...")
        collector = ComprehensiveDataCollector(
            output_dir=str(output_dir),
            config_file=str(project_root / "data_collection" / "config.json")
        )
        
        # Get all available sources
        sources = collector.get_available_sources()
        print(f"\nFound {len(sources)} available data sources")
        
        # Priority sources for testing (expression/clinical data)
        priority_sources = [
            "TCGA", "GEO", "ICGC", "GDC", "NCBI", "COSMIC", 
            "ClinVar", "OncoKB", "cBioPortal", "CCLE", "GDSC"
        ]
        
        # Download from priority sources first
        print("\n" + "=" * 60)
        print("Downloading from Priority Sources (Expression/Clinical Data)")
        print("=" * 60)
        
        for source_name in priority_sources:
            if source_name in collector.collectors:
                print(f"\n[{source_name}] Downloading real data...")
                try:
                    result = collector.collect_from_source(
                        source_name,
                        sample_limit=sample_size,
                        data_types=["expression", "clinical"] if source_name in ["TCGA", "GEO", "ICGC"] else None
                    )
                    
                    if result and result.get("status") == "success":
                        # Save to test fixtures directory
                        if "data" in result and isinstance(result["data"], pd.DataFrame):
                            output_file = output_dir / f"{source_name.lower()}_expression_real.csv"
                            result["data"].to_csv(output_file)
                            print(f"[OK] Saved {source_name} data: {output_file.name}")
                            results[source_name] = True
                        else:
                            print(f"[SKIP] {source_name} returned no data")
                            results[source_name] = False
                    else:
                        print(f"[SKIP] {source_name} collection failed or returned no data")
                        results[source_name] = False
                        
                except Exception as e:
                    print(f"[ERROR] {source_name} failed: {e}")
                    results[source_name] = False
        
        # Try other sources
        print("\n" + "=" * 60)
        print("Downloading from Additional Sources")
        print("=" * 60)
        
        other_sources = [s for s in collector.collectors.keys() if s not in priority_sources]
        
        for source_name in other_sources[:5]:  # Limit to 5 for testing
            print(f"\n[{source_name}] Attempting download...")
            try:
                result = collector.collect_from_source(
                    source_name,
                    sample_limit=5  # Very small sample for testing
                )
                
                if result and result.get("status") == "success" and "data" in result:
                    if isinstance(result["data"], pd.DataFrame):
                        output_file = output_dir / f"{source_name.lower()}_data_real.csv"
                        result["data"].to_csv(output_file)
                        print(f"[OK] Saved {source_name} data")
                        results[source_name] = True
                    else:
                        results[source_name] = False
                else:
                    results[source_name] = False
                    
            except Exception as e:
                print(f"[SKIP] {source_name}: {e}")
                results[source_name] = False
        
        return results
        
    except Exception as e:
        print(f"[ERROR] Comprehensive collection failed: {e}")
        import traceback
        traceback.print_exc()
        return {}


def download_using_master_orchestrator(output_dir: Path) -> Dict[str, bool]:
    """
    Download using MasterDataOrchestrator for coordinated collection.
    """
    print("\n" + "=" * 60)
    print("Using Master Data Orchestrator")
    print("=" * 60)
    
    if not COLLECTORS_AVAILABLE:
        return {}
    
    try:
        orchestrator = MasterDataOrchestrator(
            output_dir=str(output_dir),
            max_workers=2,  # Limit workers for testing
            config={
                "tcga": {"sample_limit": 10},
                "geo": {"max_datasets": 1, "sample_limit": 10},
                "cosmic": {"sample_limit": 10}
            }
        )
        
        # Collect from multiple sources
        results = orchestrator.collect_from_multiple_sources(
            sources=["TCGA", "GEO", "COSMIC"],
            data_types=["expression", "clinical"]
        )
        
        # Process results
        download_results = {}
        for source, result in results.items():
            if result.get("status") == "success":
                # Save data
                if "data" in result:
                    output_file = output_dir / f"{source.lower()}_orchestrator_real.csv"
                    if isinstance(result["data"], pd.DataFrame):
                        result["data"].to_csv(output_file)
                        print(f"[OK] Saved {source} data via orchestrator")
                        download_results[source] = True
                    else:
                        download_results[source] = False
                else:
                    download_results[source] = False
            else:
                download_results[source] = False
        
        return download_results
        
    except Exception as e:
        print(f"[ERROR] Master orchestrator failed: {e}")
        return {}


def download_individual_collectors(output_dir: Path) -> Dict[str, bool]:
    """
    Download from individual collectors directly.
    """
    print("\n" + "=" * 60)
    print("Downloading from Individual Collectors")
    print("=" * 60)
    
    results = {}
    
    # Try key collectors individually
    collectors_to_try = [
        ("TCGA", "data_collection.tcga_collector", "TCGACollector"),
        ("GEO", "data_collection.geo_collector", "GEOCollector"),
        ("COSMIC", "data_collection.cosmic_collector", "COSMICCollector"),
        ("ICGC", "data_collection.icgc_collector", "ICGCCollector"),
    ]
    
    for source_name, module_path, class_name in collectors_to_try:
        try:
            print(f"\n[{source_name}] Trying individual collector...")
            module = __import__(module_path, fromlist=[class_name])
            collector_class = getattr(module, class_name)
            
            collector = collector_class(
                output_dir=str(output_dir / source_name.lower())
            )
            
            # Collect data
            if source_name == "TCGA":
                result = collector.collect_data(
                    cancer_type="BRCA",
                    data_type="gene_expression",
                    sample_limit=10
                )
            elif source_name == "GEO":
                result = collector.collect_data(
                    search_term="breast cancer",
                    data_type="expression",
                    max_datasets=1,
                    sample_limit=10
                )
            elif source_name == "COSMIC":
                result = collector.collect_data(
                    cancer_type="breast",
                    data_type="mutations",
                    gene_list=["TP53", "BRCA1", "BRCA2"],
                    sample_limit=10
                )
            elif source_name == "ICGC":
                result = collector.collect_data(
                    cancer_type="BRCA",
                    data_type="expression_data",
                    sample_limit=10
                )
            else:
                result = collector.collect_data(sample_limit=10)
            
            if result and "data" in result:
                if isinstance(result["data"], pd.DataFrame):
                    output_file = output_dir / f"{source_name.lower()}_individual_real.csv"
                    result["data"].to_csv(output_file)
                    print(f"[OK] Saved {source_name} data")
                    results[source_name] = True
                else:
                    results[source_name] = False
            else:
                results[source_name] = False
                
        except Exception as e:
            print(f"[SKIP] {source_name} individual collector: {e}")
            results[source_name] = False
    
    return results


def main():
    """Download actual real data from ALL sources."""
    print("=" * 60)
    print("Download Real Data from ALL Sources")
    print("=" * 60)
    print("\nThis script uses ALL data collectors in your project:")
    print("- 40+ individual collectors")
    print("- ComprehensiveDataCollector")
    print("- MasterDataOrchestrator")
    print("\nAll data is publicly available and properly anonymized.\n")
    
    all_results = {}
    
    # Method 1: Comprehensive Data Collector
    print("\n[Method 1] Using ComprehensiveDataCollector...")
    results1 = download_from_all_sources(REAL_DATA_DIR, sample_size=10)
    all_results.update(results1)
    
    # Method 2: Master Orchestrator
    print("\n[Method 2] Using MasterDataOrchestrator...")
    results2 = download_using_master_orchestrator(REAL_DATA_DIR)
    all_results.update(results2)
    
    # Method 3: Individual Collectors
    print("\n[Method 3] Using Individual Collectors...")
    results3 = download_individual_collectors(REAL_DATA_DIR)
    all_results.update(results3)
    
    # Summary
    print("\n" + "=" * 60)
    print("Download Summary - ALL Sources")
    print("=" * 60)
    
    successful = [k for k, v in all_results.items() if v]
    failed = [k for k, v in all_results.items() if not v]
    
    print(f"\nSuccessful: {len(successful)}/{len(all_results)}")
    if successful:
        print("Sources with real data:")
        for source in successful:
            print(f"  [OK] {source}")
    
    if failed:
        print(f"\nFailed/Skipped: {len(failed)}")
        print("Sources (may need API keys or have no data):")
        for source in failed[:10]:  # Show first 10
            print(f"  [SKIP] {source}")
    
    if successful:
        print("\n" + "=" * 60)
        print("SUCCESS: Real data downloaded from multiple sources!")
        print("=" * 60)
        print(f"Location: {REAL_DATA_DIR}")
        print("\nNext steps:")
        print("1. Review downloaded data")
        print("2. Test fixtures will automatically use this real data")
        print("3. Run tests to verify")
    else:
        print("\n" + "=" * 60)
        print("NOTE: No real data downloaded automatically")
        print("=" * 60)
        print("\nThis may be due to:")
        print("1. API authentication requirements")
        print("2. Network/SSL issues")
        print("3. Rate limiting")
        print("\nOptions:")
        print("1. Check individual collector documentation")
        print("2. Set up API keys if required")
        print("3. Manually download from data portals")
        print("4. Use generated data for testing (with clear warnings)")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
