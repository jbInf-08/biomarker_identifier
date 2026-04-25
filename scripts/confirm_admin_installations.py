#!/usr/bin/env python3
"""
Admin Installation Confirmation Script

This script presents a menu of tools that require admin permissions
and lets you choose which ones to install.
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

def check_admin_privileges():
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_command(command, description, shell=True):
    """Run a command and return success status."""
    try:
        print(f"🔄 {description}...")
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

def install_tool(tool_name, install_command, description):
    """Install a single tool."""
    print(f"\n📦 Installing {tool_name}...")
    print(f"Purpose: {description}")
    print(f"Command: {install_command}")
    
    response = input(f"\n   Install {tool_name}? (y/N): ")
    if response.lower() != 'y':
        print(f"⏭️  Skipping {tool_name}")
        return False
    
    if run_command(install_command, f"Installing {tool_name}"):
        print(f"✅ {tool_name} installed successfully")
        return True
    else:
        print(f"❌ {tool_name} installation failed")
        return False

def main():
    """Main confirmation function."""
    print("🚀 Admin-Required Tools Installation Confirmation")
    print("=" * 60)
    
    # Check if running on Windows
    if platform.system() != "Windows":
        print("❌ This script is designed for Windows.")
        return False
    
    # Check admin privileges
    if not check_admin_privileges():
        print("⚠️  WARNING: Not running as administrator!")
        print("   Please run this script as administrator for best results.")
        print("\n   To run as administrator:")
        print("   1. Right-click PowerShell/Command Prompt")
        print("   2. Select 'Run as administrator'")
        print("   3. Navigate to project directory")
        print("   4. Run this script again")
        return False
    
    print("✅ Running with administrator privileges")
    
    # Define tools with their installation commands
    tools = [
        {
            "name": "Git",
            "command": "winget install --id Git.Git",
            "description": "Version control system for code management",
            "check": "git --version"
        },
        {
            "name": "Docker Desktop",
            "command": "winget install --id Docker.DockerDesktop",
            "description": "Containerization platform for deployment",
            "check": "docker --version"
        },
        {
            "name": "PostgreSQL",
            "command": "winget install --id PostgreSQL.PostgreSQL",
            "description": "Database system for storing results",
            "check": "psql --version"
        },
        {
            "name": "Node.js",
            "command": "winget install --id OpenJS.NodeJS",
            "description": "JavaScript runtime for frontend development",
            "check": "node --version"
        },
        {
            "name": "Visual Studio Build Tools",
            "command": "winget install --id Microsoft.VisualStudio.2022.BuildTools",
            "description": "C++ compilation tools for Python packages",
            "check": "where cl"
        },
        {
            "name": "Chocolatey",
            "command": 'powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString(\'https://community.chocolatey.org/install.ps1\'))"',
            "description": "Windows package manager for easier installations",
            "check": "choco --version"
        },
        {
            "name": "Redis",
            "command": "choco install redis-64 -y",
            "description": "Caching and task queue system",
            "check": "redis-server --version"
        },
        {
            "name": "WSL (Windows Subsystem for Linux)",
            "command": "dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart",
            "description": "Linux environment for bioinformatics tools",
            "check": "wsl --version"
        }
    ]
    
    print(f"\n📋 Available tools for installation:")
    for i, tool in enumerate(tools, 1):
        status = "✅ Already installed" if check_tool_installed(tool["name"], tool["check"]) else "❌ Not installed"
        print(f"   {i}. {tool['name']}: {tool['description']} [{status}]")
    
    print(f"\n🔄 Installation options:")
    print(f"   a. Install all tools")
    print(f"   s. Select individual tools")
    print(f"   q. Quit without installing")
    
    choice = input(f"\n   Choose option (a/s/q): ").lower()
    
    if choice == 'q':
        print("👋 Installation cancelled")
        return False
    
    installed_count = 0
    
    if choice == 'a':
        print(f"\n🚀 Installing all tools...")
        for tool in tools:
            if not check_tool_installed(tool["name"], tool["check"]):
                if install_tool(tool["name"], tool["command"], tool["description"]):
                    installed_count += 1
            else:
                print(f"⏭️  {tool['name']} already installed, skipping")
    
    elif choice == 's':
        print(f"\n🎯 Select tools to install:")
        for i, tool in enumerate(tools, 1):
            if not check_tool_installed(tool["name"], tool["check"]):
                if install_tool(tool["name"], tool["command"], tool["description"]):
                    installed_count += 1
            else:
                print(f"⏭️  {tool['name']} already installed, skipping")
    
    # Final summary
    print(f"\n🎉 Installation process completed!")
    print(f"✅ Successfully installed: {installed_count} tools")
    
    if installed_count > 0:
        print(f"\n📋 Next steps:")
        print(f"   1. Restart your computer if Docker or WSL was installed")
        print(f"   2. Start Docker Desktop if installed")
        print(f"   3. Set up PostgreSQL database if installed")
        print(f"   4. Install frontend dependencies: cd frontend && npm install")
        print(f"   5. Test the installation: python tests/test_week5_python_only.py")
    
    return installed_count > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
