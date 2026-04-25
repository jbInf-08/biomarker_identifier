"""
Test package for Cancer Biomarker Identifier application.
"""

__version__ = "1.0.0"
__author__ = "Cancer Biomarker Identifier Team"

# Test configuration
TEST_CONFIG = {
    "test_data_dir": "test_data",
    "output_dir": "test_output",
    "timeout": 300,  # 5 minutes
    "max_memory": "4GB"
}

# Test categories (all tests use real data only - no mock/fake/dummy/artificial data)
TEST_CATEGORIES = [
    "unit",
    "integration",
    "performance",
    "smoke",
    "real_data_e2e"
]

# Performance benchmarks
PERFORMANCE_BENCHMARKS = {
    "dataset_creation": 1.0,  # seconds
    "data_transformation": 2.0,  # seconds
    "statistical_analysis": 5.0,  # seconds
    "pipeline_execution": 30.0,  # seconds
    "memory_usage": 4.0  # GB
}
