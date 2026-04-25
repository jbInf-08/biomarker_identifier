"""
Comprehensive Performance Testing Suite
Tests system performance under various load conditions
"""

import asyncio
import aiohttp
import time
import statistics
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import pandas as pd
import numpy as np
import json
import logging
from dataclasses import dataclass
import matplotlib.pyplot as plt
import seaborn as sns

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics data class"""
    response_time: float
    throughput: float
    error_rate: float
    cpu_usage: float
    memory_usage: float
    concurrent_users: int
    timestamp: float

class PerformanceTestSuite:
    """Comprehensive performance testing suite"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.start_time = None
        self.end_time = None
        
    async def run_load_test(
        self,
        concurrent_users: int = 10,
        duration_seconds: int = 60,
        ramp_up_seconds: int = 10
    ) -> Dict[str, Any]:
        """
        Run load test with specified parameters
        
        Args:
            concurrent_users: Number of concurrent users
            duration_seconds: Test duration in seconds
            ramp_up_seconds: Ramp-up time in seconds
        """
        logger.info(f"Starting load test: {concurrent_users} users, {duration_seconds}s duration")
        
        self.start_time = time.time()
        tasks = []
        
        # Create tasks for concurrent users
        for user_id in range(concurrent_users):
            task = asyncio.create_task(
                self._simulate_user_session(user_id, duration_seconds, ramp_up_seconds)
            )
            tasks.append(task)
        
        # Monitor system resources
        monitor_task = asyncio.create_task(
            self._monitor_system_resources(duration_seconds)
        )
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, monitor_task)
        
        self.end_time = time.time()
        
        # Analyze results
        return self._analyze_results()
    
    async def _simulate_user_session(
        self, 
        user_id: int, 
        duration_seconds: int, 
        ramp_up_seconds: int
    ):
        """Simulate a user session"""
        
        # Ramp up delay
        ramp_up_delay = (user_id / 10) * ramp_up_seconds
        await asyncio.sleep(ramp_up_delay)
        
        session_start = time.time()
        session_end = session_start + duration_seconds
        
        async with aiohttp.ClientSession() as session:
            while time.time() < session_end:
                try:
                    # Simulate different user actions
                    action = np.random.choice([
                        'health_check',
                        'upload_data',
                        'start_analysis',
                        'get_results',
                        'generate_report'
                    ], p=[0.3, 0.2, 0.2, 0.2, 0.1])
                    
                    start_time = time.time()
                    
                    if action == 'health_check':
                        await self._health_check(session)
                    elif action == 'upload_data':
                        await self._upload_data(session, user_id)
                    elif action == 'start_analysis':
                        await self._start_analysis(session, user_id)
                    elif action == 'get_results':
                        await self._get_results(session, user_id)
                    elif action == 'generate_report':
                        await self._generate_report(session, user_id)
                    
                    response_time = time.time() - start_time
                    
                    # Record metrics
                    self.results.append(PerformanceMetrics(
                        response_time=response_time,
                        throughput=1.0,
                        error_rate=0.0,
                        cpu_usage=psutil.cpu_percent(),
                        memory_usage=psutil.virtual_memory().percent,
                        concurrent_users=1,
                        timestamp=time.time()
                    ))
                    
                    # Random delay between actions
                    await asyncio.sleep(np.random.uniform(1, 5))
                    
                except Exception as e:
                    logger.error(f"Error in user session {user_id}: {str(e)}")
                    self.results.append(PerformanceMetrics(
                        response_time=0.0,
                        throughput=0.0,
                        error_rate=1.0,
                        cpu_usage=psutil.cpu_percent(),
                        memory_usage=psutil.virtual_memory().percent,
                        concurrent_users=1,
                        timestamp=time.time()
                    ))
    
    async def _health_check(self, session: aiohttp.ClientSession):
        """Simulate health check request"""
        async with session.get(f"{self.base_url}/health") as response:
            if response.status != 200:
                raise Exception(f"Health check failed: {response.status}")
    
    async def _upload_data(self, session: aiohttp.ClientSession, user_id: int):
        """Simulate data upload"""
        # Create test data
        test_data = self._create_test_data(user_id)
        
        data = aiohttp.FormData()
        data.add_field('expression_file', test_data['expression'], filename='expression.tsv')
        data.add_field('labels_file', test_data['labels'], filename='labels.tsv')
        
        async with session.post(f"{self.base_url}/api/upload", data=data) as response:
            if response.status not in [200, 201]:
                raise Exception(f"Upload failed: {response.status}")
    
    async def _start_analysis(self, session: aiohttp.ClientSession, user_id: int):
        """Simulate analysis start"""
        analysis_config = {
            'analysis_type': 'classification',
            'feature_selection': True,
            'cross_validation': 5
        }
        
        async with session.post(
            f"{self.base_url}/api/analysis/start",
            json=analysis_config
        ) as response:
            if response.status not in [200, 201]:
                raise Exception(f"Analysis start failed: {response.status}")
    
    async def _get_results(self, session: aiohttp.ClientSession, user_id: int):
        """Simulate results retrieval"""
        async with session.get(f"{self.base_url}/api/results/{user_id}") as response:
            if response.status not in [200, 404]:  # 404 is acceptable for test
                raise Exception(f"Results retrieval failed: {response.status}")
    
    async def _generate_report(self, session: aiohttp.ClientSession, user_id: int):
        """Simulate report generation"""
        report_config = {
            'format': 'pdf',
            'include_metadata': True,
            'include_visualizations': True
        }
        
        async with session.post(
            f"{self.base_url}/api/reports/generate",
            json=report_config
        ) as response:
            if response.status not in [200, 201]:
                raise Exception(f"Report generation failed: {response.status}")
    
    def _create_test_data(self, user_id: int) -> Dict[str, str]:
        """Create test data for upload"""
        # Generate random expression data
        n_samples = 100
        n_genes = 1000
        
        expression_data = np.random.randn(n_samples, n_genes)
        gene_names = [f"GENE_{i:04d}" for i in range(n_genes)]
        sample_names = [f"SAMPLE_{user_id}_{i:03d}" for i in range(n_samples)]
        
        # Create expression DataFrame
        df_expr = pd.DataFrame(expression_data, columns=gene_names, index=sample_names)
        expression_str = df_expr.to_csv(sep='\t')
        
        # Create labels
        labels = np.random.choice(['case', 'control'], n_samples)
        df_labels = pd.DataFrame({
            'sample_id': sample_names,
            'label': labels
        })
        labels_str = df_labels.to_csv(sep='\t', index=False)
        
        return {
            'expression': expression_str,
            'labels': labels_str
        }
    
    async def _monitor_system_resources(self, duration_seconds: int):
        """Monitor system resources during test"""
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            
            logger.info(f"System resources - CPU: {cpu_usage}%, Memory: {memory_usage}%, Disk: {disk_usage}%")
            
            await asyncio.sleep(5)  # Monitor every 5 seconds
    
    def _analyze_results(self) -> Dict[str, Any]:
        """Analyze performance test results"""
        if not self.results:
            return {'error': 'No results to analyze'}
        
        # Extract metrics
        response_times = [r.response_time for r in self.results]
        error_rates = [r.error_rate for r in self.results]
        cpu_usage = [r.cpu_usage for r in self.results]
        memory_usage = [r.memory_usage for r in self.results]
        
        # Calculate statistics
        analysis = {
            'test_duration': self.end_time - self.start_time,
            'total_requests': len(self.results),
            'response_time': {
                'mean': statistics.mean(response_times),
                'median': statistics.median(response_times),
                'p95': np.percentile(response_times, 95),
                'p99': np.percentile(response_times, 99),
                'max': max(response_times),
                'min': min(response_times)
            },
            'throughput': {
                'requests_per_second': len(self.results) / (self.end_time - self.start_time),
                'mean_throughput': statistics.mean([r.throughput for r in self.results])
            },
            'error_rate': {
                'overall': statistics.mean(error_rates),
                'total_errors': sum(error_rates)
            },
            'system_resources': {
                'cpu_usage': {
                    'mean': statistics.mean(cpu_usage),
                    'max': max(cpu_usage),
                    'min': min(cpu_usage)
                },
                'memory_usage': {
                    'mean': statistics.mean(memory_usage),
                    'max': max(memory_usage),
                    'min': min(memory_usage)
                }
            },
            'performance_grade': self._calculate_performance_grade()
        }
        
        return analysis
    
    def _calculate_performance_grade(self) -> str:
        """Calculate performance grade based on metrics"""
        if not self.results:
            return 'F'
        
        response_times = [r.response_time for r in self.results]
        error_rates = [r.error_rate for r in self.results]
        
        mean_response_time = statistics.mean(response_times)
        mean_error_rate = statistics.mean(error_rates)
        
        # Grading criteria
        if mean_response_time < 1.0 and mean_error_rate < 0.01:
            return 'A'
        elif mean_response_time < 2.0 and mean_error_rate < 0.05:
            return 'B'
        elif mean_response_time < 5.0 and mean_error_rate < 0.1:
            return 'C'
        elif mean_response_time < 10.0 and mean_error_rate < 0.2:
            return 'D'
        else:
            return 'F'
    
    async def run_stress_test(
        self,
        max_concurrent_users: int = 100,
        step_size: int = 10,
        step_duration: int = 30
    ) -> Dict[str, Any]:
        """
        Run stress test to find breaking point
        
        Args:
            max_concurrent_users: Maximum number of concurrent users
            step_size: Number of users to add per step
            step_duration: Duration of each step in seconds
        """
        logger.info(f"Starting stress test: max {max_concurrent_users} users")
        
        stress_results = []
        current_users = 0
        
        while current_users < max_concurrent_users:
            current_users += step_size
            logger.info(f"Testing with {current_users} concurrent users")
            
            # Run load test for this step
            step_result = await self.run_load_test(
                concurrent_users=current_users,
                duration_seconds=step_duration,
                ramp_up_seconds=5
            )
            
            step_result['concurrent_users'] = current_users
            stress_results.append(step_result)
            
            # Check if system is still responsive
            if step_result['error_rate']['overall'] > 0.5:
                logger.warning(f"High error rate detected at {current_users} users")
                break
            
            if step_result['response_time']['mean'] > 10.0:
                logger.warning(f"High response time detected at {current_users} users")
                break
        
        return {
            'stress_test_results': stress_results,
            'breaking_point': current_users,
            'recommended_max_users': current_users - step_size
        }
    
    async def run_endurance_test(
        self,
        concurrent_users: int = 20,
        duration_hours: int = 1
    ) -> Dict[str, Any]:
        """
        Run endurance test to check for memory leaks and stability
        
        Args:
            concurrent_users: Number of concurrent users
            duration_hours: Test duration in hours
        """
        logger.info(f"Starting endurance test: {concurrent_users} users for {duration_hours} hours")
        
        duration_seconds = duration_hours * 3600
        return await self.run_load_test(
            concurrent_users=concurrent_users,
            duration_seconds=duration_seconds,
            ramp_up_seconds=60
        )
    
    def generate_performance_report(self, results: Dict[str, Any], output_file: str = "performance_report.html"):
        """Generate HTML performance report"""
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Performance Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; }}
                .good {{ background-color: #d4edda; }}
                .warning {{ background-color: #fff3cd; }}
                .error {{ background-color: #f8d7da; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Performance Test Report</h1>
            <p>Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>Test Summary</h2>
            <div class="metric">
                <strong>Test Duration:</strong> {results.get('test_duration', 0):.2f} seconds<br>
                <strong>Total Requests:</strong> {results.get('total_requests', 0)}<br>
                <strong>Performance Grade:</strong> {results.get('performance_grade', 'N/A')}
            </div>
            
            <h2>Response Time Metrics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Mean Response Time</td><td>{results.get('response_time', {}).get('mean', 0):.3f}s</td></tr>
                <tr><td>Median Response Time</td><td>{results.get('response_time', {}).get('median', 0):.3f}s</td></tr>
                <tr><td>95th Percentile</td><td>{results.get('response_time', {}).get('p95', 0):.3f}s</td></tr>
                <tr><td>99th Percentile</td><td>{results.get('response_time', {}).get('p99', 0):.3f}s</td></tr>
                <tr><td>Max Response Time</td><td>{results.get('response_time', {}).get('max', 0):.3f}s</td></tr>
            </table>
            
            <h2>Throughput Metrics</h2>
            <div class="metric">
                <strong>Requests per Second:</strong> {results.get('throughput', {}).get('requests_per_second', 0):.2f}<br>
                <strong>Mean Throughput:</strong> {results.get('throughput', {}).get('mean_throughput', 0):.2f}
            </div>
            
            <h2>Error Rate</h2>
            <div class="metric {'error' if results.get('error_rate', {}).get('overall', 0) > 0.1 else 'good'}">
                <strong>Overall Error Rate:</strong> {results.get('error_rate', {}).get('overall', 0):.2%}<br>
                <strong>Total Errors:</strong> {results.get('error_rate', {}).get('total_errors', 0)}
            </div>
            
            <h2>System Resources</h2>
            <table>
                <tr><th>Resource</th><th>Mean</th><th>Max</th><th>Min</th></tr>
                <tr><td>CPU Usage</td><td>{results.get('system_resources', {}).get('cpu_usage', {}).get('mean', 0):.1f}%</td><td>{results.get('system_resources', {}).get('cpu_usage', {}).get('max', 0):.1f}%</td><td>{results.get('system_resources', {}).get('cpu_usage', {}).get('min', 0):.1f}%</td></tr>
                <tr><td>Memory Usage</td><td>{results.get('system_resources', {}).get('memory_usage', {}).get('mean', 0):.1f}%</td><td>{results.get('system_resources', {}).get('memory_usage', {}).get('max', 0):.1f}%</td><td>{results.get('system_resources', {}).get('memory_usage', {}).get('min', 0):.1f}%</td></tr>
            </table>
        </body>
        </html>
        """
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Performance report generated: {output_file}")

async def main():
    """Main function to run performance tests"""
    
    # Initialize test suite
    test_suite = PerformanceTestSuite()
    
    # Run different types of tests
    logger.info("Running performance tests...")
    
    # 1. Load test
    logger.info("1. Running load test...")
    load_results = await test_suite.run_load_test(
        concurrent_users=20,
        duration_seconds=60,
        ramp_up_seconds=10
    )
    
    # 2. Stress test
    logger.info("2. Running stress test...")
    stress_results = await test_suite.run_stress_test(
        max_concurrent_users=50,
        step_size=5,
        step_duration=30
    )
    
    # 3. Endurance test (shortened for demo)
    logger.info("3. Running endurance test...")
    endurance_results = await test_suite.run_endurance_test(
        concurrent_users=10,
        duration_hours=0.1  # 6 minutes for demo
    )
    
    # Generate reports
    test_suite.generate_performance_report(load_results, "load_test_report.html")
    test_suite.generate_performance_report(stress_results, "stress_test_report.html")
    test_suite.generate_performance_report(endurance_results, "endurance_test_report.html")
    
    # Print summary
    print("\n" + "="*50)
    print("PERFORMANCE TEST SUMMARY")
    print("="*50)
    print(f"Load Test Grade: {load_results.get('performance_grade', 'N/A')}")
    print(f"Stress Test Breaking Point: {stress_results.get('breaking_point', 'N/A')} users")
    print(f"Endurance Test Grade: {endurance_results.get('performance_grade', 'N/A')}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
