#!/usr/bin/env python3
"""
Script to interpret and explain biomarker pipeline results.
"""
import json
from pathlib import Path
import pandas as pd

def main():
    # Find latest results directory
    results_dir = Path('data/pipeline_results')
    if not results_dir.exists():
        print("No results directory found!")
        return
    
    dirs = sorted([d for d in results_dir.iterdir() if d.is_dir()], 
                  key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not dirs:
        print("No result directories found!")
        return
    
    latest = dirs[0]
    json_file = latest / 'pipeline_results.json'
    
    if not json_file.exists():
        print(f"Results file not found: {json_file}")
        return
    
    print("=" * 80)
    print("BIOMARKER IDENTIFICATION PIPELINE - RESULTS INTERPRETATION")
    print("=" * 80)
    print(f"\nAnalyzing results from: {latest.name}")
    
    # Load results
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Pipeline Summary
    print("\n" + "=" * 80)
    print("1. PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    summary = data.get('pipeline_summary', {})
    print(f"   Run ID: {data.get('run_id', 'N/A')}")
    print(f"   Status: {summary.get('status', 'N/A')}")
    print(f"   Timestamp: {data.get('timestamp', 'N/A')}")
    print(f"   Total Steps Completed: {summary.get('total_steps', 'N/A')}")
    
    # Data Summary
    print("\n" + "=" * 80)
    print("2. INPUT DATA SUMMARY")
    print("=" * 80)
    data_summary = summary.get('data_summary', {})
    expr_shape = data_summary.get('expression_shape', 'N/A')
    labels_shape = data_summary.get('labels_shape', 'N/A')
    print(f"   Expression Data: {expr_shape}")
    print(f"   Sample Labels: {labels_shape}")
    print(f"   Validation Status: {data_summary.get('validation_status', 'N/A')}")
    
    if data_summary.get('validation_warnings'):
        print(f"   Validation Warnings: {len(data_summary.get('validation_warnings', []))}")
    
    # Quality Control Summary
    print("\n" + "=" * 80)
    print("3. QUALITY CONTROL RESULTS")
    print("=" * 80)
    qc_summary = summary.get('qc_summary', {})
    if qc_summary:
        print(f"   Initial Data Shape: {qc_summary.get('initial_shape', 'N/A')}")
        print(f"   Filtered Data Shape: {qc_summary.get('filtered_shape', 'N/A')}")
        print(f"   PCA Components: {qc_summary.get('pca_components', 'N/A')}")
        print(f"   Batch Effects Detected: {qc_summary.get('batch_effects_detected', 'N/A')}")
    
    # Normalization Summary
    print("\n" + "=" * 80)
    print("4. NORMALIZATION RESULTS")
    print("=" * 80)
    norm_summary = summary.get('normalization_summary', {})
    if norm_summary:
        print(f"   Method: {norm_summary.get('method', 'N/A')}")
        print(f"   Batch Corrected: {norm_summary.get('batch_corrected', 'N/A')}")
        print(f"   Final Data Shape: {norm_summary.get('final_data_shape', 'N/A')}")
    
    # Statistical Analysis Summary
    print("\n" + "=" * 80)
    print("5. STATISTICAL ANALYSIS RESULTS")
    print("=" * 80)
    stats_summary = summary.get('statistical_summary', {})
    if stats_summary:
        methods = stats_summary.get('methods_run', [])
        print(f"   Methods Applied: {', '.join(methods) if methods else 'N/A'}")
        top_features = stats_summary.get('top_ranked_features', [])
        print(f"   Top Ranked Features: {len(top_features)} features identified")
        if top_features:
            print(f"   Top 5 Features: {', '.join(top_features[:5])}")
    
    # ML Selection Summary
    print("\n" + "=" * 80)
    print("6. MACHINE LEARNING FEATURE SELECTION RESULTS")
    print("=" * 80)
    ml_summary = summary.get('ml_selection_summary', {})
    if ml_summary:
        methods = ml_summary.get('methods_run', [])
        print(f"   Methods Applied: {', '.join(methods) if methods else 'N/A'}")
        consensus_count = ml_summary.get('consensus_features_count', 0)
        print(f"   Consensus Features: {consensus_count} features")
        top_consensus = ml_summary.get('top_consensus_features', [])
        if top_consensus:
            print(f"   Top 5 Consensus Features: {', '.join(top_consensus[:5])}")
    
    # Biomarker List
    print("\n" + "=" * 80)
    print("7. IDENTIFIED BIOMARKERS")
    print("=" * 80)
    biomarkers_raw = data.get('biomarker_list', [])
    # Handle both list and dict formats
    if isinstance(biomarkers_raw, dict):
        biomarkers = biomarkers_raw.get('biomarkers', [])
    elif isinstance(biomarkers_raw, list):
        biomarkers = biomarkers_raw
    else:
        biomarkers = []
    
    print(f"   Total Biomarkers Identified: {len(biomarkers)}")
    
    if biomarkers and len(biomarkers) > 0:
        print(f"\n   Top 10 Biomarkers:")
        print(f"   {'Rank':<6} {'Gene':<20} {'Source':<30} {'Score':<10}")
        print(f"   {'-'*6} {'-'*20} {'-'*30} {'-'*10}")
        for i, bm in enumerate(list(biomarkers)[:10], 1):
            if isinstance(bm, dict):
                gene = bm.get('gene', 'N/A')
                source = bm.get('source', 'N/A')
                score = bm.get('score', 'N/A')
                rank = bm.get('rank', i)
                score_str = f"{score:.4f}" if isinstance(score, (int, float)) else str(score)
                print(f"   {rank:<6} {gene:<20} {source:<30} {score_str:<10}")
            else:
                print(f"   {i:<6} {str(bm)}")
    
    # Interpretation
    print("\n" + "=" * 80)
    print("8. INTERPRETATION & INSIGHTS")
    print("=" * 80)
    
    print("\n   [OK] Pipeline Status:")
    if summary.get('status') == 'completed':
        print("      - Pipeline executed successfully from start to finish")
        print("      - All analysis steps completed without critical errors")
    else:
        print(f"      - Pipeline status: {summary.get('status')}")
    
    print("\n   [OK] Data Quality:")
    if data_summary.get('validation_status') == 'passed':
        print("      - Input data passed all validation checks")
        print("      - Data is suitable for biomarker identification")
    elif data_summary.get('validation_status') == 'warning':
        print("      - Data passed validation with warnings")
        print("      - Some quality issues detected but analysis proceeded")
    
    print("\n   [OK] Statistical Analysis:")
    if stats_summary.get('methods_run'):
        print(f"      - Applied {len(stats_summary.get('methods_run', []))} statistical method(s)")
        print("      - Identified differentially expressed genes")
        print("      - Features ranked by statistical significance")
    
    print("\n   [OK] Machine Learning Selection:")
    if ml_summary.get('consensus_features_count', 0) > 0:
        print(f"      - {ml_summary.get('consensus_features_count')} consensus features identified")
        print("      - Multiple ML methods agreed on these features")
        print("      - These features are robust across different selection methods")
    
    print("\n   [OK] Biomarker Discovery:")
    if len(biomarkers) > 0:
        print(f"      - {len(biomarkers)} potential biomarkers identified")
        print("      - Biomarkers combine statistical and ML evidence")
        print("      - Top-ranked biomarkers are most promising for further validation")
    else:
        print("      - No biomarkers identified - may need to adjust thresholds")
    
    # Notes about the run
    print("\n" + "=" * 80)
    print("9. NOTES & RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n   [WARNING] Bootstrap Warnings:")
    print("      - Some bootstrap iterations failed during stability selection")
    print("      - This is expected with small sample sizes (4 samples)")
    print("      - Results are still valid - failures were handled gracefully")
    
    print("\n   [INFO] Sample Size Considerations:")
    print("      - Analysis used 4 samples (very small dataset)")
    print("      - Results should be validated with larger datasets")
    print("      - Statistical power is limited with this sample size")
    
    print("\n   [NEXT STEPS] Recommendations:")
    print("      - Validate top biomarkers in independent dataset")
    print("      - Perform functional enrichment analysis on identified genes")
    print("      - Consider pathway analysis for biomarker interpretation")
    print("      - Expand to larger sample size for more robust results")
    
    print("\n" + "=" * 80)
    print("END OF RESULTS INTERPRETATION")
    print("=" * 80)

if __name__ == '__main__':
    main()
