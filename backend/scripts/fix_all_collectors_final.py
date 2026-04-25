"""
Final comprehensive fix for all collectors.
Fixes double braces and template placeholders.
"""
import re
from pathlib import Path
import subprocess

data_collection_dir = Path(__file__).parent.parent.parent / 'data_collection'

# Source name mappings
SOURCE_NAMES = {
    'tcga': 'TCGA', 'geo': 'GEO', 'cosmic': 'COSMIC', 'icgc': 'ICGC',
    'clinvar': 'ClinVar', 'oncokb': 'OncoKB', 'cbioportal': 'cBioPortal',
    'ega': 'EGA', 'tcia': 'TCIA', 'gdsc': 'GDSC', 'ccle': 'CCLE',
    'nci': 'NCI', 'nih': 'NIH', 'cdc': 'CDC', 'ncbi': 'NCBI',
    'pubmed': 'PubMed', 'kaggle': 'Kaggle', 'seer': 'SEER',
    'gdc': 'GDC', 'brats': 'BraTS', 'camelyon': 'CAMELYON',
    'ddsm': 'DDSM', 'inbreast': 'INbreast', 'lidc_idri': 'LIDC-IDRI',
    'luna16': 'Luna16', 'isic': 'ISIC', 'ham10000': 'HAM10000',
    'mimic': 'MIMIC', 'ncdb': 'NCDB', 'wisconsin_breast_cancer': 'WisconsinBreastCancer',
    'pancancer_atlas': 'PanCancerAtlas', 'pathlaion': 'PathLAION',
    'prostate_x': 'ProstateX', 'miccai': 'MICCAI', 'nih_clinical': 'NIHClinical',
    'nsclc_radiogenomics': 'NSCLCRadiogenomics', 'rembrandt': 'REMBRANDT',
    'tcia_glioblastoma': 'TCIAGlioblastoma', 'firecloud_terra': 'FireCloudTerra',
    'google_cloud_healthcare': 'GoogleCloudHealthcare', 'nci_60': 'NCI60'
}

def get_source_name(filename):
    """Extract source name from filename."""
    base = filename.replace('_collector.py', '').lower()
    return SOURCE_NAMES.get(base, base.replace('_', ' ').title())

def fix_collector_file(filepath):
    """Fix all syntax errors in a collector file."""
    source_name = get_source_name(filepath.name)
    content = filepath.read_text(encoding='utf-8')
    original = content
    
    # Fix double braces - simple replacement
    content = content.replace('{{', '{')
    content = content.replace('}}', '}')
    
    # Fix template placeholders
    content = content.replace('{source_name}', source_name)
    content = content.replace('{source_name.upper()}', source_name.upper())
    content = content.replace('{source_name.lower()}', source_name.lower())
    
    # Fix f-string patterns - use string replacement instead of regex
    upper_pattern = f'f"{{source_name.upper()}}_{{i:06d}}"'
    upper_replacement = f'f"{source_name}_{{i:06d}}"'
    content = content.replace(upper_pattern, upper_replacement)
    
    # Fix filename patterns
    filename_pattern = f'f"{{source_name.lower().replace(" ", "_")}}_'
    filename_replacement = f'f"{source_name.lower()}_'
    content = content.replace(filename_pattern, filename_replacement)
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    collector_files = [f for f in data_collection_dir.glob('*_collector.py') 
                      if f.name not in ['base_collector.py', 'generate_all_collectors.py']]
    
    print(f"Processing {len(collector_files)} collectors...")
    print("=" * 60)
    
    fixed = 0
    verified = 0
    errors = []
    
    for collector_file in sorted(collector_files):
        print(f"{collector_file.name}...", end=' ')
        
        # Fix syntax
        was_fixed = fix_collector_file(collector_file)
        if was_fixed:
            print("FIXED", end=' ')
            fixed += 1
        
        # Verify syntax
        result = subprocess.run(
            ['python', '-m', 'py_compile', str(collector_file)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓")
            verified += 1
        else:
            error_msg = result.stderr.strip().split('\n')[-1] if result.stderr else 'Unknown'
            print(f"✗ {error_msg[:50]}")
            errors.append((collector_file.name, error_msg))
    
    print("\n" + "=" * 60)
    print(f"Summary: Fixed={fixed}, Verified={verified}/{len(collector_files)}, Errors={len(errors)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
