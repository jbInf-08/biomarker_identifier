"""
Unit tests for data processing modules.
"""

import unittest
import pandas as pd
import numpy as np
import tempfile
import os
from unittest.mock import patch, MagicMock

# Import data processing modules
import sys
sys.path.append('../backend')

from app.data_processing.data_transformation import DataTransformation
from app.data_processing.batch_correction import BatchCorrection
from app.data_processing.feature_selection import FeatureSelection
from app.data_processing.statistical_analysis import StatisticalAnalysis

class TestDataTransformation(unittest.TestCase):
    """Test cases for DataTransformation."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        self.data = pd.DataFrame(
            np.random.randn(100, 50),  # 100 genes, 50 samples
            index=[f"GENE_{i:03d}" for i in range(100)],
            columns=[f"SAMPLE_{i:03d}" for i in range(50)]
        )
        
        # Add some zeros and negative values for testing
        self.data.iloc[0:10, 0:10] = 0
        self.data.iloc[10:20, 10:20] = -1
    
    def test_initialization(self):
        """Test DataTransformation initialization."""
        config = {"test_param": "test_value"}
        transformer = DataTransformation(config)
        
        self.assertEqual(transformer.config, config)
        self.assertEqual(transformer.transformation_params, {})
    
    def test_log2_transformation(self):
        """Test log2 transformation."""
        transformer = DataTransformation()
        
        # Add small constant to avoid log(0)
        data_with_offset = self.data + 1
        
        transformed_data = transformer.log2(data_with_offset)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        self.assertEqual(transformed_data.index.tolist(), self.data.index.tolist())
        self.assertEqual(transformed_data.columns.tolist(), self.data.columns.tolist())
        
        # Check that transformation parameters are stored
        self.assertIn("log2", transformer.transformation_params)
    
    def test_log10_transformation(self):
        """Test log10 transformation."""
        transformer = DataTransformation()
        
        # Add small constant to avoid log(0)
        data_with_offset = self.data + 1
        
        transformed_data = transformer.log10(data_with_offset)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("log10", transformer.transformation_params)
    
    def test_sqrt_transformation(self):
        """Test sqrt transformation."""
        transformer = DataTransformation()
        
        # Use absolute values to avoid sqrt of negative numbers
        data_abs = self.data.abs()
        
        transformed_data = transformer.sqrt(data_abs)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("sqrt", transformer.transformation_params)
    
    def test_box_cox_transformation(self):
        """Test Box-Cox transformation."""
        transformer = DataTransformation()
        
        # Use positive data for Box-Cox
        data_positive = self.data.abs() + 1
        
        transformed_data = transformer.box_cox(data_positive)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("box_cox", transformer.transformation_params)
    
    def test_yeo_johnson_transformation(self):
        """Test Yeo-Johnson transformation."""
        transformer = DataTransformation()
        
        transformed_data = transformer.yeo_johnson(self.data)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("yeo_johnson", transformer.transformation_params)
    
    def test_quantile_transformation(self):
        """Test quantile transformation."""
        transformer = DataTransformation()
        
        transformed_data = transformer.quantile(self.data)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("quantile", transformer.transformation_params)
    
    def test_rank_transformation(self):
        """Test rank transformation."""
        transformer = DataTransformation()
        
        transformed_data = transformer.rank(self.data)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("rank", transformer.transformation_params)
    
    def test_z_score_transformation(self):
        """Test z-score transformation."""
        transformer = DataTransformation()
        
        transformed_data = transformer.z_score(self.data)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("z_score", transformer.transformation_params)
    
    def test_robust_z_score_transformation(self):
        """Test robust z-score transformation."""
        transformer = DataTransformation()
        
        transformed_data = transformer.robust_z_score(self.data)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("robust_z_score", transformer.transformation_params)
    
    def test_custom_transformation(self):
        """Test custom transformation."""
        transformer = DataTransformation()
        
        # Define custom function
        def custom_func(x):
            return x ** 2
        
        transformed_data = transformer.custom(self.data, custom_func)
        
        self.assertIsInstance(transformed_data, pd.DataFrame)
        self.assertEqual(transformed_data.shape, self.data.shape)
        
        # Check that transformation parameters are stored
        self.assertIn("custom", transformer.transformation_params)
    
    def test_normality_score_calculation(self):
        """Test normality score calculation."""
        transformer = DataTransformation()
        
        # Create normally distributed data
        normal_data = pd.DataFrame(np.random.normal(0, 1, (100, 50)))
        
        score = transformer._calculate_normality_score(normal_data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)
    
    def test_transformation_comparison(self):
        """Test transformation comparison."""
        transformer = DataTransformation()
        
        # Test different transformations
        transformations = ["log2", "log10", "sqrt", "z_score"]
        scores = {}
        
        for method in transformations:
            if method == "log2" or method == "log10":
                data_with_offset = self.data + 1
                transformed = getattr(transformer, method)(data_with_offset)
            elif method == "sqrt":
                data_abs = self.data.abs()
                transformed = getattr(transformer, method)(data_abs)
            else:
                transformed = getattr(transformer, method)(self.data)
            
            scores[method] = transformer._calculate_normality_score(transformed)
        
        self.assertEqual(len(scores), len(transformations))
        for score in scores.values():
            self.assertIsInstance(score, float)
    
    def test_best_transformation_detection(self):
        """Test best transformation detection."""
        transformer = DataTransformation()
        
        best_method = transformer.detect_best_transformation(self.data)
        
        self.assertIsInstance(best_method, str)
        self.assertIn(best_method, ["log2", "log10", "sqrt", "box_cox", "yeo_johnson", "quantile", "rank", "z_score", "robust_z_score"])

class TestBatchCorrection(unittest.TestCase):
    """Test cases for BatchCorrection."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        self.data = pd.DataFrame(
            np.random.randn(100, 50),  # 100 genes, 50 samples
            index=[f"GENE_{i:03d}" for i in range(100)],
            columns=[f"SAMPLE_{i:03d}" for i in range(50)]
        )
        
        # Create batch information
        self.batch_info = pd.Series(
            ["BATCH_1"] * 25 + ["BATCH_2"] * 25,
            index=self.data.columns
        )
        
        # Create covariates
        self.covariates = pd.DataFrame({
            'age': np.random.normal(50, 10, 50),
            'gender': np.random.choice(['M', 'F'], 50)
        }, index=self.data.columns)
    
    def test_initialization(self):
        """Test BatchCorrection initialization."""
        config = {"test_param": "test_value"}
        corrector = BatchCorrection(config)
        
        self.assertEqual(corrector.config, config)
        self.assertEqual(corrector.correction_params, {})
    
    def test_combat_correction(self):
        """Test ComBat correction."""
        corrector = BatchCorrection()
        
        corrected_data = corrector.combat(self.data, self.batch_info, self.covariates)
        
        self.assertIsInstance(corrected_data, pd.DataFrame)
        self.assertEqual(corrected_data.shape, self.data.shape)
        self.assertEqual(corrected_data.index.tolist(), self.data.index.tolist())
        self.assertEqual(corrected_data.columns.tolist(), self.data.columns.tolist())
        
        # Check that correction parameters are stored
        self.assertIn("combat", corrector.correction_params)
    
    def test_limma_correction(self):
        """Test limma correction."""
        corrector = BatchCorrection()
        
        corrected_data = corrector.limma(self.data, self.batch_info, self.covariates)
        
        self.assertIsInstance(corrected_data, pd.DataFrame)
        self.assertEqual(corrected_data.shape, self.data.shape)
        
        # Check that correction parameters are stored
        self.assertIn("limma", corrector.correction_params)
    
    def test_pca_correction(self):
        """Test PCA correction."""
        corrector = BatchCorrection()
        
        corrected_data = corrector.pca(self.data, self.batch_info, self.covariates)
        
        self.assertIsInstance(corrected_data, pd.DataFrame)
        self.assertEqual(corrected_data.shape, self.data.shape)
        
        # Check that correction parameters are stored
        self.assertIn("pca", corrector.correction_params)
    
    def test_linear_regression_correction(self):
        """Test linear regression correction."""
        corrector = BatchCorrection()
        
        corrected_data = corrector.linear_regression(self.data, self.batch_info, self.covariates)
        
        self.assertIsInstance(corrected_data, pd.DataFrame)
        self.assertEqual(corrected_data.shape, self.data.shape)
        
        # Check that correction parameters are stored
        self.assertIn("linear_regression", corrector.correction_params)
    
    def test_mean_centering_correction(self):
        """Test mean centering correction."""
        corrector = BatchCorrection()
        
        corrected_data = corrector.mean_centering(self.data, self.batch_info, self.covariates)
        
        self.assertIsInstance(corrected_data, pd.DataFrame)
        self.assertEqual(corrected_data.shape, self.data.shape)
        
        # Check that correction parameters are stored
        self.assertIn("mean_centering", corrector.correction_params)
    
    def test_batch_effect_detection(self):
        """Test batch effect detection."""
        corrector = BatchCorrection()
        
        # Add batch effects to data
        batch_effects = np.random.normal(0, 2, (100, 50))
        data_with_batch = self.data + batch_effects
        
        detection_results = corrector.detect_batch_effects(data_with_batch, self.batch_info)
        
        self.assertIn("pca_analysis", detection_results)
        self.assertIn("anova_analysis", detection_results)
        self.assertIn("correlation_analysis", detection_results)
        self.assertIn("overall_score", detection_results)
    
    def test_correction_evaluation(self):
        """Test correction evaluation."""
        corrector = BatchCorrection()
        
        # Apply correction
        corrected_data = corrector.combat(self.data, self.batch_info, self.covariates)
        
        # Evaluate correction
        evaluation = corrector.evaluate_correction(self.data, corrected_data, self.batch_info)
        
        self.assertIn("batch_effect_reduction", evaluation)
        self.assertIn("data_preservation", evaluation)
        self.assertIn("overall_score", evaluation)
    
    def test_assess_batch_effects(self):
        """Test batch effect assessment."""
        corrector = BatchCorrection()
        
        assessment = corrector.assess_batch_effects(self.data, self.batch_info)
        
        self.assertIn("batch_effect_present", assessment)
        self.assertIn("severity", assessment)
        self.assertIn("recommendation", assessment)

