#!/usr/bin/env python3
"""
R and Dependencies Installation Script for Windows

This script installs R and all required dependencies for Week 5 functionality.
"""

import subprocess
import sys
import os
import platform
import urllib.request
import zipfile
import tempfile
from pathlib import Path
import shutil

def run_command(command, description, shell=True):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=shell, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False

def check_admin_privileges():
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def download_file(url, filename):
    """Download a file from URL."""
    try:
        print(f"🔄 Downloading {filename}...")
        urllib.request.urlretrieve(url, filename)
        print(f"✅ Downloaded {filename}")
        return True
    except Exception as e:
        print(f"❌ Failed to download {filename}: {e}")
        return False

def install_r_windows():
    """Install R on Windows."""
    print("🔄 Installing R on Windows...")
    
    # R download URL for Windows
    r_url = "https://cran.r-project.org/bin/windows/base/R-4.4.2-win.exe"
    r_installer = "R-4.4.2-win.exe"
    
    # Download R installer
    if not download_file(r_url, r_installer):
        return False
    
    # Install R silently
    install_cmd = f"{r_installer} /SILENT /DIR=C:\\Program Files\\R\\R-4.4.2"
    if not run_command(install_cmd, "Installing R"):
        return False
    
    # Add R to PATH
    r_path = "C:\\Program Files\\R\\R-4.4.2\\bin"
    current_path = os.environ.get('PATH', '')
    if r_path not in current_path:
        os.environ['PATH'] = f"{r_path};{current_path}"
        print(f"✅ Added R to PATH: {r_path}")
    
    # Clean up installer
    try:
        os.remove(r_installer)
        print("✅ Cleaned up R installer")
    except:
        pass
    
    return True

def install_r_packages():
    """Install required R packages."""
    print("🔄 Installing R packages...")
    
    # R commands to install packages
    r_commands = [
        # Install BiocManager
        "if (!requireNamespace('BiocManager', quietly = TRUE)) install.packages('BiocManager', repos = 'https://cran.rstudio.com/')",
        
        # Install Bioconductor packages
        "BiocManager::install(c('DESeq2', 'edgeR', 'limma'), update = FALSE, ask = FALSE)",
        
        # Install CRAN packages
        "install.packages(c('survival', 'survminer', 'ggplot2', 'dplyr', 'devtools'), repos = 'https://cran.rstudio.com/')",
        
        # Install additional packages
        "install.packages(c('RColorBrewer', 'pheatmap', 'VennDiagram'), repos = 'https://cran.rstudio.com/')"
    ]
    
    for i, cmd in enumerate(r_commands, 1):
        r_cmd = f'R -e "{cmd}"'
        if not run_command(r_cmd, f"Installing R packages (step {i}/{len(r_commands)})"):
            print(f"⚠️  Warning: R package installation step {i} failed")
    
    return True

def install_python_dependencies():
    """Install Python dependencies with SSL workaround."""
    print("🔄 Installing Python dependencies...")
    
    # Clear SSL environment variables
    os.environ.pop('SSL_CERT_FILE', None)
    os.environ.pop('REQUESTS_CA_BUNDLE', None)
    
    # Trusted hosts for pip
    trusted_hosts = [
        '--trusted-host', 'pypi.org',
        '--trusted-host', 'pypi.python.org',
        '--trusted-host', 'files.pythonhosted.org'
    ]
    
    # Core dependencies
    core_packages = [
        'pandas', 'numpy', 'scipy', 'scikit-learn', 
        'matplotlib', 'seaborn', 'pyyaml', 'requests'
    ]
    
    # Week 5 specific dependencies
    week5_packages = [
        'lifelines', 'networkx', 'scikit-survival', 
        'anndata', 'scanpy', 'igraph', 'rpy2'
    ]
    
    # Install core packages
    core_cmd = [sys.executable, '-m', 'pip', 'install'] + trusted_hosts + core_packages
    if not run_command(core_cmd, "Installing core Python packages"):
        print("⚠️  Warning: Some core packages failed to install")
    
    # Install Week 5 packages
    week5_cmd = [sys.executable, '-m', 'pip', 'install'] + trusted_hosts + week5_packages
    if not run_command(week5_cmd, "Installing Week 5 Python packages"):
        print("⚠️  Warning: Some Week 5 packages failed to install")
    
    return True

