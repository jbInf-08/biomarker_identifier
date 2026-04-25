"""
Comprehensive Data Collection Runner.

This script runs data collection from all available sources with proper
configuration, error handling, and progress tracking.
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

# Importing base_collector triggers ``_load_dotenv_if_present`` — so env vars
# defined in a top-level ``.env`` (OncoKB / COSMIC / NCBI / GDC tokens) are
# available to every collector below without extra wiring.
from . import base_collector  # noqa: F401  (side-effect import)

# Import all collectors
from .tcga_collector import TCGACollector
from .geo_collector import GEOCollector
from .cosmic_collector import COSMICCollector
from .icgc_collector import ICGCCollector
from .ega_collector import EGACollector
from .tcia_collector import TCIACollector
from .gdc_collector import GDCCollector
from .cdc_collector import CDCCollector
from .nih_collector import NIHCollector
from .kaggle_collector import KaggleCollector
from .nci_collector import NCICollector
from .pubmed_collector import PubMedCollector
from .ncbi_collector import NCBICollector
from .miccai_collector import MICCAICollector
from .nih_clinical_collector import NIHClinicalCollector
from .prostate_x_collector import ProstateXCollector
from .pathlaion_collector import PathLAIONCollector
from .camelyon_collector import CAMELYONCollector
from .pancancer_atlas_collector import PanCancerAtlasCollector
from .seer_collector import SEERCollector
from .ncdb_collector import NCDBCollector
from .mimic_collector import MIMICCollector
from .wisconsin_breast_cancer_collector import WisconsinBreastCancerCollector
from .ddsm_collector import DDSMCollector
from .inbreast_collector import INbreastCollector
from .lidc_idri_collector import LIDCIDRICollector
from .nsclc_radiogenomics_collector import NSCLCRadiogenomicsCollector
from .luna16_collector import Luna16Collector
from .isic_collector import ISICCollector
from .ham10000_collector import HAM10000Collector
from .brats_collector import BraTSCollector
from .rembrandt_collector import REMBRANDTCollector
from .tcia_glioblastoma_collector import TCIAGlioblastomaCollector
from .clinvar_collector import ClinVarCollector
from .oncokb_collector import OncoKBCollector
from .cbioportal_collector import cBioPortalCollector
from .firecloud_terra_collector import FireCloudTerraCollector
from .google_cloud_healthcare_collector import GoogleCloudHealthcareCollector
from .ccle_collector import CCLECollector
from .gdsc_collector import GDSCCollector
from .nci_60_collector import NCI60Collector


class ComprehensiveDataCollector:
    """
    Comprehensive data collector that manages all data sources.
    """
    
    def __init__(self, 
                 output_dir: str = "data/external_sources",
                 config_file: Optional[str] = None,
                 max_workers: int = 4):
        """
        Initialize the comprehensive data collector.
        
        Args:
            output_dir: Base directory for collected data
            config_file: Path to configuration file
            max_workers: Maximum number of parallel workers
        """
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.config = self._load_config(config_file)
        
        # Setup logging
        self.logger = self._setup_logger()
        
        # Report which credentials were picked up — ``.env`` has already been
        # loaded via ``base_collector`` at import time.  We only check *presence*
        # here; the preflight command validates shape / performs test calls.
        self._log_credentials_overview()

        # Initialize all collectors
        self.collectors = self._initialize_all_collectors()

        # Collection results
        self.results = {}
        self.collection_log = []

    def _log_credentials_overview(self) -> None:
        """Log which optional credentials are present (masked)."""
        def _present(name: str) -> str:
            val = os.environ.get(name, "").strip()
            if not val:
                return f"  {name:<26} (missing)"
            masked = val[:4] + "…" + val[-2:] if len(val) > 8 else "set"
            return f"  {name:<26} {masked}"

        lines = [
            "Credential overview (masked):",
            _present("ONCOKB_API_TOKEN"),
            _present("ONCOKB_API_KEY"),
            _present("COSMIC_API_EMAIL"),
            _present("COSMIC_API_KEY"),
            _present("NCBI_API_KEY"),
            _present("NCBI_EMAIL"),
            _present("GDC_API_TOKEN"),
            _present("KAGGLE_USERNAME"),
            _present("KAGGLE_KEY"),
        ]
        for line in lines:
            self.logger.info(line)
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file."""
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "tcga": {
                "sample_limit": 100,
                "cancer_types": ["BRCA", "LUAD", "COAD", "PRAD"]
            },
            "geo": {
                "max_datasets": 5,
                "search_terms": ["breast cancer", "lung cancer", "prostate cancer"]
            },
            "cosmic": {
                "gene_list": ["TP53", "BRCA1", "BRCA2", "EGFR", "KRAS", "MYC", "RB1", "PTEN"],
                "cancer_types": ["breast", "lung", "prostate", "colorectal"]
            },
            "general": {
                "sample_limit": 50,
                "rate_limit_delay": 1.0,
                "max_retries": 3
            }
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Setup comprehensive logging."""
        logger = logging.getLogger("ComprehensiveDataCollector")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Create logs directory
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            # File handler
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_handler = logging.FileHandler(logs_dir / f"data_collection_{timestamp}.log")
            file_handler.setLevel(logging.INFO)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            
        return logger
    
    def _initialize_all_collectors(self) -> Dict[str, Any]:
        """Initialize all available collectors."""
        collectors = {}
        
        # Define all collector classes
        collector_classes = {
            "TCGA": TCGACollector,
            "GEO": GEOCollector,
            "COSMIC": COSMICCollector,
            "ICGC": ICGCCollector,
            "EGA": EGACollector,
            "TCIA": TCIACollector,
            "GDC": GDCCollector,
            "CDC": CDCCollector,
            "NIH": NIHCollector,
            "Kaggle": KaggleCollector,
            "NCI": NCICollector,
            "PubMed": PubMedCollector,
            "NCBI": NCBICollector,
            "MICCAI": MICCAICollector,
            "NIH_Clinical": NIHClinicalCollector,
            "Prostate_X": ProstateXCollector,
            "PathLAION": PathLAIONCollector,
            "CAMELYON": CAMELYONCollector,
            "PanCancer_Atlas": PanCancerAtlasCollector,
            "SEER": SEERCollector,
            "NCDB": NCDBCollector,
            "MIMIC": MIMICCollector,
            "Wisconsin_Breast_Cancer": WisconsinBreastCancerCollector,
            "DDSM": DDSMCollector,
            "INbreast": INbreastCollector,
            "LIDC_IDRI": LIDCIDRICollector,
            "NSCLC_Radiogenomics": NSCLCRadiogenomicsCollector,
            "Luna16": Luna16Collector,
            "ISIC": ISICCollector,
            "HAM10000": HAM10000Collector,
            "BraTS": BraTSCollector,
            "REMBRANDT": REMBRANDTCollector,
            "TCIA_Glioblastoma": TCIAGlioblastomaCollector,
            "ClinVar": ClinVarCollector,
            "OncoKB": OncoKBCollector,
            "cBioPortal": cBioPortalCollector,
            "FireCloud_Terra": FireCloudTerraCollector,
            "Google_Cloud_Healthcare": GoogleCloudHealthcareCollector,
            "CCLE": CCLECollector,
            "GDSC": GDSCCollector,
            "NCI_60": NCI60Collector
        }
        
        # Initialize collectors
        for name, collector_class in collector_classes.items():
            try:
                collector_config = self.config.get(name.lower(), self.config.get("general", {}))
                collectors[name] = collector_class(
                    output_dir=str(self.output_dir / name.lower()),
                    config=collector_config
                )
                self.logger.info(f"Initialized {name} collector")
            except Exception as e:
                self.logger.warning(f"Failed to initialize {name} collector: {e}")
        
        self.logger.info(f"Initialized {len(collectors)} collectors")
        return collectors
    
    def get_available_sources(self) -> List[Dict[str, Any]]:
        """Get list of all available data sources."""
        sources = []
        
        for name, collector in self.collectors.items():
            try:
                datasets = collector.get_available_datasets()
                sources.append({
                    "name": name,
                    "collector": collector.__class__.__name__,
                    "datasets_count": len(datasets),
                    "datasets": datasets[:3]  # Show first 3 datasets
                })
            except Exception as e:
                self.logger.warning(f"Failed to get datasets from {name}: {e}")
                sources.append({
                    "name": name,
                    "collector": collector.__class__.__name__,
                    "datasets_count": 0,
                    "error": str(e)
                })
        
        return sources
    
    def collect_from_source(self, 
                          source_name: str,
                          collection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Collect data from a specific source."""
        if source_name not in self.collectors:
            raise ValueError(f"Unknown data source: {source_name}")
        
        collector = self.collectors[source_name]
        
        try:
            self.logger.info(f"Starting data collection from {source_name}")
            start_time = time.time()
            
            results = collector.run_collection(**collection_params)
            results["source"] = source_name
            results["collection_time"] = time.time() - start_time
            
            self.collection_log.append({
                "timestamp": datetime.now().isoformat(),
                "source": source_name,
                "status": "success",
                "collection_time": results["collection_time"],
                "records_collected": results.get("records_collected", 0),
                "samples_collected": results.get("samples_collected", 0)
            })
            
            self.logger.info(f"Successfully collected data from {source_name}")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to collect data from {source_name}: {e}")
            self.collection_log.append({
                "timestamp": datetime.now().isoformat(),
                "source": source_name,
                "status": "failed",
                "error": str(e)
            })
            raise
    
    def run_comprehensive_collection(self, 
                                   sources: Optional[List[str]] = None,
                                   data_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run comprehensive data collection from all or selected sources.
        
        Args:
            sources: List of source names to collect from (None for all)
            data_types: List of data types to collect (None for all)
            
        Returns:
            Comprehensive collection results
        """
        if sources is None:
            sources = list(self.collectors.keys())
        
        if data_types is None:
            data_types = ["clinical", "expression", "mutation", "copy_number", "methylation"]
        
        self.logger.info(f"Starting comprehensive collection from {len(sources)} sources")
        
        # Create collection plan
        collection_plan = {}
        for source in sources:
            if source in self.collectors:
                # Get default parameters for this source
                source_config = self.config.get(source.lower(), {})
                
                # Create collection parameters
                params = {
                    "sample_limit": source_config.get("sample_limit", 50),
                    "data_type": data_types[0] if data_types else "clinical"
                }
                
                # Add source-specific parameters
                if source == "TCGA":
                    params.update({
                        "cancer_type": source_config.get("cancer_types", ["BRCA"])[0],
                        "data_type": "gene_expression"
                    })
                elif source == "GEO":
                    params.update({
                        "search_term": source_config.get("search_terms", ["cancer"])[0],
                        "data_type": "expression",
                        "max_datasets": source_config.get("max_datasets", 3),
                        "series_list": source_config.get("series_list", []),
                    })
                elif source == "COSMIC":
                    params.update({
                        "data_type": "mutations",
                        "cancer_type": source_config.get("cancer_types", ["breast"])[0],
                        "gene_list": source_config.get("gene_list", ["TP53", "BRCA1", "BRCA2"])
                    })
                elif source == "GDC":
                    params.update({
                        "data_type": "cases",
                        "size": min(int(source_config.get("sample_limit", 50)), 500),
                        "project": source_config.get("project", "TCGA-BRCA"),
                    })
                    params.pop("sample_limit", None)
                elif source == "ICGC":
                    params.update({
                        "data_type": "bioproject_index",
                        "sample_limit": min(int(source_config.get("sample_limit", 25)), 200),
                        "term": source_config.get("search_term", "ICGC cancer"),
                    })
                elif source == "ClinVar":
                    params.update({
                        "data_type": "genetic_variants",
                        "gene_symbol": source_config.get("gene_symbol", "TP53"),
                        "max_records": min(int(source_config.get("max_records", 100)), 500),
                    })
                    params.pop("sample_limit", None)
                elif source == "OncoKB":
                    params.update({
                        "data_type": "cancer_genes",
                    })
                    params.pop("sample_limit", None)
                elif source == "NCBI":
                    params.update({
                        "data_type": "gene",
                        "gene_symbol": source_config.get("gene_symbol", "TP53"),
                        "max_ids": min(int(source_config.get("max_ids", 10)), 50),
                    })
                elif source == "PubMed":
                    params.update({
                        "data_type": "literature",
                        "query": source_config.get("query", "cancer biomarker review"),
                        "max_records": min(int(source_config.get("max_records", 15)), 100),
                    })
                elif source == "cBioPortal":
                    params.update({
                        "data_type": "cancer_types",
                        "page_size": min(int(source_config.get("page_size", 50)), 200),
                    })
                elif source == "CCLE":
                    params.update({
                        "data_type": "cell_line_data",
                        "max_samples": min(int(source_config.get("max_samples", 500)), 5000),
                    })
                elif source == "GDSC":
                    params.update({
                        "data_type": "drug_annotation",
                        "max_rows": min(int(source_config.get("max_rows", 400)), 5000),
                    })
                
                collection_plan[source] = params
        
        # Run collection
        results = {}
        start_time = time.time()
        
        for source, params in collection_plan.items():
            try:
                result = self.collect_from_source(source, params)
                results[source] = result
            except Exception as e:
                self.logger.error(f"Collection from {source} failed: {e}")
                results[source] = {"error": str(e), "status": "failed"}
        
        # Generate summary
        total_time = time.time() - start_time
        summary = self._generate_summary(results, total_time)
        
        # Save results
        self._save_results(results, summary)
        
        return {
            "results": results,
            "summary": summary,
            "collection_log": self.collection_log
        }
    
    def _generate_summary(self, results: Dict[str, Any], total_time: float) -> Dict[str, Any]:
        """Generate collection summary."""
        successful_sources = [s for s, r in results.items() if "error" not in r]
        failed_sources = [s for s, r in results.items() if "error" in r]
        
        total_records = sum(
            r.get("records_collected", 0) for r in results.values() 
            if "error" not in r
        )
        
        total_samples = sum(
            r.get("samples_collected", 0) for r in results.values() 
            if "error" not in r
        )
        
        return {
            "total_sources": len(results),
            "successful_sources": len(successful_sources),
            "failed_sources": len(failed_sources),
            "successful_source_names": successful_sources,
            "failed_source_names": failed_sources,
            "total_records_collected": total_records,
            "total_samples_collected": total_samples,
            "total_collection_time": total_time,
            "average_time_per_source": total_time / len(results) if results else 0,
            "collection_timestamp": datetime.now().isoformat()
        }
    
    def _save_results(self, results: Dict[str, Any], summary: Dict[str, Any]):
        """Save collection results."""
        try:
            results_dir = self.output_dir / "collection_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save detailed results
            results_file = results_dir / f"comprehensive_collection_{timestamp}.json"
            with open(results_file, 'w') as f:
                json.dump({
                    "results": results,
                    "summary": summary,
                    "collection_log": self.collection_log
                }, f, indent=2, default=str)
            
            # Save summary
            summary_file = results_dir / f"collection_summary_{timestamp}.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.logger.info(f"Saved results to {results_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")


def main():
    """Main function for running comprehensive data collection."""
    parser = argparse.ArgumentParser(description="Comprehensive Data Collection Runner")
    parser.add_argument("--output-dir", default="data/external_sources", 
                       help="Output directory for collected data")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--sources", nargs="+", help="Specific sources to collect from")
    parser.add_argument("--data-types", nargs="+", help="Specific data types to collect")
    parser.add_argument("--max-workers", type=int, default=4, 
                       help="Maximum number of parallel workers")
    parser.add_argument("--list-sources", action="store_true",
                       help="List available sources and exit")
    parser.add_argument("--preflight", action="store_true",
                       help="Check which sources have their credentials set (no downloads).")
    parser.add_argument("--probe", action="store_true",
                       help="With --preflight, make a tiny live call to each API.")

    args = parser.parse_args()

    # Preflight: cheap, no collectors instantiated, works without the heavy
    # import path of the orchestrator below.
    if args.preflight:
        from . import preflight
        results = preflight.run(args.sources, probe=args.probe)
        print(preflight.format_table(results))
        # Hard-fail on missing credentials only if the user explicitly listed sources.
        if args.sources:
            missing = [r for r in results if r.status == "missing"]
            return 1 if missing else 0
        return 0
    
    # Initialize collector
    collector = ComprehensiveDataCollector(
        output_dir=args.output_dir,
        config_file=args.config,
        max_workers=args.max_workers
    )
    
    # List sources if requested
    if args.list_sources:
        sources = collector.get_available_sources()
        print("Available data sources:")
        for source in sources:
            print(f"  {source['name']}: {source['datasets_count']} datasets")
        return
    
    # Run collection
    print("Starting comprehensive data collection...")
    results = collector.run_comprehensive_collection(
        sources=args.sources,
        data_types=args.data_types
    )
    
    # Print summary
    summary = results["summary"]
    print(f"\nCollection Summary:")
    print(f"  Total sources: {summary['total_sources']}")
    print(f"  Successful: {summary['successful_sources']}")
    print(f"  Failed: {summary['failed_sources']}")
    print(f"  Total records: {summary['total_records_collected']}")
    print(f"  Total samples: {summary['total_samples_collected']}")
    print(f"  Total time: {summary['total_collection_time']:.2f} seconds")
    
    if summary['failed_sources'] > 0:
        print(f"\nFailed sources: {', '.join(summary['failed_source_names'])}")


if __name__ == "__main__":
    rc = main()
    if isinstance(rc, int):
        raise SystemExit(rc)