class TestFeatureSelection(unittest.TestCase):
    """Test cases for FeatureSelection."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        self.X = pd.DataFrame(
            np.random.randn(100, 50),  # 100 samples, 50 features
            columns=[f"FEATURE_{i:02d}" for i in range(50)]
        )
        self.y = pd.Series(np.random.choice([0, 1], 100))
    
    def test_initialization(self):
        """Test FeatureSelection initialization."""
        config = {"test_param": "test_value"}
        selector = FeatureSelection(config)
        
        self.assertEqual(selector.config, config)
        self.assertEqual(selector.selection_results, {})
    
    def test_variance_filter(self):
        """Test variance filter method."""
        selector = FeatureSelection()
        
        selected_features = selector.variance(self.X, threshold=0.1)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("variance", selector.selection_results)
    
    def test_f_test_filter(self):
        """Test F-test filter method."""
        selector = FeatureSelection()
        
        selected_features = selector.f_test(self.X, self.y, k=10)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("f_test", selector.selection_results)
    
    def test_mutual_info_filter(self):
        """Test mutual information filter method."""
        selector = FeatureSelection()
        
        selected_features = selector.mutual_info(self.X, self.y, k=10)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("mutual_info", selector.selection_results)
    
    def test_correlation_filter(self):
        """Test correlation filter method."""
        selector = FeatureSelection()
        
        selected_features = selector.correlation(self.X, threshold=0.8)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("correlation", selector.selection_results)
    
    def test_anova_filter(self):
        """Test ANOVA filter method."""
        selector = FeatureSelection()
        
        selected_features = selector.anova(self.X, self.y, k=10)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("anova", selector.selection_results)
    
    def test_chi2_filter(self):
        """Test chi-squared filter method."""
        selector = FeatureSelection()
        
        # Convert data to non-negative for chi2
        X_positive = self.X.abs()
        
        selected_features = selector.chi2(X_positive, self.y, k=10)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("chi2", selector.selection_results)
    
    def test_rfe_wrapper(self):
        """Test RFE wrapper method."""
        selector = FeatureSelection()
        
        selected_features = selector.rfe(self.X, self.y, n_features=10)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("rfe", selector.selection_results)
    
    def test_sequential_forward_wrapper(self):
        """Test sequential forward wrapper method."""
        selector = FeatureSelection()
        
        selected_features = selector.sequential_forward(self.X, self.y, n_features=10)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("sequential_forward", selector.selection_results)
    
    def test_sequential_backward_wrapper(self):
        """Test sequential backward wrapper method."""
        selector = FeatureSelection()
        
        selected_features = selector.sequential_backward(self.X, self.y, n_features=10)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("sequential_backward", selector.selection_results)
    
    def test_lasso_embedded(self):
        """Test LASSO embedded method."""
        selector = FeatureSelection()
        
        selected_features = selector.lasso(self.X, self.y, alpha=0.01)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("lasso", selector.selection_results)
    
    def test_elastic_net_embedded(self):
        """Test Elastic Net embedded method."""
        selector = FeatureSelection()
        
        selected_features = selector.elastic_net(self.X, self.y, alpha=0.01, l1_ratio=0.5)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("elastic_net", selector.selection_results)
    
    def test_random_forest_embedded(self):
        """Test Random Forest embedded method."""
        selector = FeatureSelection()
        
        selected_features = selector.random_forest(self.X, self.y, n_estimators=100)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("random_forest", selector.selection_results)
    
    def test_svm_embedded(self):
        """Test SVM embedded method."""
        selector = FeatureSelection()
        
        selected_features = selector.svm(self.X, self.y, C=1.0)
        
        self.assertIsInstance(selected_features, pd.Series)
        self.assertEqual(len(selected_features), len(self.X.columns))
        self.assertIn("svm", selector.selection_results)
    
    def test_stability_selection(self):
        """Test stability selection."""
        selector = FeatureSelection()
        
        stability_results = selector.stability_selection(self.X, self.y, n_bootstraps=10)
        
        self.assertIn("selection_frequencies", stability_results)
        self.assertIn("stable_features", stability_results)
        self.assertIn("stability_scores", stability_results)
    
    def test_ensemble_selection(self):
        """Test ensemble selection."""
        selector = FeatureSelection()
        
        # Run multiple selection methods
        selector.variance(self.X, threshold=0.1)
        selector.f_test(self.X, self.y, k=10)
        selector.random_forest(self.X, self.y, n_estimators=100)
        
        ensemble_results = selector.ensemble_selection()
        
        self.assertIn("ensemble_scores", ensemble_results)
        self.assertIn("consensus_features", ensemble_results)
        self.assertIn("method_agreement", ensemble_results)

class TestStatisticalAnalysis(unittest.TestCase):
    """Test cases for StatisticalAnalysis."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        self.data = pd.DataFrame(
            np.random.randn(100, 50),  # 100 genes, 50 samples
            index=[f"GENE_{i:03d}" for i in range(100)],
            columns=[f"SAMPLE_{i:03d}" for i in range(50)]
        )
        
        # Create binary labels
        self.binary_labels = pd.Series(
            ["TUMOR"] * 25 + ["NORMAL"] * 25,
            index=self.data.columns
        )
        
        # Create multi-class labels
        self.multiclass_labels = pd.Series(
            ["SUBTYPE_A"] * 17 + ["SUBTYPE_B"] * 17 + ["SUBTYPE_C"] * 16,
            index=self.data.columns
        )
        
        # Create continuous labels
        self.continuous_labels = pd.Series(
            np.random.normal(0, 1, 50),
            index=self.data.columns
        )
    
    def test_initialization(self):
        """Test StatisticalAnalysis initialization."""
        config = {"test_param": "test_value"}
        analyzer = StatisticalAnalysis(config)
        
        self.assertEqual(analyzer.config, config)
        self.assertEqual(analyzer.analysis_results, {})
    
    def test_t_test_analysis(self):
        """Test t-test analysis."""
        analyzer = StatisticalAnalysis()
        
        results = analyzer.t_test(self.data, self.binary_labels)
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertEqual(len(results), len(self.data.index))
        self.assertIn("pvalue", results.columns)
        self.assertIn("statistic", results.columns)
        self.assertIn("effect_size", results.columns)
        
        # Check that results are stored
        self.assertIn("t_test", analyzer.analysis_results)
    
    def test_wilcoxon_analysis(self):
        """Test Wilcoxon analysis."""
        analyzer = StatisticalAnalysis()
        
        results = analyzer.wilcoxon(self.data, self.binary_labels)
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertEqual(len(results), len(self.data.index))
        self.assertIn("pvalue", results.columns)
        self.assertIn("statistic", results.columns)
        self.assertIn("effect_size", results.columns)
        
        # Check that results are stored
        self.assertIn("wilcoxon", analyzer.analysis_results)
    
    def test_anova_analysis(self):
        """Test ANOVA analysis."""
        analyzer = StatisticalAnalysis()
        
        results = analyzer.anova(self.data, self.multiclass_labels)
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertEqual(len(results), len(self.data.index))
        self.assertIn("pvalue", results.columns)
        self.assertIn("statistic", results.columns)
        self.assertIn("effect_size", results.columns)
        
        # Check that results are stored
        self.assertIn("anova", analyzer.analysis_results)
    
    def test_kruskal_analysis(self):
        """Test Kruskal-Wallis analysis."""
        analyzer = StatisticalAnalysis()
        
        results = analyzer.kruskal(self.data, self.multiclass_labels)
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertEqual(len(results), len(self.data.index))
        self.assertIn("pvalue", results.columns)
        self.assertIn("statistic", results.columns)
        self.assertIn("effect_size", results.columns)
        
        # Check that results are stored
        self.assertIn("kruskal", analyzer.analysis_results)
    
    def test_correlation_analysis(self):
        """Test correlation analysis."""
        analyzer = StatisticalAnalysis()
        
        results = analyzer.correlation(self.data, self.continuous_labels)
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertEqual(len(results), len(self.data.index))
        self.assertIn("correlation", results.columns)
        self.assertIn("pvalue", results.columns)
        
        # Check that results are stored
        self.assertIn("correlation", analyzer.analysis_results)
    
    def test_regression_analysis(self):
        """Test regression analysis."""
        analyzer = StatisticalAnalysis()
        
        results = analyzer.regression(self.data, self.continuous_labels)
        
        self.assertIsInstance(results, pd.DataFrame)
        self.assertEqual(len(results), len(self.data.index))
        self.assertIn("coefficient", results.columns)
        self.assertIn("pvalue", results.columns)
        self.assertIn("r_squared", results.columns)
        
        # Check that results are stored
        self.assertIn("regression", analyzer.analysis_results)
    
    def test_multiple_testing_correction(self):
        """Test multiple testing correction."""
        analyzer = StatisticalAnalysis()
        
        # Create mock results with p-values
        mock_results = pd.DataFrame({
            'pvalue': np.random.uniform(0, 1, 100)
        }, index=self.data.index)
        
        corrected_results = analyzer._apply_multiple_testing_correction(mock_results, method='fdr_bh')
        
        self.assertIn("pvalue_adjusted", corrected_results.columns)
        self.assertTrue(all(corrected_results['pvalue_adjusted'] >= 0))
        self.assertTrue(all(corrected_results['pvalue_adjusted'] <= 1))
    
    def test_effect_size_calculation(self):
        """Test effect size calculation."""
        analyzer = StatisticalAnalysis()
        
        # Test Cohen's d for binary
        effect_size = analyzer._calculate_effect_size(
            self.data.iloc[0, :25],  # Group 1
            self.data.iloc[0, 25:],  # Group 2
            'cohens_d'
        )
        
        self.assertIsInstance(effect_size, float)
    
    def test_volcano_plot_data(self):
        """Test volcano plot data preparation."""
        analyzer = StatisticalAnalysis()
        
        # Run t-test first
        results = analyzer.t_test(self.data, self.binary_labels)
        
        volcano_data = analyzer.volcano_plot_data(results, log2fc_col='effect_size', pvalue_col='pvalue')
        
        self.assertIsInstance(volcano_data, pd.DataFrame)
        self.assertIn("log2fc", volcano_data.columns)
        self.assertIn("neg_log10_pvalue", volcano_data.columns)
        self.assertIn("significant", volcano_data.columns)
    
    def test_rank_features(self):
        """Test feature ranking."""
        analyzer = StatisticalAnalysis()
        
        # Run t-test first
        results = analyzer.t_test(self.data, self.binary_labels)
        
        ranked_features = analyzer.rank_features(results, method='combined')
        
        self.assertIsInstance(ranked_features, pd.DataFrame)
        self.assertIn("rank", ranked_features.columns)
        self.assertEqual(len(ranked_features), len(results))

if __name__ == '__main__':
    unittest.main()
