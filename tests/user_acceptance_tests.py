"""
User Acceptance Tests for Biomarker Identifier
Comprehensive testing framework for production deployment validation
"""

import pytest
import requests
import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import numpy as np

class TestUserAcceptance:
    """User Acceptance Test Suite"""
    
    @pytest.fixture(scope="class")
    def setup_environment(self):
        """Setup test environment"""
        self.base_url = os.getenv('BASE_URL', 'http://localhost')
        self.api_url = f"{self.base_url}/api"
        self.admin_credentials = {
            'username': os.getenv('ADMIN_USERNAME', 'admin'),
            'password': os.getenv('ADMIN_PASSWORD', 'admin123')
        }
        self.test_user_credentials = {
            'username': 'testuser',
            'password': 'testpass123',
            'email': 'testuser@example.com'
        }
        
    @pytest.fixture(scope="class")
    def setup_selenium(self):
        """Setup Selenium WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        yield driver
        driver.quit()
    
    def test_01_application_accessibility(self, setup_environment, setup_selenium):
        """Test 1: Application is accessible and loads correctly"""
        driver = setup_selenium
        
        # Test frontend accessibility
        driver.get(self.base_url)
        assert "Biomarker Identifier" in driver.title
        
        # Test API accessibility
        response = requests.get(f"{self.api_url}/health")
        assert response.status_code == 200
        
        # Test all main pages load
        pages = ['/', '/upload', '/analysis', '/results', '/reports']
        for page in pages:
            driver.get(f"{self.base_url}{page}")
            assert driver.current_url.endswith(page) or page == '/'
    
    def test_02_user_registration_and_authentication(self, setup_environment, setup_selenium):
        """Test 2: User registration and authentication flow"""
        driver = setup_selenium
        
        # Test user registration
        driver.get(f"{self.base_url}/register")
        
        # Fill registration form
        driver.find_element(By.NAME, "username").send_keys(self.test_user_credentials['username'])
        driver.find_element(By.NAME, "email").send_keys(self.test_user_credentials['email'])
        driver.find_element(By.NAME, "password").send_keys(self.test_user_credentials['password'])
        driver.find_element(By.NAME, "confirm_password").send_keys(self.test_user_credentials['password'])
        
        # Submit registration
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Verify registration success
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "alert-success"))
        )
        
        # Test login
        driver.get(f"{self.base_url}/login")
        driver.find_element(By.NAME, "username").send_keys(self.test_user_credentials['username'])
        driver.find_element(By.NAME, "password").send_keys(self.test_user_credentials['password'])
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Verify login success
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "user-menu"))
        )
    
    def test_03_data_upload_functionality(self, setup_environment, setup_selenium):
        """Test 3: Data upload and validation"""
        driver = setup_selenium
        
        # Login first
        self._login_user(driver, self.test_user_credentials)
        
        # Navigate to upload page
        driver.get(f"{self.base_url}/upload")
        
        # Create test data files
        test_data = self._create_test_data()
        
        # Test file upload
        file_input = driver.find_element(By.NAME, "expression_file")
        file_input.send_keys(test_data['expression_file'])
        
        file_input = driver.find_element(By.NAME, "labels_file")
        file_input.send_keys(test_data['labels_file'])
        
        # Submit upload
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Verify upload success
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "upload-success"))
        )
    
    def test_04_analysis_pipeline_execution(self, setup_environment, setup_selenium):
        """Test 4: Analysis pipeline execution"""
        driver = setup_selenium
        
        # Login and upload data
        self._login_user(driver, self.test_user_credentials)
        self._upload_test_data(driver)
        
        # Start analysis
        driver.get(f"{self.base_url}/analysis")
        
        # Configure analysis parameters
        driver.find_element(By.NAME, "analysis_type").send_keys("classification")
        driver.find_element(By.NAME, "feature_selection").click()
        driver.find_element(By.NAME, "cross_validation").send_keys("5")
        
        # Start analysis
        driver.find_element(By.XPATH, "//button[contains(text(), 'Start Analysis')]").click()
        
        # Monitor analysis progress
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CLASS_NAME, "analysis-progress"))
        )
        
        # Wait for completion
        WebDriverWait(driver, 300).until(
            EC.presence_of_element_located((By.CLASS_NAME, "analysis-complete"))
        )
    
    def test_05_results_visualization(self, setup_environment, setup_selenium):
        """Test 5: Results visualization and interpretation"""
        driver = setup_selenium
        
        # Login and complete analysis
        self._login_user(driver, self.test_user_credentials)
        self._complete_test_analysis(driver)
        
        # Navigate to results
        driver.get(f"{self.base_url}/results")
        
        # Verify results are displayed
        assert driver.find_element(By.CLASS_NAME, "results-container").is_displayed()
        
        # Test interactive visualizations
        driver.find_element(By.CLASS_NAME, "visualization-tab").click()
        assert driver.find_element(By.CLASS_NAME, "plot-container").is_displayed()
        
        # Test biomarker table
        driver.find_element(By.CLASS_NAME, "biomarkers-tab").click()
        assert driver.find_element(By.CLASS_NAME, "biomarkers-table").is_displayed()
        
        # Test pathway analysis
        driver.find_element(By.CLASS_NAME, "pathways-tab").click()
        assert driver.find_element(By.CLASS_NAME, "pathways-container").is_displayed()
    
    def test_06_report_generation(self, setup_environment, setup_selenium):
        """Test 6: Report generation and export"""
        driver = setup_selenium
        
        # Login and complete analysis
        self._login_user(driver, self.test_user_credentials)
        self._complete_test_analysis(driver)
        
        # Navigate to reports
        driver.get(f"{self.base_url}/reports")
        
        # Generate PDF report
        driver.find_element(By.XPATH, "//button[contains(text(), 'Generate PDF')]").click()
        
        # Wait for report generation
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CLASS_NAME, "report-download"))
        )
        
        # Test HTML report
        driver.find_element(By.XPATH, "//button[contains(text(), 'Generate HTML')]").click()
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "html-report"))
        )
    
    def test_07_performance_under_load(self, setup_environment):
        """Test 7: Performance testing under load"""
        # Test concurrent users
        import concurrent.futures
        import threading
        
        def make_request():
            response = requests.get(f"{self.api_url}/health")
            return response.status_code
        
        # Test with 10 concurrent users
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        assert all(status == 200 for status in results)
    
    def test_08_data_security_and_privacy(self, setup_environment, setup_selenium):
        """Test 8: Data security and privacy compliance"""
        driver = setup_selenium
        
        # Test HTTPS in production
        if self.base_url.startswith('https'):
            assert driver.current_url.startswith('https')
        
        # Test data encryption
        response = requests.get(f"{self.api_url}/data/encryption-status")
        assert response.status_code == 200
        
        # Test user data isolation
        self._login_user(driver, self.test_user_credentials)
        driver.get(f"{self.base_url}/results")
        
        # Verify user can only see their own data
        assert "testuser" in driver.page_source or "No results found" in driver.page_source
    
    def test_09_mobile_responsiveness(self, setup_selenium):
        """Test 9: Mobile responsiveness"""
        driver = setup_selenium
        
        # Test mobile viewport
        driver.set_window_size(375, 667)  # iPhone SE size
        
        pages = ['/', '/upload', '/analysis', '/results', '/reports']
        for page in pages:
            driver.get(f"{self.base_url}{page}")
            
            # Check if mobile navigation is present
            assert driver.find_element(By.CLASS_NAME, "mobile-nav").is_displayed()
            
            # Check if content is responsive
            assert driver.find_element(By.CLASS_NAME, "main-content").is_displayed()
    
    def test_10_offline_capabilities(self, setup_environment, setup_selenium):
        """Test 10: Offline capabilities"""
        driver = setup_selenium
        
        # Test service worker registration
        driver.get(f"{self.base_url}")
        driver.execute_script("return 'serviceWorker' in navigator")
        
        # Test offline mode
        driver.execute_script("window.navigator.serviceWorker.ready.then(reg => reg.active.postMessage('skipWaiting'))")
        
        # Test cached resources
        driver.get(f"{self.base_url}/offline")
        assert "You are offline" in driver.page_source or "Cached content" in driver.page_source
    
    def test_11_error_handling_and_recovery(self, setup_environment, setup_selenium):
        """Test 11: Error handling and recovery"""
        driver = setup_selenium
        
        # Test invalid file upload
        driver.get(f"{self.base_url}/upload")
        
        # Upload invalid file
        invalid_file = self._create_invalid_test_file()
        file_input = driver.find_element(By.NAME, "expression_file")
        file_input.send_keys(invalid_file)
        
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Verify error handling
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "error-message"))
        )
        
        # Test network error recovery
        driver.get(f"{self.base_url}/analysis")
        # Simulate network error
        driver.execute_script("window.fetch = () => Promise.reject(new Error('Network error'))")
        
        # Verify error recovery
        assert "Retry" in driver.page_source or "Network error" in driver.page_source
    
    def test_12_accessibility_compliance(self, setup_selenium):
        """Test 12: Accessibility compliance (WCAG 2.1)"""
        driver = setup_selenium
        
        pages = ['/', '/upload', '/analysis', '/results', '/reports']
        for page in pages:
            driver.get(f"{self.base_url}{page}")
            
            # Check for alt text on images
            images = driver.find_elements(By.TAG_NAME, "img")
            for img in images:
                assert img.get_attribute("alt") is not None
            
            # Check for proper heading structure
            headings = driver.find_elements(By.XPATH, "//h1 | //h2 | //h3 | //h4 | //h5 | //h6")
            assert len(headings) > 0
            
            # Check for form labels
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for input_elem in inputs:
                if input_elem.get_attribute("type") not in ["hidden", "submit", "button"]:
                    input_id = input_elem.get_attribute("id")
                    if input_id:
                        label = driver.find_element(By.XPATH, f"//label[@for='{input_id}']")
                        assert label is not None
    
    # Helper methods
    def _login_user(self, driver, credentials):
        """Helper method to login user"""
        driver.get(f"{self.base_url}/login")
        driver.find_element(By.NAME, "username").send_keys(credentials['username'])
        driver.find_element(By.NAME, "password").send_keys(credentials['password'])
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "user-menu"))
        )
    
    def _create_test_data(self):
        """Create test data files"""
        # Create expression data
        expression_data = pd.DataFrame({
            'gene_1': np.random.randn(100),
            'gene_2': np.random.randn(100),
            'gene_3': np.random.randn(100)
        })
        expression_file = '/tmp/test_expression.tsv'
        expression_data.to_csv(expression_file, sep='\t', index=False)
        
        # Create labels data
        labels_data = pd.DataFrame({
            'sample_id': [f'sample_{i}' for i in range(100)],
            'label': np.random.choice(['case', 'control'], 100)
        })
        labels_file = '/tmp/test_labels.tsv'
        labels_data.to_csv(labels_file, sep='\t', index=False)
        
        return {
            'expression_file': expression_file,
            'labels_file': labels_file
        }
    
    def _create_invalid_test_file(self):
        """Create invalid test file"""
        invalid_file = '/tmp/invalid_data.txt'
        with open(invalid_file, 'w') as f:
            f.write("This is not a valid data file")
        return invalid_file
    
    def _upload_test_data(self, driver):
        """Helper method to upload test data"""
        test_data = self._create_test_data()
        driver.get(f"{self.base_url}/upload")
        
        file_input = driver.find_element(By.NAME, "expression_file")
        file_input.send_keys(test_data['expression_file'])
        
        file_input = driver.find_element(By.NAME, "labels_file")
        file_input.send_keys(test_data['labels_file'])
        
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "upload-success"))
        )
    
    def _complete_test_analysis(self, driver):
        """Helper method to complete test analysis"""
        self._upload_test_data(driver)
        
        driver.get(f"{self.base_url}/analysis")
        driver.find_element(By.NAME, "analysis_type").send_keys("classification")
        driver.find_element(By.XPATH, "//button[contains(text(), 'Start Analysis')]").click()
        
        WebDriverWait(driver, 300).until(
            EC.presence_of_element_located((By.CLASS_NAME, "analysis-complete"))
        )

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
