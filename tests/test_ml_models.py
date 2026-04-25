"""
Comprehensive tests for ML models and feature selection.

Tests feature selection, model training, cross-validation, permutation tests, and SHAP explainability.
"""

import unittest
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification, make_regression
from sklearn.model_selection import train_test_split
import tempfile
import os
import sys

# Add backend to path
sys.path.append('../backend')

from app.ml_models.feature_selection import FeatureSelector, ConsensusFeatureSelector
from app.ml_models.model_training import ModelTrainer, ModelEvaluator
from app.ml_models.cross_validation import CrossValidator
from app.ml_models.permutation_tests import PermutationTester
from app.ml_models.shap_explainer import SHAPExplainer


class TestFeatureSelection(unittest.TestCase):
    """Test feature selection algorithms."""
    
    def setUp(self):
        """Set up test data."""
        # Create synthetic classification data
        X, y = make_classification(
            n_samples=200, n_features=50, n_informative=10, 
            n_redundant=5, n_clusters_per_class=1, random_state=42
        )
        
        self.X = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(50)])
        self.y = pd.Series(y, name='target')
        
        # Create synthetic regression data
        X_reg, y_reg = make_regression(
            n_samples=200, n_features=50, n_informative=10, 
            noise=0.1, random_state=42
        )
        
        self.X_reg = pd.DataFrame(X_reg, columns=[f'feature_{i}' for i in range(50)])
        self.y_reg = pd.Series(y_reg, name='target')
    
    def test_feature_selector_classification(self):
        """Test feature selection for classification."""
        selector = FeatureSelector(random_state=42)
        
        # Test with default methods
        selector.fit(self.X, self.y, n_features=20)
        
        # Check that features were selected
        self.assertIsNotNone(selector.selected_features_)
        self.assertGreater(len(selector.selected_features_['features']), 0)
        self.assertLessEqual(len(selector.selected_features_['features']), 20)
        
        # Check that consensus scores were computed
        self.assertIsNotNone(selector.consensus_scores_)
        
        # Test feature importance summary
        importance_df = selector.get_feature_importance()
        self.assertIsInstance(importance_df, pd.DataFrame)
        self.assertGreater(len(importance_df), 0)
        
        # Test transform
        X_transformed = selector.transform(self.X)
        self.assertEqual(X_transformed.shape[1], len(selector.selected_features_['features']))
    
    def test_feature_selector_regression(self):
        """Test feature selection for regression."""
        selector = FeatureSelector(random_state=42)
        
        # Test with regression data
        selector.fit(self.X_reg, self.y_reg, n_features=15)
        
        # Check that features were selected
        self.assertIsNotNone(selector.selected_features_)
        self.assertGreater(len(selector.selected_features_['features']), 0)
        self.assertLessEqual(len(selector.selected_features_['features']), 15)
    
    def test_consensus_feature_selector(self):
        """Test consensus feature selection."""
        selector = ConsensusFeatureSelector(random_state=42)
        
        # Test with bootstrap sampling
        selector.fit(self.X, self.y, n_bootstrap=20, n_features=15)
        
        # Check that consensus results were computed
        self.assertIsNotNone(selector.consensus_results_)
        self.assertGreater(len(selector.consensus_results_['features']), 0)
        
        # Test consensus summary
        summary_df = selector.get_consensus_summary()
        self.assertIsInstance(summary_df, pd.DataFrame)
        self.assertGreater(len(summary_df), 0)
        
        # Test transform
        X_transformed = selector.transform(self.X)
        self.assertEqual(X_transformed.shape[1], len(selector.consensus_results_['features']))


class TestModelTraining(unittest.TestCase):
    """Test model training and evaluation."""
    
    def setUp(self):
        """Set up test data."""
        # Create synthetic classification data
        X, y = make_classification(
            n_samples=200, n_features=20, n_informative=10, 
            n_redundant=5, n_clusters_per_class=1, random_state=42
        )
        
        self.X = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
        self.y = pd.Series(y, name='target')
        
        # Split data
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            self.X, self.y, test_size=0.3, random_state=42, stratify=self.y
        )
    
    def test_model_trainer(self):
        """Test model training."""
        trainer = ModelTrainer(random_state=42)
        
        # Test training with default models
        results = trainer.train_models(self.X_train, self.y_train, optimize_hyperparameters=False)
        
        # Check that models were trained
        self.assertGreater(len(results), 0)
        self.assertGreater(len(trainer.trained_models_), 0)
        
        # Check that each model has required keys
        for model_name, model_results in results.items():
            self.assertIn('model', model_results)
            self.assertIn('best_params', model_results)
            self.assertIn('best_score', model_results)
            self.assertIn('model_type', model_results)
        
        # Test getting best model
        best_model_name, best_model = trainer.get_best_model()
        self.assertIsNotNone(best_model_name)
        self.assertIsNotNone(best_model)
    
    def test_model_evaluator(self):
        """Test model evaluation."""
        trainer = ModelTrainer(random_state=42)
        evaluator = ModelEvaluator(random_state=42)
        
        # Train models first
        trainer.train_models(self.X_train, self.y_train, optimize_hyperparameters=False)
        
        # Evaluate models
        evaluation_results = evaluator.evaluate_models(
            trainer.trained_models_, self.X_test, self.y_test
        )
        
        # Check that evaluation results were generated
        self.assertGreater(len(evaluation_results), 0)
        
        # Check that each model has evaluation results
        for model_name, results in evaluation_results.items():
            self.assertIn('cv_results', results)
            self.assertIn('full_results', results)
            self.assertIn('model_type', results)
        
        # Test model comparison
        comparison_df = evaluator.compare_models()
        self.assertIsInstance(comparison_df, pd.DataFrame)
        
        # Test evaluation summary
        summary_df = evaluator.get_evaluation_summary()
        self.assertIsInstance(summary_df, pd.DataFrame)
        self.assertGreater(len(summary_df), 0)


