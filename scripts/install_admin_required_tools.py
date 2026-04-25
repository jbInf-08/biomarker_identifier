#!/usr/bin/env python3
"""
Admin-Required Tools Installation Script

This script identifies and installs tools that require administrator privileges
for the biomarker identifier project.
"""

import os
import sys
import platform
import subprocess
import json
from pathlib import Path

def check_admin_privileges():
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_command(command, description, shell=True, check_output=False):
    """Run a command and return success status."""
    try:
        print(f"🔄 {description}...")
        if check_output:
            result = subprocess.run(command, shell=shell, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        else:
            result = subprocess.run(command, shell=shell, check=True)
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        return False
    except Exception as e:
        print(f"❌ {description} failed: {e}")
        return False

def check_tool_installed(tool_name, version_command):
    """Check if a tool is already installed."""
    try:
        result = subprocess.run(version_command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ {tool_name} already installed: {version}")
            return True
        else:
            print(f"❌ {tool_name} not found")
            return False
    except:
        print(f"❌ {tool_name} not found")
        return False

def install_git():
    """Install Git using winget."""
    if check_tool_installed("Git", "git --version"):
        return True
    
    print("\n📦 Installing Git...")
    print("Git is required for version control and cloning repositories.")
    
    # Try winget first
    if run_command("winget install --id Git.Git", "Installing Git via winget"):
        return True
    
    # Fallback to chocolatey
    if run_command("choco install git -y", "Installing Git via Chocolatey"):
        return True
    
    print("⚠️  Git installation failed. Please install manually:")
    print("   1. Download from: https://git-scm.com/downloads")
    print("   2. Run installer as administrator")
    return False

def install_docker():
    """Install Docker Desktop using winget."""
    if check_tool_installed("Docker", "docker --version"):
        return True
    
    print("\n🐳 Installing Docker Desktop...")
    print("Docker is required for containerization and deployment.")
    
    # Try winget first
    if run_command("winget install --id Docker.DockerDesktop", "Installing Docker Desktop via winget"):
        print("✅ Docker Desktop installed. Please restart your computer and start Docker Desktop.")
        return True
    
    # Fallback to chocolatey
    if run_command("choco install docker-desktop -y", "Installing Docker Desktop via Chocolatey"):
        print("✅ Docker Desktop installed. Please restart your computer and start Docker Desktop.")
        return True
    
    print("⚠️  Docker Desktop installation failed. Please install manually:")
    print("   1. Download from: https://www.docker.com/products/docker-desktop")
    print("   2. Run installer as administrator")
    print("   3. Restart computer after installation")
    return False

def install_postgresql():
    """Install PostgreSQL using winget."""
    if check_tool_installed("PostgreSQL", "psql --version"):
        return True
    
    print("\n🐘 Installing PostgreSQL...")
    print("PostgreSQL is required for the database backend.")
    
    # Try winget first
    if run_command("winget install --id PostgreSQL.PostgreSQL", "Installing PostgreSQL via winget"):
        print("✅ PostgreSQL installed. Please set up the database:")
        print("   1. Start PostgreSQL service")
        print("   2. Create database user and database")
        return True
    
    # Fallback to chocolatey
    if run_command("choco install postgresql -y", "Installing PostgreSQL via Chocolatey"):
        print("✅ PostgreSQL installed. Please set up the database:")
        print("   1. Start PostgreSQL service")
        print("   2. Create database user and database")
        return True
    
    print("⚠️  PostgreSQL installation failed. Please install manually:")
    print("   1. Download from: https://www.postgresql.org/download/")
    print("   2. Run installer as administrator")
    print("   3. Set up database and user")
    return False

def install_nodejs():
    """Install Node.js using winget."""
    if check_tool_installed("Node.js", "node --version"):
        return True
    
    print("\n🟢 Installing Node.js...")
    print("Node.js is required for the frontend React application.")
    
    # Try winget first
    if run_command("winget install --id OpenJS.NodeJS", "Installing Node.js via winget"):
        return True
    
    # Fallback to chocolatey
    if run_command("choco install nodejs -y", "Installing Node.js via Chocolatey"):
        return True
    
    print("⚠️  Node.js installation failed. Please install manually:")
    print("   1. Download from: https://nodejs.org/")
    print("   2. Run installer as administrator")
    return False

def install_visual_studio_build_tools():
    """Install Visual Studio Build Tools for C++ compilation."""
    print("\n🔨 Installing Visual Studio Build Tools...")
    print("Build Tools are required for compiling Python packages with C extensions.")
    
    # Try winget first
    if run_command("winget install --id Microsoft.VisualStudio.2022.BuildTools", "Installing VS Build Tools via winget"):
        return True
    
    # Fallback to chocolatey
    if run_command("choco install visualstudio2022buildtools -y", "Installing VS Build Tools via Chocolatey"):
        return True
    
    print("⚠️  Visual Studio Build Tools installation failed. Please install manually:")
    print("   1. Download from: https://visualstudio.microsoft.com/downloads/")
    print("   2. Install 'Build Tools for Visual Studio 2022'")
    print("   3. Include 'C++ build tools' workload")
    return False

def install_wsl():
    """Install Windows Subsystem for Linux (WSL)."""
    print("\n🐧 Installing Windows Subsystem for Linux (WSL)...")
    print("WSL is useful for running Linux-based bioinformatics tools.")
    
    # Enable WSL feature
    if run_command("dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart", "Enabling WSL feature"):
        # Install WSL 2
        if run_command("dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart", "Enabling Virtual Machine Platform"):
            print("✅ WSL features enabled. Please restart your computer.")
            print("   After restart, run: wsl --install")
            return True
    
    print("⚠️  WSL installation failed. Please install manually:")
    print("   1. Run as administrator: wsl --install")
    print("   2. Restart computer")
    return False

def install_chocolatey():
    """Install Chocolatey package manager."""
    if check_tool_installed("Chocolatey", "choco --version"):
        return True
    
    print("\n🍫 Installing Chocolatey...")
    print("Chocolatey is a Windows package manager for easier software installation.")
    
    # Install Chocolatey
    install_cmd = 'powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString(\'https://community.chocolatey.org/install.ps1\'))"'
    
    if run_command(install_cmd, "Installing Chocolatey"):
        print("✅ Chocolatey installed successfully")
        return True
    
    print("⚠️  Chocolatey installation failed. Please install manually:")
    print("   1. Open PowerShell as administrator")
    print("   2. Run the installation command from: https://chocolatey.org/install")
    return False

def install_redis():
    """Install Redis for caching and task queue."""
    if check_tool_installed("Redis", "redis-server --version"):
        return True
    
    print("\n🔴 Installing Redis...")
    print("Redis is required for caching and Celery task queue.")
    
    # Try chocolatey
    if run_command("choco install redis-64 -y", "Installing Redis via Chocolatey"):
        return True
    
    # Try winget
    if run_command("winget install --id Redis.Redis", "Installing Redis via winget"):
        return True
    
    print("⚠️  Redis installation failed. Please install manually:")
    print("   1. Download from: https://github.com/microsoftarchive/redis/releases")
    print("   2. Run installer as administrator")
    return False

def create_installation_summary(installed_tools):
    """Create a summary of installed tools."""
    summary = {
        "timestamp": str(Path().cwd()),
        "platform": platform.system(),
        "admin_privileges": check_admin_privileges(),
        "installed_tools": installed_tools,
        "next_steps": []
    }
    
    # Add next steps based on what was installed
    if "docker" in installed_tools:
        summary["next_steps"].append("Restart computer and start Docker Desktop")
    
    if "postgresql" in installed_tools:
        summary["next_steps"].append("Set up PostgreSQL database and user")
    
    if "wsl" in installed_tools:
        summary["next_steps"].append("Restart computer and run 'wsl --install'")
    
    if "nodejs" in installed_tools:
        summary["next_steps"].append("Install frontend dependencies: cd frontend && npm install")
    
    # Save summary
    with open("admin_tools_installation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n📄 Installation summary saved to: admin_tools_installation_summary.json")

def main():
    """Main installation function."""
    print("🚀 Admin-Required Tools Installation for Biomarker Identifier")
    print("=" * 70)
    
    # Check if running on Windows
    if platform.system() != "Windows":
        print("❌ This script is designed for Windows. Please install tools manually on your system.")
        return False
    
    # Check admin privileges
    if not check_admin_privileges():
        print("⚠️  WARNING: Not running as administrator!")
        print("   Some installations may fail without admin privileges.")
        print("   Please run this script as administrator for best results.")
        print("\n   To run as administrator:")
        print("   1. Right-click PowerShell/Command Prompt")
        print("   2. Select 'Run as administrator'")
        print("   3. Navigate to project directory")
        print("   4. Run this script again")
        
        response = input("\n   Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    print("✅ Running with administrator privileges")
    
    # List of tools to install
    tools_to_install = [
        ("Git", install_git, "Version control system"),
        ("Docker Desktop", install_docker, "Containerization platform"),
        ("PostgreSQL", install_postgresql, "Database system"),
        ("Node.js", install_nodejs, "JavaScript runtime for frontend"),
        ("Visual Studio Build Tools", install_visual_studio_build_tools, "C++ compilation tools"),
        ("Chocolatey", install_chocolatey, "Windows package manager"),
        ("Redis", install_redis, "Caching and task queue"),
        ("WSL", install_wsl, "Windows Subsystem for Linux"),
    ]
    
    installed_tools = []
    
    print(f"\n📋 Tools to install ({len(tools_to_install)} total):")
    for i, (name, _, description) in enumerate(tools_to_install, 1):
        print(f"   {i}. {name}: {description}")
    
    print(f"\n🔄 Starting installation process...")
    
    # Install each tool
    for name, install_func, description in tools_to_install:
        print(f"\n{'='*50}")
        print(f"Installing: {name}")
        print(f"Purpose: {description}")
        print(f"{'='*50}")
        
        if install_func():
            installed_tools.append(name.lower().replace(" ", "_"))
            print(f"✅ {name} installed successfully")
        else:
            print(f"❌ {name} installation failed")
    
    # Create installation summary
    create_installation_summary(installed_tools)
    
    # Final summary
    print(f"\n🎉 Installation process completed!")
    print(f"✅ Successfully installed: {len(installed_tools)} tools")
    print(f"❌ Failed installations: {len(tools_to_install) - len(installed_tools)} tools")
    
    if installed_tools:
        print(f"\n📦 Installed tools:")
        for tool in installed_tools:
            print(f"   ✅ {tool}")
    
    print(f"\n📋 Next steps:")
    print(f"   1. Restart your computer if Docker or WSL was installed")
    print(f"   2. Start Docker Desktop if installed")
    print(f"   3. Set up PostgreSQL database if installed")
    print(f"   4. Install frontend dependencies: cd frontend && npm install")
    print(f"   5. Test the installation: python tests/test_week5_python_only.py")
    
    return len(installed_tools) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
