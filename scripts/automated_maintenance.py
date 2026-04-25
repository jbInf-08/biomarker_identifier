"""
Automated Maintenance Procedures
Automated system maintenance and performance optimization strategies
"""

import os
import sys
import logging
import subprocess
import json
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import shutil
import sqlite3
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('maintenance.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutomatedMaintenance:
    """Automated maintenance procedures for system optimization"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.maintenance_log = []
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load maintenance configuration"""
        default_config = {
            'database': {
                'vacuum_threshold_days': 7,
                'analyze_threshold_days': 1,
                'backup_retention_days': 30,
                'max_connection_age_hours': 24
            },
            'cache': {
                'redis_flush_pattern': None,
                'cache_ttl_cleanup_days': 30
            },
            'storage': {
                'temp_file_cleanup_days': 7,
                'log_rotation_days': 30,
                'old_backup_cleanup_days': 60
            },
            'performance': {
                'slow_query_threshold_ms': 1000,
                'index_rebuild_threshold_days': 14,
                'statistics_update_threshold_days': 7
            },
            'alerts': {
                'disk_usage_threshold': 85,
                'memory_usage_threshold': 90,
                'cpu_usage_threshold': 80
            }
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def run_daily_maintenance(self):
        """Run daily maintenance tasks"""
        logger.info("Starting daily maintenance tasks")
        
        tasks = [
            ('database_vacuum', self._vacuum_database),
            ('cache_cleanup', self._cleanup_cache),
            ('temp_file_cleanup', self._cleanup_temp_files),
            ('log_rotation', self._rotate_logs),
            ('system_health_check', self._system_health_check),
            ('performance_metrics', self._collect_performance_metrics)
        ]
        
        results = {}
        for task_name, task_func in tasks:
            try:
                logger.info(f"Running task: {task_name}")
                result = task_func()
                results[task_name] = {'status': 'success', 'result': result}
                self.maintenance_log.append({
                    'task': task_name,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'success'
                })
            except Exception as e:
                logger.error(f"Error in task {task_name}: {str(e)}")
                results[task_name] = {'status': 'error', 'error': str(e)}
                self.maintenance_log.append({
                    'task': task_name,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'error',
                    'error': str(e)
                })
        
        self._save_maintenance_log()
        logger.info("Daily maintenance tasks completed")
        return results
    
    def run_weekly_maintenance(self):
        """Run weekly maintenance tasks"""
        logger.info("Starting weekly maintenance tasks")
        
        tasks = [
            ('database_analyze', self._analyze_database),
            ('index_rebuild', self._rebuild_indexes),
            ('backup_cleanup', self._cleanup_old_backups),
            ('storage_optimization', self._optimize_storage),
            ('security_audit', self._security_audit)
        ]
        
        results = {}
        for task_name, task_func in tasks:
            try:
                logger.info(f"Running task: {task_name}")
                result = task_func()
                results[task_name] = {'status': 'success', 'result': result}
            except Exception as e:
                logger.error(f"Error in task {task_name}: {str(e)}")
                results[task_name] = {'status': 'error', 'error': str(e)}
        
        self._save_maintenance_log()
        logger.info("Weekly maintenance tasks completed")
        return results
    
    def run_monthly_maintenance(self):
        """Run monthly maintenance tasks"""
        logger.info("Starting monthly maintenance tasks")
        
        tasks = [
            ('full_database_backup', self._create_full_backup),
            ('comprehensive_health_check', self._comprehensive_health_check),
            ('performance_optimization', self._optimize_performance),
            ('documentation_update', self._update_documentation)
        ]
        
        results = {}
        for task_name, task_func in tasks:
            try:
                logger.info(f"Running task: {task_name}")
                result = task_func()
                results[task_name] = {'status': 'success', 'result': result}
            except Exception as e:
                logger.error(f"Error in task {task_name}: {str(e)}")
                results[task_name] = {'status': 'error', 'error': str(e)}
        
        self._save_maintenance_log()
        logger.info("Monthly maintenance tasks completed")
        return results
    
    def _vacuum_database(self) -> Dict[str, Any]:
        """Vacuum database to reclaim space"""
        try:
            database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/biomarker_db')
            engine = create_engine(database_url)
            
            with engine.connect() as conn:
                # Check when last vacuum was run
                result = conn.execute(text("""
                    SELECT last_vacuum, last_autovacuum 
                    FROM pg_stat_user_tables 
                    WHERE schemaname = 'public'
                    LIMIT 1
                """))
                
                # Run VACUUM ANALYZE on all tables
                conn.execute(text("VACUUM ANALYZE"))
                conn.commit()
                
                logger.info("Database vacuum completed")
                return {'vacuumed': True, 'timestamp': datetime.now().isoformat()}
                
        except Exception as e:
            logger.error(f"Error vacuuming database: {str(e)}")
            raise
    
    def _analyze_database(self) -> Dict[str, Any]:
        """Analyze database statistics"""
        try:
            database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/biomarker_db')
            engine = create_engine(database_url)
            
            with engine.connect() as conn:
                # Analyze all tables
                conn.execute(text("ANALYZE"))
                conn.commit()
                
                logger.info("Database analysis completed")
                return {'analyzed': True, 'timestamp': datetime.now().isoformat()}
                
        except Exception as e:
            logger.error(f"Error analyzing database: {str(e)}")
            raise
    
    def _rebuild_indexes(self) -> Dict[str, Any]:
        """Rebuild database indexes"""
        try:
            database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/biomarker_db')
            engine = create_engine(database_url)
            
            with engine.connect() as conn:
                # Get index information
                result = conn.execute(text("""
                    SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
                    FROM pg_stat_user_indexes
                    WHERE schemaname = 'public'
                """))
                
                indexes_rebuilt = 0
                for row in result:
                    # Rebuild indexes with low usage
                    if row.idx_scan < 100:  # Low usage threshold
                        try:
                            conn.execute(text(f"REINDEX INDEX CONCURRENTLY {row.indexname}"))
                            indexes_rebuilt += 1
                        except Exception as e:
                            logger.warning(f"Could not rebuild index {row.indexname}: {str(e)}")
                
                conn.commit()
                
                logger.info(f"Rebuilt {indexes_rebuilt} indexes")
                return {'indexes_rebuilt': indexes_rebuilt, 'timestamp': datetime.now().isoformat()}
                
        except Exception as e:
            logger.error(f"Error rebuilding indexes: {str(e)}")
            raise
    
    def _cleanup_cache(self) -> Dict[str, Any]:
        """Cleanup cache (Redis)"""
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            r = redis.from_url(redis_url)
            
            # Get cache statistics
            info = r.info('stats')
            keys_before = r.dbsize()
            
            # Cleanup expired keys (Redis does this automatically, but we can force cleanup)
            # Clear old cache entries based on pattern
            if self.config['cache']['redis_flush_pattern']:
                pattern = self.config['cache']['redis_flush_pattern']
                keys_deleted = 0
                for key in r.scan_iter(match=pattern):
                    r.delete(key)
                    keys_deleted += 1
            else:
                # Standard cleanup - Redis handles TTL automatically
                keys_deleted = 0
            
            keys_after = r.dbsize()
            
            logger.info(f"Cache cleanup: {keys_before - keys_after} keys removed")
            return {
                'keys_before': keys_before,
                'keys_after': keys_after,
                'keys_deleted': keys_before - keys_after,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning cache: {str(e)}")
            raise
    
    def _cleanup_temp_files(self) -> Dict[str, Any]:
        """Cleanup temporary files"""
        try:
            temp_dirs = [
                '/tmp/biomarker_identifier',
                '/var/tmp/biomarker_identifier',
                os.path.join(os.getenv('HOME', '/'), '.biomarker_identifier', 'temp')
            ]
            
            cutoff_date = datetime.now() - timedelta(days=self.config['storage']['temp_file_cleanup_days'])
            total_size = 0
            files_deleted = 0
            
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if file_time < cutoff_date:
                                    file_size = os.path.getsize(file_path)
                                    os.remove(file_path)
                                    total_size += file_size
                                    files_deleted += 1
                            except Exception as e:
                                logger.warning(f"Could not delete {file_path}: {str(e)}")
            
            logger.info(f"Cleaned up {files_deleted} temporary files ({total_size / 1024 / 1024:.2f} MB)")
            return {
                'files_deleted': files_deleted,
                'size_freed_mb': total_size / 1024 / 1024,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning temp files: {str(e)}")
            raise
    
    def _rotate_logs(self) -> Dict[str, Any]:
        """Rotate log files"""
        try:
            log_dirs = [
                '/var/log/biomarker_identifier',
                './logs'
            ]
            
            cutoff_date = datetime.now() - timedelta(days=self.config['storage']['log_rotation_days'])
            files_rotated = 0
            
            for log_dir in log_dirs:
                if os.path.exists(log_dir):
                    for file in os.listdir(log_dir):
                        if file.endswith('.log'):
                            file_path = os.path.join(log_dir, file)
                            try:
                                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if file_time < cutoff_date:
                                    # Compress old logs
                                    if not file.endswith('.gz'):
                                        subprocess.run(['gzip', file_path], check=False)
                                    files_rotated += 1
                                    
                                    # Delete very old compressed logs
                                    if file_time < cutoff_date - timedelta(days=90):
                                        gz_path = file_path + '.gz'
                                        if os.path.exists(gz_path):
                                            os.remove(gz_path)
                            except Exception as e:
                                logger.warning(f"Could not rotate log {file_path}: {str(e)}")
            
            logger.info(f"Rotated {files_rotated} log files")
            return {
                'files_rotated': files_rotated,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error rotating logs: {str(e)}")
            raise
    
    def _cleanup_old_backups(self) -> Dict[str, Any]:
        """Cleanup old backup files"""
        try:
            backup_dirs = [
                '/opt/backups/biomarker_identifier',
                './backups'
            ]
            
            cutoff_date = datetime.now() - timedelta(days=self.config['storage']['old_backup_cleanup_days'])
            backups_deleted = 0
            size_freed = 0
            
            for backup_dir in backup_dirs:
                if os.path.exists(backup_dir):
                    for file in os.listdir(backup_dir):
                        if file.endswith(('.sql', '.sql.gz', '.tar.gz', '.bak')):
                            file_path = os.path.join(backup_dir, file)
                            try:
                                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if file_time < cutoff_date:
                                    file_size = os.path.getsize(file_path)
                                    os.remove(file_path)
                                    size_freed += file_size
                                    backups_deleted += 1
                            except Exception as e:
                                logger.warning(f"Could not delete backup {file_path}: {str(e)}")
            
            logger.info(f"Cleaned up {backups_deleted} old backups ({size_freed / 1024 / 1024:.2f} MB)")
            return {
                'backups_deleted': backups_deleted,
                'size_freed_mb': size_freed / 1024 / 1024,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning backups: {str(e)}")
            raise
    
    def _system_health_check(self) -> Dict[str, Any]:
        """Perform system health check"""
        try:
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'cpu_usage': psutil.cpu_percent(interval=1),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'status': 'healthy'
            }
            
            # Check thresholds
            if health_status['disk_usage'] > self.config['alerts']['disk_usage_threshold']:
                health_status['status'] = 'warning'
                health_status['warnings'] = ['High disk usage']
            
            if health_status['memory_usage'] > self.config['alerts']['memory_usage_threshold']:
                health_status['status'] = 'warning'
                if 'warnings' not in health_status:
                    health_status['warnings'] = []
                health_status['warnings'].append('High memory usage')
            
            if health_status['cpu_usage'] > self.config['alerts']['cpu_usage_threshold']:
                health_status['status'] = 'warning'
                if 'warnings' not in health_status:
                    health_status['warnings'] = []
                health_status['warnings'].append('High CPU usage')
            
            logger.info(f"System health check: {health_status['status']}")
            return health_status
            
        except Exception as e:
            logger.error(f"Error in health check: {str(e)}")
            raise
    
    def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics"""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_percent': psutil.disk_usage('/').percent,
                    'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                },
                'network': dict(psutil.net_io_counters()._asdict()) if hasattr(psutil, 'net_io_counters') else {},
                'processes': {
                    'total': len(psutil.pids()),
                    'running': len([p for p in psutil.process_iter(['status']) if p.info['status'] == 'running'])
                }
            }
            
            # Save metrics to file
            metrics_file = './logs/performance_metrics.json'
            os.makedirs(os.path.dirname(metrics_file), exist_ok=True)
            
            if os.path.exists(metrics_file):
                with open(metrics_file, 'r') as f:
                    all_metrics = json.load(f)
            else:
                all_metrics = []
            
            all_metrics.append(metrics)
            
            # Keep only last 1000 entries
            if len(all_metrics) > 1000:
                all_metrics = all_metrics[-1000:]
            
            with open(metrics_file, 'w') as f:
                json.dump(all_metrics, f, indent=2)
            
            logger.info("Performance metrics collected")
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {str(e)}")
            raise
    
    def _create_full_backup(self) -> Dict[str, Any]:
        """Create full system backup"""
        try:
            backup_dir = '/opt/backups/biomarker_identifier'
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'full_backup_{timestamp}.tar.gz')
            
            # Backup database
            database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/biomarker_db')
            db_backup_file = os.path.join(backup_dir, f'db_backup_{timestamp}.sql')
            
            subprocess.run([
                'pg_dump',
                database_url.replace('postgresql://', '').split('/')[0],
                '-f', db_backup_file
            ], check=False)
            
            # Create archive
            with tarfile.open(backup_file, 'w:gz') as tar:
                tar.add(db_backup_file, arcname='database.sql')
                # Add other important directories
                data_dirs = ['./data', './config']
                for data_dir in data_dirs:
                    if os.path.exists(data_dir):
                        tar.add(data_dir, arcname=os.path.basename(data_dir))
            
            # Remove temporary database backup
            if os.path.exists(db_backup_file):
                os.remove(db_backup_file)
            
            backup_size = os.path.getsize(backup_file) / 1024 / 1024
            
            logger.info(f"Full backup created: {backup_file} ({backup_size:.2f} MB)")
            return {
                'backup_file': backup_file,
                'size_mb': backup_size,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            raise
    
    def _optimize_storage(self) -> Dict[str, Any]:
        """Optimize storage usage"""
        try:
            optimization_results = {
                'timestamp': datetime.now().isoformat(),
                'actions_taken': []
            }
            
            # Compress old data files
            data_dirs = ['./data/processed', './data/raw']
            for data_dir in data_dirs:
                if os.path.exists(data_dir):
                    for root, dirs, files in os.walk(data_dir):
                        for file in files:
                            if not file.endswith('.gz') and os.path.getsize(os.path.join(root, file)) > 100 * 1024 * 1024:  # > 100MB
                                file_path = os.path.join(root, file)
                                try:
                                    subprocess.run(['gzip', file_path], check=False)
                                    optimization_results['actions_taken'].append(f'Compressed: {file_path}')
                                except Exception as e:
                                    logger.warning(f"Could not compress {file_path}: {str(e)}")
            
            logger.info(f"Storage optimization: {len(optimization_results['actions_taken'])} actions taken")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Error optimizing storage: {str(e)}")
            raise
    
    def _security_audit(self) -> Dict[str, Any]:
        """Perform security audit"""
        try:
            audit_results = {
                'timestamp': datetime.now().isoformat(),
                'checks_performed': [],
                'issues_found': []
            }
            
            # Check file permissions
            important_files = ['./.env', './config.json']
            for file_path in important_files:
                if os.path.exists(file_path):
                    file_stat = os.stat(file_path)
                    if file_stat.st_mode & 0o077 != 0:
                        audit_results['issues_found'].append(f'Insecure permissions on {file_path}')
                    audit_results['checks_performed'].append(f'Checked permissions: {file_path}')
            
            # Check for default passwords (simplified check)
            if os.path.exists('./.env'):
                with open('./.env', 'r') as f:
                    env_content = f.read()
                    if 'password=password' in env_content.lower() or 'password=123' in env_content.lower():
                        audit_results['issues_found'].append('Possible default password detected')
            
            logger.info(f"Security audit: {len(audit_results['checks_performed'])} checks, {len(audit_results['issues_found'])} issues")
            return audit_results
            
        except Exception as e:
            logger.error(f"Error in security audit: {str(e)}")
            raise
    
    def _comprehensive_health_check(self) -> Dict[str, Any]:
        """Comprehensive system health check"""
        try:
            health = self._system_health_check()
            
            # Additional checks
            health['services'] = self._check_services()
            health['database'] = self._check_database_health()
            health['storage'] = self._check_storage_health()
            
            return health
            
        except Exception as e:
            logger.error(f"Error in comprehensive health check: {str(e)}")
            raise
    
    def _check_services(self) -> Dict[str, Any]:
        """Check service status"""
        try:
            services = {}
            
            # Check if services are running (simplified)
            try:
                import redis
                r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
                r.ping()
                services['redis'] = 'running'
            except:
                services['redis'] = 'not_running'
            
            return services
            
        except Exception as e:
            logger.error(f"Error checking services: {str(e)}")
            return {'error': str(e)}
    
    def _check_database_health(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/biomarker_db')
            engine = create_engine(database_url)
            
            with engine.connect() as conn:
                # Check connection
                result = conn.execute(text("SELECT 1"))
                result.scalar()
                
                # Get database size
                size_result = conn.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
                db_size = size_result.scalar()
                
                # Get connection count
                conn_result = conn.execute(text("SELECT count(*) FROM pg_stat_activity"))
                conn_count = conn_result.scalar()
                
                return {
                    'status': 'healthy',
                    'size': db_size,
                    'connections': conn_count
                }
                
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}
    
    def _check_storage_health(self) -> Dict[str, Any]:
        """Check storage health"""
        try:
            disk = psutil.disk_usage('/')
            return {
                'total_gb': disk.total / 1024 / 1024 / 1024,
                'used_gb': disk.used / 1024 / 1024 / 1024,
                'free_gb': disk.free / 1024 / 1024 / 1024,
                'percent': disk.percent
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _optimize_performance(self) -> Dict[str, Any]:
        """Optimize system performance"""
        try:
            optimizations = {
                'timestamp': datetime.now().isoformat(),
                'actions': []
            }
            
            # Database optimization
            try:
                self._analyze_database()
                optimizations['actions'].append('Database statistics updated')
            except Exception as e:
                logger.warning(f"Database optimization failed: {str(e)}")
            
            # Cache optimization
            try:
                self._cleanup_cache()
                optimizations['actions'].append('Cache optimized')
            except Exception as e:
                logger.warning(f"Cache optimization failed: {str(e)}")
            
            logger.info(f"Performance optimization: {len(optimizations['actions'])} actions")
            return optimizations
            
        except Exception as e:
            logger.error(f"Error optimizing performance: {str(e)}")
            raise
    
    def _update_documentation(self) -> Dict[str, Any]:
        """Update maintenance documentation"""
        try:
            # This would update documentation based on maintenance logs
            logger.info("Documentation update (placeholder)")
            return {'updated': True, 'timestamp': datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"Error updating documentation: {str(e)}")
            raise
    
    def _save_maintenance_log(self):
        """Save maintenance log"""
        try:
            log_file = './logs/maintenance_log.json'
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            with open(log_file, 'w') as f:
                json.dump(self.maintenance_log, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving maintenance log: {str(e)}")

def main():
    """Main entry point for maintenance script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Maintenance Procedures')
    parser.add_argument('--type', choices=['daily', 'weekly', 'monthly'], default='daily',
                       help='Type of maintenance to run')
    parser.add_argument('--config', help='Path to configuration file')
    
    args = parser.parse_args()
    
    maintenance = AutomatedMaintenance(config_path=args.config)
    
    if args.type == 'daily':
        results = maintenance.run_daily_maintenance()
    elif args.type == 'weekly':
        results = maintenance.run_weekly_maintenance()
    elif args.type == 'monthly':
        results = maintenance.run_monthly_maintenance()
    
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    import tarfile  # Import here to avoid issues if not available
    main()

