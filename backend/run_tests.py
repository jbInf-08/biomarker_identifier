#!/usr/bin/env python3
"""
Test runner script for the Cancer Biomarker Identifier application.
"""
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {description}:")
        print(f"Return code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run tests for the Cancer Biomarker Identifier")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "e2e", "all"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage reporting"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Run with verbose output"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--markers",
        help="Run tests with specific markers (e.g., 'auth and not slow')"
    )
    parser.add_argument(
        "--file",
        help="Run specific test file"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test path based on type
    if args.type == "unit":
        cmd.append("tests/unit/")
    elif args.type == "integration":
        cmd.append("tests/integration/")
    elif args.type == "e2e":
        cmd.append("tests/e2e/")
    elif args.type == "all":
        cmd.append("tests/")
    
    # Add specific file if provided
    if args.file:
        cmd = ["python", "-m", "pytest", args.file]
    
    # Add coverage if requested
    if args.coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    # Add verbose output
    if args.verbose:
        cmd.append("-v")
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", "auto"])
    
    # Add markers
    if args.markers:
        cmd.extend(["-m", args.markers])
    
    # Add pytest configuration
    cmd.extend([
        "--tb=short",
        "--strict-markers",
        "--disable-warnings"
    ])
    
    # Run the tests
    success = run_command(cmd, f"Running {args.type} tests")
    
    if success:
        print(f"\n{'='*60}")
        print("✅ All tests passed successfully!")
        print(f"{'='*60}")
        
        if args.coverage:
            print("\n📊 Coverage report generated in htmlcov/index.html")
        
        return 0
    else:
        print(f"\n{'='*60}")
        print("❌ Tests failed!")
        print(f"{'='*60}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
