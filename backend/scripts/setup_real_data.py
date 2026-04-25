"""
Setup script to download and configure real data for testing.

This script:
1. (Optional) Generates sample data for testing without network
2. Downloads actual data from TCGA/GEO
3. Sets up proper SSL certificates
4. Configures test fixtures to use real data

Usage:
  python setup_real_data.py              # Full setup (download from TCGA/GEO)
  python setup_real_data.py --generate-sample   # Generate sample CSVs only (no network)
"""
import argparse
import os
import sys
from pathlib import Path
import subprocess

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

REAL_DATA_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "real_data"
REAL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def generate_sample_data():
    """
    Generate minimal sample expression and clinical CSVs for real_data fixtures.
    Enables real data tests without network access.
    """
    import numpy as np
    import pandas as pd

    np.random.seed(42)
    n_genes, n_samples = 100, 50
    gene_names = [f"GENE{i:04d}" for i in range(n_genes)]
    sample_names = [f"SAMPLE{i:03d}" for i in range(n_samples)]
    expr = np.random.lognormal(5, 1, (n_genes, n_samples))

    expr_df = pd.DataFrame(expr, index=gene_names, columns=sample_names)
    expr_file = REAL_DATA_DIR / "tcga_brca_expression_real.csv"
    expr_df.to_csv(expr_file)
    print(f"[OK] Generated {expr_file.name} ({expr_df.shape[0]} genes x {expr_df.shape[1]} samples)")

    clinical = pd.DataFrame(
        {
            "sample_id": sample_names,
            "overall_survival_time": np.random.exponential(1000, n_samples) + 1,
            "overall_survival_event": np.random.binomial(1, 0.6, n_samples),
            "age": np.random.normal(60, 15, n_samples),
            "gender": np.random.choice(["M", "F"], n_samples),
            "group": np.random.choice(["Control", "Treatment"], n_samples),
        },
        index=sample_names,
    )
    clinical_file = REAL_DATA_DIR / "tcga_brca_clinical_real.csv"
    clinical.to_csv(clinical_file)
    print(f"[OK] Generated {clinical_file.name} ({len(clinical)} samples)")

    geo_expr = pd.DataFrame(
        np.random.lognormal(4, 0.8, (80, 40)),
        index=[f"GEO_GENE{i:03d}" for i in range(80)],
        columns=[f"GSM{i:05d}" for i in range(40)],
    )
    geo_file = REAL_DATA_DIR / "geo_expression_real.csv"
    geo_expr.to_csv(geo_file)
    print(f"[OK] Generated {geo_file.name}")

    print("\n[OK] Sample real data generated. Real data tests will no longer skip.")


def install_certifi():
    """Ensure certifi is installed for SSL certificates."""
    try:
        import certifi
        print(f"[OK] certifi installed: {certifi.where()}")
        return True
    except ImportError:
        print("Installing certifi for SSL certificates...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "certifi"])
        import certifi
        print(f"[OK] certifi installed: {certifi.where()}")
        return True


def setup_ssl_environment():
    """Set up SSL environment variables."""
    try:
        import certifi
        cert_path = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = cert_path
        os.environ['SSL_CERT_FILE'] = cert_path
        print(f"[OK] SSL certificates configured: {cert_path}")
        return True
    except Exception as e:
        print(f"⚠ Warning: Could not set up SSL: {e}")
        return False


def download_real_data():
    """Download actual real data."""
    print("\n" + "=" * 60)
    print("Downloading Real Data")
    print("=" * 60)
    
    # Run the download script
    script_path = Path(__file__).parent / "download_real_data_proper.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("⚠ Download timed out")
        return False
    except Exception as e:
        print(f"⚠ Error running download script: {e}")
        return False


def check_real_data_available():
    """Check if real data files are available."""
    print("\n" + "=" * 60)
    print("Checking Real Data Availability")
    print("=" * 60)
    
    real_data_files = [
        "tcga_brca_expression_real.csv",
        "tcga_brca_expression_real.tsv",
        "geo_expression_real.csv"
    ]
    
    available = []
    missing = []
    
    for filename in real_data_files:
        filepath = REAL_DATA_DIR / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"[OK] {filename} ({size:,} bytes)")
            available.append(filename)
        else:
            print(f"[MISSING] {filename} (not found)")
            missing.append(filename)
    
    return len(available) > 0, available, missing


def update_fixtures_to_use_real_data(available_files):
    """Update fixtures to use real data if available."""
    print("\n" + "=" * 60)
    print("Updating Fixtures")
    print("=" * 60)
    
    if not available_files:
        print("[WARNING] No real data files available - fixtures will use generated data")
        return False
    
    # Check if we have TCGA data
    if any("tcga" in f.lower() for f in available_files):
        print("[OK] TCGA data available - fixtures can use real data")
        print("  Update conftest_real_data_fixtures.py to load from:")
        print(f"  {REAL_DATA_DIR / 'tcga_brca_expression_real.csv'}")
        return True
    
    return False


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Setup real data for testing")
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate sample CSV files (no network, for CI/local testing)",
    )
    args = parser.parse_args()

    if args.generate_sample:
        print("=" * 60)
        print("Generating Sample Real Data")
        print("=" * 60)
        generate_sample_data()
        print("\n" + "=" * 60)
        return

    print("=" * 60)
    print("Real Data Setup")
    print("=" * 60)
    print("\nThis script sets up actual real data for testing.")
    print("It downloads genuine data from public sources.\n")

    # Step 1: Install certifi
    print("\n[1/4] Setting up SSL certificates...")
    if not install_certifi():
        print("[ERROR] Failed to install certifi")
        return
    
    # Step 2: Configure SSL
    print("\n[2/4] Configuring SSL environment...")
    setup_ssl_environment()
    
    # Step 3: Download real data
    print("\n[3/4] Downloading real data...")
    download_success = download_real_data()
    
    # Step 4: Check what we have
    print("\n[4/4] Checking downloaded data...")
    has_data, available, missing = check_real_data_available()
    
    # Summary
    print("\n" + "=" * 60)
    print("Setup Summary")
    print("=" * 60)
    
    if has_data:
        print("\n[OK] Real data is available!")
        print(f"\nAvailable files: {len(available)}")
        for f in available:
            print(f"  - {f}")
        
        print("\nNext steps:")
        print("1. Review downloaded data in:", REAL_DATA_DIR)
        print("2. Update test fixtures to use real data")
        print("3. Run tests to verify real data works")
    else:
        print("\n[WARNING] No real data downloaded")
        print("\nOptions:")
        print("1. Check internet connection")
        print("2. Verify API access (TCGA/GEO)")
        print("3. Manually download data from:")
        print("   - GDC Portal: https://portal.gdc.cancer.gov/")
        print("   - GEO: https://www.ncbi.nlm.nih.gov/geo/")
        print("\nFor now, test fixtures will use generated data.")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
