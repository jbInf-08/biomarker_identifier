"""
Base data collector framework for all data sources.
"""

import os
import json
import logging
import requests
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from datetime import datetime
import hashlib
import time
from urllib.parse import urljoin, urlparse, urlencode, urlsplit, urlunsplit, parse_qsl
import ssl
import certifi

# --- .env autoloading ---------------------------------------------------------
# The collectors read credentials from environment variables (OncoKB, COSMIC,
# NCBI, GDC, …).  Running `python -m data_collection.run_data_collection` from
# the repo root should pick up a repo-level `.env` automatically.  We try
# python-dotenv first (nice behaviour around quoted values and exports) and
# fall back to a tiny parser so this module works with a stock Python install.
def _load_dotenv_if_present() -> None:
    # Candidate .env paths, in order of precedence.
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",           # repo root
        Path(__file__).resolve().parents[1] / "backend" / ".env",
    ]
    try:
        from dotenv import load_dotenv  # type: ignore
        for p in candidates:
            if p.exists():
                load_dotenv(p, override=False)
        return
    except Exception:
        pass
    for p in candidates:
        try:
            if not p.exists():
                continue
            for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except Exception:
            # Never let a malformed .env break imports.
            continue


_load_dotenv_if_present()


class DataCollectorBase(ABC):
    """
    Abstract base class for all data collectors.
    
    Provides common functionality for authentication, rate limiting,
    error handling, and data validation.
    """
    
    def __init__(self, 
                 output_dir: str = "data/external_sources",
                 config: Optional[Dict[str, Any]] = None,
                 rate_limit_delay: float = 1.0,
                 max_retries: int = 3):
        """
        Initialize the data collector.
        
        Args:
            output_dir: Directory to save collected data
            config: Configuration dictionary with API keys, endpoints, etc.
            rate_limit_delay: Delay between requests in seconds
            max_retries: Maximum number of retry attempts
        """
        self.output_dir = Path(output_dir)
        self.config = config or {}
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.logger = self._setup_logger()
        self._install_ncbi_auth_hook()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup session with proper SSL context
        # Override any incorrect SSL_CERT_FILE environment variable
        try:
            import certifi
            cert_path = certifi.where()
            # Verify the path exists
            if os.path.exists(cert_path):
                # Set environment variable to override any incorrect paths
                os.environ['SSL_CERT_FILE'] = cert_path
                os.environ['REQUESTS_CA_BUNDLE'] = cert_path
                self.session.verify = cert_path
            else:
                # Fallback to True (use system default)
                self.session.verify = True
                self.logger.warning(f"Certifi path not found: {cert_path}, using system default")
        except (ImportError, Exception) as e:
            # Fallback to default verification if certifi not available
            self.session.verify = True
            self.logger.warning(f"Could not set certifi path: {e}, using system default")
        
        # Setup authentication if provided
        self._setup_authentication()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup logger for this collector."""
        logger = logging.getLogger(f"{self.__class__.__name__}")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _setup_authentication(self):
        """Setup authentication for the session."""
        # Override in subclasses for specific authentication methods
        pass

    def _install_ncbi_auth_hook(self) -> None:
        """
        Auto-attach NCBI_API_KEY / NCBI_EMAIL / NCBI_TOOL to every outgoing
        request to ``eutils.ncbi.nlm.nih.gov``.

        This means any collector that hits E-utilities (GEO, ClinVar, NCBI,
        PubMed, ICGC, …) gets the higher 10 req/s rate-limit automatically
        as long as NCBI_API_KEY is set — no per-collector plumbing needed.
        """
        api_key = os.environ.get("NCBI_API_KEY", "").strip()
        email = os.environ.get("NCBI_EMAIL", "").strip()
        tool = os.environ.get("NCBI_TOOL", "cancer-biomarker-identifier").strip()
        if not (api_key or email):
            return

        def _attach_auth(prepared_request, *args, **kwargs):
            # Runs once per request via Session.send; non-eutils URLs untouched.
            u = urlsplit(prepared_request.url)
            if "eutils.ncbi.nlm.nih.gov" not in (u.netloc or ""):
                return
            qs = dict(parse_qsl(u.query, keep_blank_values=True))
            if api_key and "api_key" not in qs:
                qs["api_key"] = api_key
            if email and "email" not in qs:
                qs["email"] = email
            if tool and "tool" not in qs:
                qs["tool"] = tool
            prepared_request.url = urlunsplit(
                (u.scheme, u.netloc, u.path, urlencode(qs, doseq=True), u.fragment)
            )

        # requests uses the "response" hook after a response, so we patch the
        # session.send method to mutate the prepared request before it flies.
        original_send = self.session.send

        def send(prepared_request, **send_kwargs):  # type: ignore[override]
            _attach_auth(prepared_request)
            return original_send(prepared_request, **send_kwargs)

        self.session.send = send  # type: ignore[assignment]
    
    def _make_request(self, 
                     url: str, 
                     method: str = "GET",
                     params: Optional[Dict] = None,
                     data: Optional[Dict] = None,
                     headers: Optional[Dict] = None,
                     timeout: int = 30) -> requests.Response:
        """
        Make HTTP request with retry logic and rate limiting.
        
        Args:
            url: Request URL
            method: HTTP method
            params: Query parameters
            data: Request body data
            headers: Request headers
            timeout: Request timeout
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If all retry attempts fail
        """
        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                if attempt > 0:
                    time.sleep(self.rate_limit_delay * (2 ** attempt))
                
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=timeout
                )
                
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                self.logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                    
        raise requests.RequestException("All retry attempts failed")
    
    def _save_data(self, 
                   data: Union[pd.DataFrame, Dict, List],
                   filename: str,
                   format: str = "auto") -> str:
        """
        Save data to file with automatic format detection.
        
        Args:
            data: Data to save
            filename: Output filename
            format: File format (auto, csv, tsv, json, parquet)
            
        Returns:
            Path to saved file
        """
        filepath = self.output_dir / filename
        
        if format == "auto":
            format = filepath.suffix[1:] if filepath.suffix else "csv"
        
        try:
            if isinstance(data, pd.DataFrame):
                if format in ["csv"]:
                    data.to_csv(filepath, index=False)
                elif format in ["tsv"]:
                    data.to_csv(filepath, sep='\t', index=False)
                elif format in ["parquet"]:
                    data.to_parquet(filepath, index=False)
                elif format in ["json"]:
                    data.to_json(filepath, orient='records', indent=2)
                else:
                    raise ValueError(f"Unsupported format for DataFrame: {format}")
                    
            elif isinstance(data, (dict, list)):
                if format in ["json"]:
                    with open(filepath, 'w') as f:
                        json.dump(data, f, indent=2, default=str)
                else:
                    raise ValueError(f"Unsupported format for dict/list: {format}")
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
                
            self.logger.info(f"Saved data to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save data to {filepath}: {e}")
            raise
    
    def _validate_data(self, data: Union[pd.DataFrame, Dict, List]) -> Dict[str, Any]:
        """
        Validate collected data and return quality metrics.
        
        Args:
            data: Data to validate
            
        Returns:
            Validation results dictionary
        """
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "data_type": type(data).__name__,
            "is_valid": True,
            "issues": [],
            "metrics": {}
        }
        
        try:
            if isinstance(data, pd.DataFrame):
                validation_results["metrics"] = {
                    "rows": len(data),
                    "columns": len(data.columns),
                    "missing_values": data.isnull().sum().sum(),
                    "duplicate_rows": data.duplicated().sum(),
                    "memory_usage": data.memory_usage(deep=True).sum()
                }
                
                # Check for common issues
                if data.empty:
                    validation_results["issues"].append("DataFrame is empty")
                    validation_results["is_valid"] = False
                    
                if data.isnull().sum().sum() > len(data) * 0.5:
                    validation_results["issues"].append("High percentage of missing values")
                    
            elif isinstance(data, (dict, list)):
                validation_results["metrics"] = {
                    "size": len(data),
                    "type": type(data).__name__
                }
                
                if not data:
                    validation_results["issues"].append("Data is empty")
                    validation_results["is_valid"] = False
                    
        except Exception as e:
            validation_results["issues"].append(f"Validation error: {str(e)}")
            validation_results["is_valid"] = False
            
        return validation_results
    
    def _generate_metadata(self, 
                          source: str,
                          data_type: str,
                          collection_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate metadata for collected data.
        
        Args:
            source: Data source name
            data_type: Type of data collected
            collection_params: Parameters used for collection
            
        Returns:
            Metadata dictionary
        """
        return {
            "source": source,
            "data_type": data_type,
            "collection_timestamp": datetime.now().isoformat(),
            "collector_version": "1.0.0",
            "collection_params": collection_params,
            "output_directory": str(self.output_dir)
        }
    
    @abstractmethod
    def collect_data(self, **kwargs) -> Dict[str, Any]:
        """
        Collect data from the source.
        
        This method must be implemented by subclasses.
        
        Returns:
            Dictionary containing collected data and metadata
        """
        pass
    
    @abstractmethod
    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """
        Get list of available datasets from the source.
        
        Returns:
            List of dataset information dictionaries
        """
        pass
    
    def run_collection(self, **kwargs) -> Dict[str, Any]:
        """
        Run the complete data collection process.
        
        Args:
            **kwargs: Collection parameters
            
        Returns:
            Collection results dictionary
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting data collection from {self.__class__.__name__}")
            
            # Collect data
            results = self.collect_data(**kwargs)
            
            # Validate data
            if "data" in results:
                validation = self._validate_data(results["data"])
                results["validation"] = validation
                
                if not validation["is_valid"]:
                    self.logger.warning(f"Data validation issues: {validation['issues']}")
            
            # Add collection metadata
            results["metadata"] = self._generate_metadata(
                source=self.__class__.__name__,
                data_type=results.get("data_type", "unknown"),
                collection_params=kwargs
            )
            
            # Add timing information
            results["collection_time"] = time.time() - start_time
            
            self.logger.info(f"Data collection completed in {results['collection_time']:.2f} seconds")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Data collection failed: {e}")
            raise
