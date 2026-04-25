"""
Master Data Collection Orchestrator.

Coordinates data collection from all available sources.
"""

import asyncio
import concurrent.futures
from typing import Dict, List, Optional, Any
import json
import time
from pathlib import Path
import logging
from datetime import datetime

from .tcga_collector import TCGACollector
from .geo_collector import GEOCollector
from .cosmic_collector import COSMICCollector


class MasterDataOrchestrator:
    """
    Master orchestrator for collecting data from all sources.
    
    Manages parallel data collection, progress tracking, and result aggregation.
    """
    
    def __init__(self, 
                 output_dir: str = "data/external_sources",
                 max_workers: int = 4,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the master orchestrator.
        
        Args:
            output_dir: Base directory for all collected data
            max_workers: Maximum number of parallel workers
            config: Global configuration for all collectors
        """
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        self.config = config or {}
        
        # Setup logging
        self.logger = self._setup_logger()
        
        # Initialize collectors
        self.collectors = self._initialize_collectors()
        
        # Collection results
        self.results = {}
        self.collection_log = []
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger for the orchestrator."""
        logger = logging.getLogger("MasterDataOrchestrator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Create logs directory
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            # File handler
            file_handler = logging.FileHandler(logs_dir / "data_collection.log")
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
    
    def _initialize_collectors(self) -> Dict[str, Any]:
        """Initialize all available data collectors."""
        collectors = {}
        
        try:
            # TCGA Collector
            collectors["TCGA"] = TCGACollector(
                output_dir=str(self.output_dir / "tcga"),
                config=self.config.get("tcga", {})
            )
            
            # GEO Collector
            collectors["GEO"] = GEOCollector(
                output_dir=str(self.output_dir / "geo"),
                config=self.config.get("geo", {})
            )
            
            # COSMIC Collector
            collectors["COSMIC"] = COSMICCollector(
                output_dir=str(self.output_dir / "cosmic"),
                config=self.config.get("cosmic", {})
            )
            
            self.logger.info(f"Initialized {len(collectors)} data collectors")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize collectors: {e}")
            raise
            
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
                    "datasets": datasets[:5]  # Show first 5 datasets
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
        """
        Collect data from a specific source.
        
        Args:
            source_name: Name of the data source
            collection_params: Parameters for data collection
            
        Returns:
            Collection results
        """
        if source_name not in self.collectors:
            raise ValueError(f"Unknown data source: {source_name}")
        
        collector = self.collectors[source_name]
        
        try:
            self.logger.info(f"Starting data collection from {source_name}")
            start_time = time.time()
            
            # Run collection
            results = collector.run_collection(**collection_params)
            
            # Add source information
            results["source"] = source_name
            results["collection_time"] = time.time() - start_time
            
            # Log collection
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
            
            # Log failure
            self.collection_log.append({
                "timestamp": datetime.now().isoformat(),
                "source": source_name,
                "status": "failed",
                "error": str(e)
            })
            
            raise
    
    def collect_from_multiple_sources(self,
                                    collection_plan: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Collect data from multiple sources in parallel.
        
        Args:
            collection_plan: Dictionary mapping source names to collection parameters
            
        Returns:
            Aggregated collection results
        """
        self.logger.info(f"Starting parallel collection from {len(collection_plan)} sources")
        
        results = {}
        start_time = time.time()
        
        # Use ThreadPoolExecutor for parallel collection
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all collection tasks
            future_to_source = {
                executor.submit(self.collect_from_source, source, params): source
                for source, params in collection_plan.items()
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    result = future.result()
                    results[source] = result
                    self.logger.info(f"Completed collection from {source}")
                except Exception as e:
                    self.logger.error(f"Collection from {source} failed: {e}")
                    results[source] = {"error": str(e), "status": "failed"}
        
        # Generate summary
        total_time = time.time() - start_time
        summary = self._generate_collection_summary(results, total_time)
        
        # Save results
        self._save_collection_results(results, summary)
        
        return {
            "results": results,
            "summary": summary,
            "collection_log": self.collection_log
        }
    
    def _generate_collection_summary(self, 
                                   results: Dict[str, Any],
                                   total_time: float) -> Dict[str, Any]:
        """Generate summary of collection results."""
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
            "average_time_per_source": total_time / len(results) if results else 0
        }
    
    def _save_collection_results(self, 
                               results: Dict[str, Any],
                               summary: Dict[str, Any]):
        """Save collection results to file."""
        try:
            # Create results directory
            results_dir = self.output_dir / "collection_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Save detailed results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = results_dir / f"collection_results_{timestamp}.json"
            
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
            
            self.logger.info(f"Saved collection results to {results_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save collection results: {e}")
    
    def run_full_collection(self) -> Dict[str, Any]:
        """
        Run a comprehensive data collection from all sources.
        
        Returns:
            Complete collection results
        """
        self.logger.info("Starting full data collection from all sources")
        
        # Define collection plan for all sources
        collection_plan = {
            "TCGA": {
                "data_type": "gene_expression",
                "cancer_type": "BRCA",
                "sample_limit": 50
            },
            "GEO": {
                "search_term": "breast cancer",
                "data_type": "expression",
                "max_datasets": 3
            },
            "COSMIC": {
                "data_type": "mutations",
                "cancer_type": "breast",
                "gene_list": ["TP53", "BRCA1", "BRCA2", "EGFR", "KRAS"]
            }
        }
        
        return self.collect_from_multiple_sources(collection_plan)
    
    def get_collection_status(self) -> Dict[str, Any]:
        """Get current collection status and statistics."""
        return {
            "total_collections": len(self.collection_log),
            "successful_collections": len([l for l in self.collection_log if l["status"] == "success"]),
            "failed_collections": len([l for l in self.collection_log if l["status"] == "failed"]),
            "available_sources": list(self.collectors.keys()),
            "last_collection": self.collection_log[-1] if self.collection_log else None
        }


def main():
    """Main function for running data collection."""
    # Initialize orchestrator
    orchestrator = MasterDataOrchestrator(
        output_dir="data/external_sources",
        max_workers=3
    )
    
    # Get available sources
    print("Available data sources:")
    sources = orchestrator.get_available_sources()
    for source in sources:
        print(f"- {source['name']}: {source['datasets_count']} datasets")
    
    # Run full collection
    print("\nStarting full data collection...")
    results = orchestrator.run_full_collection()
    
    # Print summary
    summary = results["summary"]
    print(f"\nCollection Summary:")
    print(f"- Total sources: {summary['total_sources']}")
    print(f"- Successful: {summary['successful_sources']}")
    print(f"- Failed: {summary['failed_sources']}")
    print(f"- Total records: {summary['total_records_collected']}")
    print(f"- Total samples: {summary['total_samples_collected']}")
    print(f"- Total time: {summary['total_collection_time']:.2f} seconds")


if __name__ == "__main__":
    main()
