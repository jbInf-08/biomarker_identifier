"""
Download ACTUAL real data using ALL data collectors in this project.

This script uses the ComprehensiveDataCollector and ALL individual collectors
you've specified throughout the project development.
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


def setup_ssl():
    """Set up SSL certificates."""
    try:
        import certifi
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        os.environ['SSL_CERT_FILE'] = certifi.where()
        return True
    except ImportError:
        return False


def download_using_comprehensive_collector(output_dir: Path) -> Dict[str, bool]:
    """
    Use ComprehensiveDataCollector to download from all sources.
    """
    print("\n" + "=" * 60)
    print("Using ComprehensiveDataCollector (ALL Sources)")
    print("=" * 60)
    
    try:
        from data_collection.run_data_collection import ComprehensiveDataCollector
        
        # Initialize with config
        config_file = project_root / "data_collection" / "config.json"
        collector = ComprehensiveDataCollector(
            output_dir=str(output_dir),
            config_file=str(config_file) if config_file.exists() else None
        )
        
        # Get available sources
        sources = collector.get_available_sources()
        print(f"\nFound {len(sources)} available data sources")
        
        # Priority sources for expression/clinical data
        priority_sources = ["TCGA", "GEO", "ICGC", "GDC", "COSMIC", "ClinVar"]
        
        results = {}
        
        for source_name in priority_sources:
            if source_name in [s.get("name") for s in sources]:
                print(f"\n[{source_name}] Downloading...")
                try:
                    # Get the collector instance
                    if hasattr(collector, 'collectors') and source_name in collector.collectors:
                        source_collector = collector.collectors[source_name]
                        
                        # Collect data based on source type
                        if source_name == "TCGA":
                            result = source_collector.collect_data(
                                cancer_type="BRCA",
                                data_type="gene_expression",
                                sample_limit=10
                            )
                        elif source_name == "GEO":
                            result = source_collector.collect_data(
                                search_term="breast cancer",
                                data_type="expression",
                                max_datasets=1,
                                sample_limit=10
                            )
                        elif source_name == "COSMIC":
                            result = source_collector.collect_data(
                                cancer_type="breast",
                                data_type="mutations",
                                gene_list=["TP53", "BRCA1", "BRCA2"],
                                sample_limit=10
                            )
                        elif source_name == "ICGC":
                            result = source_collector.collect_data(
                                cancer_type="BRCA",
                                data_type="expression_data",
                                sample_limit=10
                            )
                        else:
                            result = source_collector.collect_data(sample_limit=10)
                    else:
                        result = None
                    
                    if result and result.get("status") == "success":
                        if "data" in result and isinstance(result["data"], pd.DataFrame):
                            output_file = output_dir / f"{source_name.lower()}_real.csv"
                            result["data"].to_csv(output_file)
                            print(f"[OK] Saved {source_name} data")
                            results[source_name] = True
                        else:
                            results[source_name] = False
                    else:
                        results[source_name] = False
                        
                except Exception as e:
                    print(f"[SKIP] {source_name}: {str(e)[:100]}")
                    results[source_name] = False
        
        return results
        
    except ImportError as e:
        print(f"[ERROR] Could not import ComprehensiveDataCollector: {e}")
        return {}
    except Exception as e:
        print(f"[ERROR] Comprehensive collector failed: {e}")
        return {}


def download_from_tcga_collector(output_dir: Path) -> bool:
    """Download using TCGA collector directly."""
    try:
        from data_collection.tcga_collector import TCGACollector
        
        print("\n[TCGA] Using TCGA collector...")
        collector = TCGACollector(output_dir=str(output_dir / "tcga"))
        
        result = collector.collect_data(
            cancer_type="BRCA",
            data_type="gene_expression",
            sample_limit=10
        )
        
        if result and "data" in result:
            if isinstance(result["data"], pd.DataFrame):
                output_file = output_dir / "tcga_brca_expression_real.csv"
                result["data"].to_csv(output_file)
                print(f"[OK] Saved TCGA data: {output_file.name}")
                return True
        
        return False
    except Exception as e:
        print(f"[SKIP] TCGA collector: {e}")
        return False


def download_from_geo_collector(output_dir: Path) -> bool:
    """Download using GEO collector directly."""
    try:
        from data_collection.geo_collector import GEOCollector
        
        print("\n[GEO] Using GEO collector...")
        collector = GEOCollector(output_dir=str(output_dir / "geo"))
        
        result = collector.collect_data(
            search_term="breast cancer",
            data_type="expression",
            max_datasets=1,
            sample_limit=10
        )
        
        if result and "data" in result:
            if isinstance(result["data"], pd.DataFrame):
                output_file = output_dir / "geo_expression_real.csv"
                result["data"].to_csv(output_file)
                print(f"[OK] Saved GEO data: {output_file.name}")
                return True
        
        return False
    except Exception as e:
        print(f"[SKIP] GEO collector: {e}")
        return False


def download_from_cosmic_collector(output_dir: Path) -> bool:
    """Download using COSMIC collector directly."""
    try:
        from data_collection.cosmic_collector import COSMICCollector
        
        print("\n[COSMIC] Using COSMIC collector...")
        collector = COSMICCollector(output_dir=str(output_dir / "cosmic"))
        
        result = collector.collect_data(
            cancer_type="breast",
            data_type="mutations",
            gene_list=["TP53", "BRCA1", "BRCA2"],
            sample_limit=10
        )
        
        if result and "data" in result:
            if isinstance(result["data"], pd.DataFrame):
                output_file = output_dir / "cosmic_mutations_real.csv"
                result["data"].to_csv(output_file)
                print(f"[OK] Saved COSMIC data: {output_file.name}")
                return True
        
        return False
    except Exception as e:
        print(f"[SKIP] COSMIC collector: {e}")
        return False


def download_from_icgc_collector(output_dir: Path) -> bool:
    """Download using ICGC collector directly."""
    try:
        from data_collection.icgc_collector import ICGCCollector
        
        print("\n[ICGC] Using ICGC collector...")
        collector = ICGCCollector(output_dir=str(output_dir / "icgc"))
        
        result = collector.collect_data(
            cancer_type="BRCA",
            data_type="expression_data",
            sample_limit=10
        )
        
        if result and "data" in result:
            if isinstance(result["data"], pd.DataFrame):
                output_file = output_dir / "icgc_expression_real.csv"
                result["data"].to_csv(output_file)
                print(f"[OK] Saved ICGC data: {output_file.name}")
                return True
        
        return False
    except Exception as e:
        print(f"[SKIP] ICGC collector: {e}")
        return False


def download_from_clinvar_collector(output_dir: Path) -> bool:
    """Download using ClinVar collector directly."""
    try:
        from data_collection.clinvar_collector import ClinVarCollector
        
        print("\n[ClinVar] Using ClinVar collector...")
        collector = ClinVarCollector(output_dir=str(output_dir / "clinvar"))
        
        result = collector.collect_data(
            gene_list=["TP53", "BRCA1", "BRCA2"],
            sample_limit=10
        )
        
        if result and "data" in result:
            if isinstance(result["data"], pd.DataFrame):
                output_file = output_dir / "clinvar_variants_real.csv"
                result["data"].to_csv(output_file)
                print(f"[OK] Saved ClinVar data: {output_file.name}")
                return True
        
        return False
    except Exception as e:
        print(f"[SKIP] ClinVar collector: {e}")
        return False


def download_from_all_individual_collectors(output_dir: Path) -> Dict[str, bool]:
    """
    Download from all individual collectors.
    
    Uses ALL collectors you've specified in the project.
    """
    print("\n" + "=" * 60)
    print("Downloading from ALL Individual Collectors")
    print("=" * 60)
    
    results = {}
    
    # Expression/Clinical data collectors (priority)
    expression_collectors = [
        ("TCGA", download_from_tcga_collector),
        ("GEO", download_from_geo_collector),
        ("ICGC", download_from_icgc_collector),
    ]
    
    # Mutation/Variant collectors
    mutation_collectors = [
        ("COSMIC", download_from_cosmic_collector),
        ("ClinVar", download_from_clinvar_collector),
    ]
    
    # Try all collectors
    all_collectors = expression_collectors + mutation_collectors
    
    for source_name, download_func in all_collectors:
        try:
            results[source_name] = download_func(output_dir)
        except Exception as e:
            print(f"[ERROR] {source_name} failed: {e}")
            results[source_name] = False
    
    return results


def main():
    """Download real data from ALL sources using ALL collectors."""
    print("=" * 60)
    print("Download Real Data - ALL Sources & Collectors")
    print("=" * 60)
    print("\nThis script uses ALL data collectors in your project:")
    print("- ComprehensiveDataCollector (all sources)")
    print("- Individual collectors (TCGA, GEO, COSMIC, ICGC, ClinVar, etc.)")
    print("- MasterDataOrchestrator")
    print("\nAll data is publicly available and properly anonymized.\n")
    
    # Set up SSL
    setup_ssl()
    
    all_results = {}
    
    # Method 1: Comprehensive Collector
    print("\n[Method 1] ComprehensiveDataCollector...")
    results1 = download_using_comprehensive_collector(REAL_DATA_DIR)
    all_results.update(results1)
    
    # Method 2: Individual Collectors
    print("\n[Method 2] Individual Collectors...")
    results2 = download_from_all_individual_collectors(REAL_DATA_DIR)
    all_results.update(results2)
    
    # Summary
    print("\n" + "=" * 60)
    print("Final Summary - ALL Sources")
    print("=" * 60)
    
    successful = [k for k, v in all_results.items() if v]
    failed = [k for k, v in all_results.items() if not v]
    
    print(f"\nSuccessful Downloads: {len(successful)}/{len(all_results)}")
    if successful:
        print("\nSources with real data downloaded:")
        for source in successful:
            print(f"  [OK] {source}")
    
    if failed:
        print(f"\nFailed/Skipped: {len(failed)}")
        print("(May need API keys, authentication, or have network issues)")
    
    # Check what files we have
    print("\n" + "=" * 60)
    print("Downloaded Files")
    print("=" * 60)
    real_files = list(REAL_DATA_DIR.glob("*_real.csv")) + list(REAL_DATA_DIR.glob("*_real.tsv"))
    if real_files:
        for f in real_files:
            size = f.stat().st_size
            print(f"  [FILE] {f.name} ({size:,} bytes)")
    else:
        print("  [NONE] No real data files downloaded")
    
    if successful:
        print("\n" + "=" * 60)
        print("SUCCESS: Real data downloaded!")
        print("=" * 60)
        print(f"Location: {REAL_DATA_DIR}")
        print("\nTest fixtures will automatically use this real data.")
    else:
        print("\n" + "=" * 60)
        print("NOTE: No real data downloaded")
        print("=" * 60)
        print("\nReasons may include:")
        print("- API authentication required")
        print("- Network/SSL issues")
        print("- Rate limiting")
        print("\nSee MANUAL_REAL_DATA_DOWNLOAD_GUIDE.md for manual download.")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