class TestCrossValidation(unittest.TestCase):
    """Test cross-validation functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create synthetic classification data
        X, y = make_classification(
            n_samples=200, n_features=20, n_informative=10, 
            n_redundant=5, n_clusters_per_class=1, random_state=42
        )
        
        self.X = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
        self.y = pd.Series(y, name='target')
    
    def test_nested_cross_validation(self):
        """Test nested cross-validation."""
        validator = CrossValidator(random_state=42)
        
        # Test nested CV with default models
        cv_results = validator.nested_cross_validation(self.X, self.y, cv_folds=3, inner_cv_folds=2)
        
        # Check that CV results were generated
        self.assertIn('model_scores', cv_results)
        self.assertIn('best_params', cv_results)
        self.assertIn('cv_scores', cv_results)
        self.assertIn('performance_metrics', cv_results)
        
        # Check that models were evaluated
        self.assertGreater(len(cv_results['model_scores']), 0)
        
        # Test model comparison
        comparison_df = validator.compare_models()
        self.assertIsInstance(comparison_df, pd.DataFrame)
        
        # Test getting best model
        best_model_name, best_model = validator.get_best_model()
        self.assertIsNotNone(best_model_name)
        self.assertIsNotNone(best_model)
        
        # Test CV summary
        summary_df = validator.get_cv_summary()
        self.assertIsInstance(summary_df, pd.DataFrame)
        self.assertGreater(len(summary_df), 0)


class TestPermutationTests(unittest.TestCase):
    """Test permutation testing functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create synthetic classification data
        X, y = make_classification(
            n_samples=100, n_features=20, n_informative=10, 
            n_redundant=5, n_clusters_per_class=1, random_state=42
        )
        
        self.X = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
        self.y = pd.Series(y, name='target')
        
        # Train a simple model
        from sklearn.ensemble import RandomForestClassifier
        self.model = RandomForestClassifier(n_estimators=10, random_state=42)
        self.model.fit(self.X, self.y)
    
    def test_feature_importance_permutation_test(self):
        """Test feature importance permutation test."""
        tester = PermutationTester(random_state=42)
        
        # Test feature importance permutation test
        results = tester.feature_importance_permutation_test(
            self.model, self.X, self.y, n_permutations=50
        )
        
        # Check that results were generated
        self.assertIn('baseline_performance', results)
        self.assertIn('feature_results', results)
        self.assertIn('significance_results', results)
        
        # Check that feature results were generated
        self.assertGreater(len(results['feature_results']), 0)
        
        # Check significance results
        significance = results['significance_results']
        self.assertIn('mean_importance', significance)
        self.assertIn('p_value', significance)
        self.assertIn('corrected_p_value', significance)
    
    def test_model_performance_permutation_test(self):
        """Test model performance permutation test."""
        tester = PermutationTester(random_state=42)
        
        # Test model performance permutation test
        results = tester.model_performance_permutation_test(
            self.model, self.X, self.y, n_permutations=50
        )
        
        # Check that results were generated
        self.assertIn('baseline_performance', results)
        self.assertIn('permuted_scores', results)
        self.assertIn('p_value', results)
        self.assertIn('effect_size', results)
        self.assertIn('significant', results)
    
    def test_stability_permutation_test(self):
        """Test stability permutation test."""
        tester = PermutationTester(random_state=42)
        selector = FeatureSelector(random_state=42)
        
        # Test stability permutation test
        results = tester.stability_permutation_test(
            self.X, self.y, selector, n_permutations=20, n_features=10
        )
        
        # Check that results were generated
        self.assertIn('baseline_features', results)
        self.assertIn('mean_stability', results)
        self.assertIn('stability_scores', results)
        self.assertIn('p_value', results)
        self.assertIn('feature_frequencies', results)
    
    def test_permutation_summary(self):
        """Test permutation test summary."""
        tester = PermutationTester(random_state=42)
        
        # Run some tests first
        tester.feature_importance_permutation_test(
            self.model, self.X, self.y, n_permutations=20
        )
        tester.model_performance_permutation_test(
            self.model, self.X, self.y, n_permutations=20
        )
        
        # Test summary
        summary_df = tester.get_permutation_summary()
        self.assertIsInstance(summary_df, pd.DataFrame)
        self.assertGreater(len(summary_df), 0)