def verify_installation():
    """Verify the installation."""
    print("🔄 Verifying installation...")
    
    # Check R installation
    if not run_command("R --version", "Checking R installation"):
        print("❌ R installation verification failed")
        return False
    
    # Check Python packages
    test_imports = [
        ("pandas", "Data processing"),
        ("numpy", "Numerical computing"),
        ("scipy", "Scientific computing"),
        ("sklearn", "Machine learning"),
        ("lifelines", "Survival analysis"),
        ("matplotlib", "Visualization"),
        ("seaborn", "Statistical visualization"),
        ("networkx", "Network analysis"),
        ("rpy2", "R integration")
    ]
    
    failed_imports = []
    for module, description in test_imports:
        try:
            __import__(module)
            print(f"✅ {description} ({module})")
        except ImportError as e:
            print(f"❌ {description} ({module}): {e}")
            failed_imports.append(module)
    
    # Test R integration
    try:
        import rpy2.robjects as ro
        ro.r('library(DESeq2)')
        print("✅ R integration with DESeq2")
    except Exception as e:
        print(f"❌ R integration test failed: {e}")
        failed_imports.append("rpy2_integration")
    
    if failed_imports:
        print(f"\n⚠️  Warning: {len(failed_imports)} modules failed verification: {', '.join(failed_imports)}")
        return False
    else:
        print("\n✅ All modules verified successfully!")
        return True

def create_environment_setup():
    """Create environment setup script."""
    setup_script = """@echo off
REM Environment setup for Week 5 dependencies

REM Add R to PATH
set PATH=C:\\Program Files\\R\\R-4.4.2\\bin;%PATH%

REM Clear SSL environment variables
set SSL_CERT_FILE=
set REQUESTS_CA_BUNDLE=

REM Set R environment variables
set R_HOME=C:\\Program Files\\R\\R-4.4.2
set R_LIBS_USER=C:\\Users\\%USERNAME%\\Documents\\R\\win-library\\4.4

echo Environment setup complete!
echo R is now available in PATH
echo SSL issues resolved
"""
    
    with open("setup_week5_env.bat", "w") as f:
        f.write(setup_script)
    
    print("✅ Created setup_week5_env.bat for environment setup")

def main():
    """Main installation function."""
    print("🚀 R and Dependencies Installation for Week 5")
    print("=" * 60)
    
    # Check if running on Windows
    if platform.system() != "Windows":
        print("❌ This script is designed for Windows. Please install R manually on your system.")
        return False
    
    # Check admin privileges
    if not check_admin_privileges():
        print("⚠️  Warning: Not running as administrator. R installation may fail.")
        print("   Please run this script as administrator for best results.")
    
    # Install R
    if not install_r_windows():
        print("❌ R installation failed")
        return False
    
    # Install R packages
    if not install_r_packages():
        print("⚠️  Warning: Some R packages failed to install")
    
    # Install Python dependencies
    if not install_python_dependencies():
        print("❌ Python dependency installation failed")
        return False
    
    # Verify installation
    if not verify_installation():
        print("⚠️  Warning: Installation verification failed")
        print("   Some components may not be working correctly")
    
    # Create environment setup script
    create_environment_setup()
    
    print("\n🎉 Installation completed!")
    print("\nNext steps:")
    print("1. Restart your terminal/PowerShell")
    print("2. Run: setup_week5_env.bat (to set environment variables)")
    print("3. Test: python tests/test_week5_simple.py")
    print("4. Start: python backend/app/main.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
