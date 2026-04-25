"""
Remove all remaining _create_mock_* methods from collector files.
"""
import re
from pathlib import Path


def remove_mock_methods_from_file(filepath: Path) -> bool:
    """Remove all _create_mock_* method definitions and their bodies."""
    content = filepath.read_text(encoding='utf-8')
    original = content
    
    # Pattern to match method definition and body
    # Match from "def _create_mock" to next method/class or end of class
    lines = content.split('\n')
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a mock method definition
        if re.match(r'\s+def _create_mock', line):
            # Get indentation level
            indent_level = len(line) - len(line.lstrip())
            
            # Skip this method - find where it ends
            i += 1
            while i < len(lines):
                current_line = lines[i]
                
                # Check if we've reached the next method/class at same or less indentation
                if current_line.strip():
                    current_indent = len(current_line) - len(current_line.lstrip())
                    if current_indent <= indent_level:
                        # Check if it's a new method/class
                        if (current_line.strip().startswith('def ') or 
                            current_line.strip().startswith('class ') or
                            current_line.strip().startswith('@')):
                            break
                
                i += 1
            continue
        
        new_lines.append(line)
        i += 1
    
    new_content = '\n'.join(new_lines)
    
    if new_content != original:
        filepath.write_text(new_content, encoding='utf-8')
        return True
    return False


def main():
    data_collection_dir = Path(__file__).parent.parent.parent / "data_collection"
    collector_files = [
        f for f in data_collection_dir.glob("*_collector.py")
        if f.name not in ["base_collector.py", "generate_all_collectors.py"]
    ]
    
    fixed = 0
    for f in collector_files:
        if remove_mock_methods_from_file(f):
            print(f"Removed mock methods from {f.name}")
            fixed += 1
    
    print(f"\nFixed {fixed} files")


if __name__ == "__main__":
    main()
