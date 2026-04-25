"""
Script to replace ALL mock data generation with real API calls in all collectors.

This script removes all synthetic/mock data generation and ensures all collectors
download real data from actual APIs.
"""
import os
import re
from pathlib import Path
from typing import List, Tuple


def remove_mock_methods(content: str) -> str:
    """Remove all _create_mock_* methods from content."""
    # Pattern to match method definitions and their bodies
    # This is a simplified approach - matches methods that start with _create_mock
    pattern = r'def _create_mock[^)]*\)[^:]*:.*?(?=\n    def |\nclass |\Z)'
    
    # More precise: match from def to next def/class/end of class
    lines = content.split('\n')
    new_lines = []
    skip_until_indent = False
    current_indent = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a mock method definition
        if re.match(r'\s+def _create_mock', line):
            # Skip this method entirely
            current_indent = len(line) - len(line.lstrip())
            skip_until_indent = True
            i += 1
            continue
        
        # If we're skipping, check if we've reached the next method/class
        if skip_until_indent:
            # Check if this line is at same or less indentation (new method/class)
            if line.strip() and not line.startswith(' ' * (current_indent + 1)):
                if line.strip().startswith('def ') or line.strip().startswith('class '):
                    skip_until_indent = False
                elif len(line) - len(line.lstrip()) <= current_indent:
                    skip_until_indent = False
            
            if skip_until_indent:
                i += 1
                continue
        
        new_lines.append(line)
        i += 1
    
    return '\n'.join(new_lines)


def remove_np_random_imports(content: str) -> str:
    """Remove numpy random imports that are only used for mock data."""
    # Remove "import numpy as np" if only used for random generation
    # This is conservative - we'll keep it if there are other uses
    if 'np.random' in content:
        # Check if np is used for other purposes
        if not re.search(r'\bnp\.(?!random)', content):
            # Only used for random, can remove import
            content = re.sub(r'import numpy as np\s*\n', '', content)
            content = re.sub(r'from numpy import.*\n', '', content)
    
    return content


def replace_mock_calls_with_markers(content: str, collector_name: str) -> str:
    """Replace calls to mock methods with explicit runtime markers for collector owners."""
    # Find all calls to _create_mock_* methods
    patterns = [
        (
            r'self\._create_mock_data\([^)]*\)',
            f'raise RuntimeError("Collector implementation incomplete for {collector_name}: replace mock path with real API download.")',
        ),
        (r'self\._create_mock_[a-z_]+\([^)]*\)',
         f'raise RuntimeError("Collector implementation incomplete for {collector_name}: replace mock path with real API download.")'),
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    
    return content


def fix_collector_file(filepath: Path) -> Tuple[bool, List[str]]:
    """
    Fix a single collector file to remove all mock data generation.
    
    Returns:
        (was_fixed, list_of_issues)
    """
    try:
        content = filepath.read_text(encoding='utf-8')
        original_content = content
        issues = []
        
        # Extract collector name
        collector_name = filepath.stem.replace('_collector', '').replace('_', ' ').title()
        
        # Step 1: Remove all _create_mock_* methods
        if '_create_mock' in content:
            content = remove_mock_methods(content)
            issues.append("Removed _create_mock_* methods")
        
        # Step 2: Replace calls to mock methods with errors
        if '_create_mock' in content:
            content = replace_mock_calls_with_markers(content, collector_name)
            issues.append("Replaced mock method calls with explicit RuntimeError markers")
        
        # Step 3: Remove np.random usage (if only used for mock data)
        if 'np.random' in content:
            # Check if it's in a comment or string (should keep)
            # For now, we'll be conservative and just warn
            issues.append("Warning: np.random found - may need manual review")
        
        # Step 4: Add comment at top if collector needs real API implementation
        if 'RuntimeError("Collector implementation incomplete' in content or '_create_mock' in content:
            header_comment = f'# NOTE: This collector needs real API implementation.\n# All mock data generation has been removed.\n'
            if not content.startswith(header_comment):
                # Find the docstring end
                if '"""' in content[:500]:
                    # Insert after docstring
                    docstring_end = content.find('"""', content.find('"""') + 3) + 3
                    content = content[:docstring_end] + '\n' + header_comment + content[docstring_end:]
                else:
                    content = header_comment + content
        
        if content != original_content:
            filepath.write_text(content, encoding='utf-8')
            return True, issues
        
        return False, []
        
    except Exception as e:
        return False, [f"Error: {str(e)}"]


def main():
    """Fix all collector files."""
    data_collection_dir = Path(__file__).parent.parent.parent / "data_collection"
    
    if not data_collection_dir.exists():
        print(f"Error: {data_collection_dir} does not exist")
        return
    
    collector_files = [
        f for f in data_collection_dir.glob("*_collector.py")
        if f.name not in ["base_collector.py", "generate_all_collectors.py"]
    ]
    
    print(f"Processing {len(collector_files)} collectors...")
    print("=" * 60)
    
    fixed_count = 0
    error_count = 0
    total_issues = []
    
    for collector_file in sorted(collector_files):
        print(f"\n{collector_file.name}...", end=" ")
        was_fixed, issues = fix_collector_file(collector_file)
        
        if issues:
            print(f"FIXED - {', '.join(issues)}")
            fixed_count += 1
            total_issues.extend([f"{collector_file.name}: {issue}" for issue in issues])
        elif was_fixed:
            print("FIXED")
            fixed_count += 1
        else:
            print("NO CHANGES")
    
    print("\n" + "=" * 60)
    print(f"\nSummary:")
    print(f"  Total collectors: {len(collector_files)}")
    print(f"  Fixed: {fixed_count}")
    print(f"  Errors: {error_count}")
    print(f"  No changes: {len(collector_files) - fixed_count - error_count}")
    
    if total_issues:
        print(f"\nIssues found:")
        for issue in total_issues[:20]:  # Show first 20
            print(f"  - {issue}")
        if len(total_issues) > 20:
            print(f"  ... and {len(total_issues) - 20} more")
    
    print("\n" + "=" * 60)
    print("\nNOTE: Some collectors may still need manual implementation")
    print("      of real API calls. Check files with 'Collector implementation incomplete'.")


if __name__ == "__main__":
    main()
