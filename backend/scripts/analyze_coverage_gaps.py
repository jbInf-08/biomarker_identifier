#!/usr/bin/env python3
"""
Script to analyze coverage gaps and generate a report of uncovered code.

Usage:
    python scripts/analyze_coverage_gaps.py [--min-lines=5] [--output=coverage_gaps.md]
"""
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict


def parse_coverage_report(coverage_file: str = "coverage.xml") -> Dict[str, List[int]]:
    """Parse coverage XML report to extract uncovered lines."""
    uncovered = defaultdict(list)
    
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(coverage_file)
        root = tree.getroot()
        
        for package in root.findall(".//package"):
            for class_elem in package.findall(".//class"):
                filename = class_elem.get("filename")
                if not filename:
                    continue
                
                for line in class_elem.findall(".//line"):
                    hits = int(line.get("hits", 0))
                    if hits == 0:
                        line_num = int(line.get("number", 0))
                        uncovered[filename].append(line_num)
    except FileNotFoundError:
        print(f"Warning: {coverage_file} not found. Run coverage first.")
    except Exception as e:
        print(f"Error parsing coverage file: {e}")
    
    return uncovered


def analyze_uncovered_code(uncovered: Dict[str, List[int]], 
                          min_lines: int = 5) -> Dict[str, Dict]:
    """Analyze uncovered code and categorize by type."""
    analysis = defaultdict(lambda: {
        "total_uncovered": 0,
        "error_handlers": 0,
        "external_service": 0,
        "complex_conditionals": 0,
        "deprecated": 0,
        "other": 0,
        "examples": []
    })
    
    for filename, lines in uncovered.items():
        if len(lines) < min_lines:
            continue
        
        file_path = Path("backend") / filename
        if not file_path.exists():
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.readlines()
            
            analysis[filename]["total_uncovered"] = len(lines)
            
            for line_num in lines[:10]:  # Analyze first 10 uncovered lines
                if line_num > len(content):
                    continue
                
                line = content[line_num - 1]
                
                # Categorize
                if re.search(r'except|raise|Error|Exception', line):
                    analysis[filename]["error_handlers"] += 1
                    if len(analysis[filename]["examples"]) < 3:
                        analysis[filename]["examples"].append({
                            "line": line_num,
                            "code": line.strip()[:80]
                        })
                elif re.search(r'redis|celery|database|db\.|get_db', line, re.IGNORECASE):
                    analysis[filename]["external_service"] += 1
                elif re.search(r'if.*and.*or|if.*if.*if', line):
                    analysis[filename]["complex_conditionals"] += 1
                elif re.search(r'deprecated|legacy|old_|_old', line, re.IGNORECASE):
                    analysis[filename]["deprecated"] += 1
                else:
                    analysis[filename]["other"] += 1
        except Exception as e:
            print(f"Error analyzing {filename}: {e}")
    
    return analysis


def generate_report(analysis: Dict[str, Dict], output_file: str = "coverage_gaps.md"):
    """Generate markdown report of coverage gaps."""
    report = ["# Coverage Gap Analysis Report\n"]
    report.append(f"Generated: {Path(__file__).stat().st_mtime}\n\n")
    
    # Sort by total uncovered lines
    sorted_files = sorted(
        analysis.items(),
        key=lambda x: x[1]["total_uncovered"],
        reverse=True
    )
    
    report.append("## Files with Coverage Gaps\n\n")
    report.append("| File | Uncovered | Error Handlers | External Services | Complex Logic | Deprecated |\n")
    report.append("|------|-----------|----------------|-------------------|----------------|------------|\n")
    
    for filename, data in sorted_files[:20]:  # Top 20 files
        report.append(
            f"| `{filename}` | {data['total_uncovered']} | "
            f"{data['error_handlers']} | {data['external_service']} | "
            f"{data['complex_conditionals']} | {data['deprecated']} |\n"
        )
    
    report.append("\n## Detailed Analysis\n\n")
    
    for filename, data in sorted_files[:10]:  # Top 10 files
        report.append(f"### {filename}\n\n")
        report.append(f"- **Total Uncovered Lines**: {data['total_uncovered']}\n")
        report.append(f"- **Error Handlers**: {data['error_handlers']}\n")
        report.append(f"- **External Services**: {data['external_service']}\n")
        report.append(f"- **Complex Conditionals**: {data['complex_conditionals']}\n")
        report.append(f"- **Deprecated Code**: {data['deprecated']}\n")
        
        if data['examples']:
            report.append("\n**Example Uncovered Lines:**\n\n")
            for example in data['examples']:
                report.append(f"```python\n")
                report.append(f"# Line {example['line']}: {example['code']}\n")
                report.append(f"```\n\n")
    
    with open(output_file, 'w') as f:
        f.writelines(report)
    
    print(f"Report generated: {output_file}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze coverage gaps")
    parser.add_argument("--min-lines", type=int, default=5,
                       help="Minimum uncovered lines to report")
    parser.add_argument("--output", default="coverage_gaps.md",
                       help="Output file for report")
    parser.add_argument("--coverage-file", default="coverage.xml",
                       help="Coverage XML file to analyze")
    
    args = parser.parse_args()
    
    print("Analyzing coverage gaps...")
    uncovered = parse_coverage_report(args.coverage_file)
    
    if not uncovered:
        print("No uncovered code found or coverage file not available.")
        return
    
    print(f"Found {len(uncovered)} files with uncovered code")
    
    analysis = analyze_uncovered_code(uncovered, args.min_lines)
    generate_report(analysis, args.output)
    
    print(f"\nSummary:")
    print(f"- Files analyzed: {len(analysis)}")
    total_uncovered = sum(d["total_uncovered"] for d in analysis.values())
    print(f"- Total uncovered lines: {total_uncovered}")


if __name__ == "__main__":
    main()