class TestSHAPExplainer(unittest.TestCase):
    """Test SHAP explainability functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create synthetic classification data
        X, y = make_classification(
            n_samples=100, n_features=20, n_informative=10, 
            n_redundant=5, n_clusters_per_class=1, random_state=42
        )
        
        self.X = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(20)])
        self.y = pd.Series(y, name='target')
        
        # Train a simple model
        from sklearn.ensemble import RandomForestClassifier
        self.model = RandomForestClassifier(n_estimators=10, random_state=42)
        self.model.fit(self.X, self.y)
    
    def test_shap_explainer_fit(self):
        """Test SHAP explainer fitting."""
        explainer = SHAPExplainer(random_state=42)
        
        # Test fitting explainer
        explainer.fit_explainer(self.model, self.X, sample_size=50)
        
        # Check that explainer was fitted
        self.assertIsNotNone(explainer.explainer_)
    
    def test_global_explanations(self):
        """Test global SHAP explanations."""
        explainer = SHAPExplainer(random_state=42)
        explainer.fit_explainer(self.model, self.X, sample_size=50)
        
        # Test global explanations
        results = explainer.explain_global(self.X, max_display=10)
        
        # Check that results were generated
        self.assertIn('feature_importance', results)
        self.assertIn('top_features', results)
        self.assertIn('summary_stats', results)
        
        # Check that feature importance was calculated
        self.assertGreater(len(results['feature_importance']), 0)
        self.assertGreater(len(results['top_features']), 0)
        
        # Test feature importance ranking
        ranking_df = explainer.get_feature_importance_ranking()
        self.assertIsInstance(ranking_df, pd.DataFrame)
        self.assertGreater(len(ranking_df), 0)
    
    def test_local_explanations(self):
        """Test local SHAP explanations."""
        explainer = SHAPExplainer(random_state=42)
        explainer.fit_explainer(self.model, self.X, sample_size=50)
        
        # Test local explanations
        results = explainer.explain_local(self.X, sample_indices=[0, 1, 2], max_display=5)
        
        # Check that results were generated
        self.assertGreater(len(results), 0)
        
        # Check that each sample has explanations
        for sample_key, sample_data in results.items():
            self.assertIn('explanation', sample_data)
            self.assertIn('top_features', sample_data)
            self.assertIn('sample_stats', sample_data)
        
        # Test getting specific sample explanation
        sample_explanation = explainer.get_sample_explanations(0)
        self.assertIsInstance(sample_explanation, dict)
    
    def test_explanation_summary(self):
        """Test explanation summary generation."""
        explainer = SHAPExplainer(random_state=42)
        explainer.fit_explainer(self.model, self.X, sample_size=50)
        
        # Generate explanations
        explainer.explain_global(self.X, max_display=10)
        explainer.explain_local(self.X, sample_indices=[0, 1], max_display=5)
        
        # Test summary
        summary = explainer.generate_explanation_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn('explanation_types', summary)
        self.assertIn('timestamp', summary)


class TestMLPipelineIntegration(unittest.TestCase):
    """Test integration of all ML components."""
    
    def setUp(self):
        """Set up test data."""
        # Create synthetic classification data
        X, y = make_classification(
            n_samples=200, n_features=30, n_informative=15, 
            n_redundant=5, n_clusters_per_class=1, random_state=42
        )
        
        self.X = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(30)])
        self.y = pd.Series(y, name='target')
    
    def test_full_ml_pipeline(self):
        """Test complete ML pipeline integration."""
        # 1. Feature Selection
        selector = FeatureSelector(random_state=42)
        selector.fit(self.X, self.y, n_features=20)
        X_selected = selector.transform(self.X)
        
        # 2. Model Training
        trainer = ModelTrainer(random_state=42)
        training_results = trainer.train_models(X_selected, self.y, optimize_hyperparameters=False)
        
        # 3. Model Evaluation
        evaluator = ModelEvaluator(random_state=42)
        evaluation_results = evaluator.evaluate_models(
            trainer.trained_models_, X_selected, self.y
        )
        
        # 4. Cross-Validation
        validator = CrossValidator(random_state=42)
        cv_results = validator.nested_cross_validation(X_selected, self.y, cv_folds=3)
        
        # 5. Permutation Tests
        best_model_name, best_model = trainer.get_best_model()
        tester = PermutationTester(random_state=42)
        permutation_results = tester.model_performance_permutation_test(
            best_model, X_selected, self.y, n_permutations=50
        )
        
        # 6. SHAP Explanations
        explainer = SHAPExplainer(random_state=42)
        explainer.fit_explainer(best_model, X_selected, sample_size=50)
        shap_results = explainer.explain_global(X_selected, max_display=10)
        
        # Verify all components worked
        self.assertGreater(len(selector.selected_features_['features']), 0)
        self.assertGreater(len(training_results), 0)
        self.assertGreater(len(evaluation_results), 0)
        self.assertGreater(len(cv_results['model_scores']), 0)
        self.assertIn('p_value', permutation_results)
        self.assertIn('feature_importance', shap_results)
        
        logger.info("Full ML pipeline integration test completed successfully")


if __name__ == '__main__':
    # Set up logging
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)
