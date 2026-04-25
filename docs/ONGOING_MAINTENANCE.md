# Ongoing maintenance documentation and user support resources

**Status (April 2026):** this document is a **template** with sample schedules, scripts, and
placeholder contact hostnames. Operational truth for *this* repository is in
[OPERATIONS_AND_RUNBOOKS.md](OPERATIONS_AND_RUNBOOKS.md), [HOW_TO_RUN.md](../HOW_TO_RUN.md), and
the [README.md](../README.md) support section (replace inboxes/URLs in your org’s fork).

## Table of Contents

1. [Maintenance Procedures](#maintenance-procedures)
2. [Troubleshooting Guide](#troubleshooting-guide)
3. [User Support Resources](#user-support-resources)
4. [Common Issues and Solutions](#common-issues-and-solutions)
5. [Maintenance Schedule](#maintenance-schedule)
6. [Contact Information](#contact-information)

## Maintenance Procedures

### Automated Maintenance

#### Daily Maintenance Script
```bash
# Run daily maintenance tasks
python scripts/automated_maintenance.py --type daily

# View maintenance log
cat logs/maintenance_log.json
```

#### Weekly Maintenance Script
```bash
# Run weekly maintenance tasks
python scripts/automated_maintenance.py --type weekly

# Check maintenance results
python scripts/automated_maintenance.py --type weekly --config maintenance_config.json
```

#### Monthly Maintenance Script
```bash
# Run monthly maintenance tasks
python scripts/automated_maintenance.py --type monthly

# Generate maintenance report
python scripts/automated_maintenance.py --type monthly > monthly_report.txt
```

### Manual Maintenance Tasks

#### Database Maintenance
```bash
# Connect to database
docker compose exec postgres psql -U postgres biomarker_db

# Run VACUUM ANALYZE
VACUUM ANALYZE;

# Check database size
SELECT pg_size_pretty(pg_database_size('biomarker_db'));

# Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

#### Cache Maintenance
```bash
# Connect to Redis
docker compose exec redis redis-cli

# Check Redis info
INFO stats
INFO memory

# Flush cache (use with caution)
FLUSHDB

# Check key count
DBSIZE
```

#### Log Management
```bash
# View application logs
docker compose logs -f backend

# View database logs
docker compose logs -f postgres

# View Prometheus logs (only if you started the prod stack with a prometheus service)
docker compose -f docker-compose.prod.yml logs -f prometheus

# Rotate logs
logrotate -f /etc/logrotate.d/biomarker-identifier
```

#### Backup Procedures

This repo includes [`scripts/ops/backup_postgres.sh`](../scripts/ops/backup_postgres.sh) and [`scripts/ops/restore_postgres.sh`](../scripts/ops/restore_postgres.sh) (require `DATABASE_URL` or use from a host with `pg_dump`/`psql`).

```bash
# Example: logical backup (see script for options)
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/biomarker_db"  # default dev mapping from docker-compose.yml
./scripts/ops/backup_postgres.sh ./backups

# Or via Docker
docker compose exec postgres pg_dump -U postgres biomarker_db | gzip > backup.sql.gz
```

## Troubleshooting Guide

### Common Issues

#### Issue: Service Not Starting

**Symptoms:**
- Service fails to start
- Error messages in logs
- Container exits immediately

**Diagnosis:**
```bash
# Check service status
docker compose ps

# View service logs
docker compose logs service_name

# Check container health
docker inspect container_name | grep Health
```

**Solutions:**
1. Check environment variables
2. Verify database connectivity
3. Review configuration files
4. Check resource availability (CPU, memory, disk)

#### Issue: High Database Load

**Symptoms:**
- Slow query responses
- High CPU usage
- Connection pool exhaustion

**Diagnosis:**
```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check table sizes
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public';
```

**Solutions:**
1. Optimize slow queries
2. Add database indexes
3. Increase connection pool size
4. Scale database resources
5. Review query patterns

#### Issue: High Memory Usage

**Symptoms:**
- System memory near capacity
- OOM (Out of Memory) errors
- Slow application performance

**Diagnosis:**
```bash
# Check memory usage
free -h

# Check process memory
ps aux --sort=-%mem | head

# Check Docker container memory
docker stats
```

**Solutions:**
1. Increase container memory limits
2. Optimize application memory usage
3. Implement caching strategies
4. Review data processing workflows
5. Scale horizontally

#### Issue: Cache Performance Issues

**Symptoms:**
- Low cache hit rates
- High cache memory usage
- Slow cache operations

**Diagnosis:**
```bash
# Connect to Redis
docker compose exec redis redis-cli

# Check cache statistics
INFO stats
INFO memory

# Check cache hit rate
INFO stats | grep keyspace_hits
```

**Solutions:**
1. Optimize cache TTL settings
2. Implement cache warming
3. Review cache eviction policies
4. Scale Redis resources
5. Analyze cache access patterns

### Performance Issues

#### Slow API Responses

**Diagnosis:**
1. Check API response times in monitoring dashboard
2. Review slow query logs
3. Analyze database query performance
4. Check cache hit rates

**Solutions:**
1. Optimize database queries
2. Implement API response caching
3. Add database indexes
4. Scale application resources
5. Review API rate limiting

#### High CPU Usage

**Diagnosis:**
```bash
# Check CPU usage
top
htop

# Check process CPU usage
ps aux --sort=-%cpu | head

# Check Docker container CPU
docker stats
```

**Solutions:**
1. Optimize application code
2. Scale application horizontally
3. Review background tasks
4. Optimize data processing
5. Upgrade CPU resources

### Data Issues

#### Data Integrity Issues

**Diagnosis:**
```sql
-- Check for data inconsistencies
SELECT COUNT(*) FROM analysis_runs WHERE status IS NULL;

-- Check for orphaned records
SELECT * FROM biomarker_results 
WHERE run_id NOT IN (SELECT id FROM analysis_runs);
```

**Solutions:**
1. Run data integrity checks
2. Fix data inconsistencies
3. Implement data validation
4. Review data processing workflows
5. Restore from backup if needed

## User Support Resources

### User Documentation

#### Getting Started
- **Quick Start Guide**: `docs/USER_GUIDE.md`
- **Installation Guide**: `docs/DEPLOYMENT_GUIDE.md`
- **Video / hosted docs:** link your own portal if you have one; otherwise use the in-repo `docs/` tree and live `/docs` API

#### User Manuals
- **Complete User Manual**: `docs/USER_MANUAL.md`
- **Training Guide**: `docs/USER_TRAINING_GUIDE.md`
- **API Reference**: `docs/API_DOCUMENTATION.md`

### Support channels

Use the **Support** and **Community** section in the root [README.md](../README.md) for
GitHub Issues, Discussions, and maintainer email. Define your own SLAs in an internal
runbook for production deployments.

### Support Tiers

#### Tier 1: Basic Support
- Email support (24-48 hour response)
- Documentation access
- Community forum access

#### Tier 2: Standard Support
- Email support (24 hour response)
- Priority documentation access
- Technical guidance
- Bug reporting

#### Tier 3: Premium Support
- Email support (4 hour response)
- Phone support (business hours)
- Dedicated support engineer
- Custom development assistance

### Frequently Asked Questions (FAQ)

#### Q: How do I upload data?
**A:** Use the Data Upload page in the web interface. Supported formats include TSV, CSV, and Excel. See `docs/USER_MANUAL.md` for detailed instructions.

#### Q: How long does an analysis take?
**A:** Analysis time depends on data size and complexity. Typical analyses take 10-30 minutes. Large datasets may take several hours.

#### Q: How do I export results?
**A:** Results can be exported from the Results page. Supported formats include CSV, Excel, and PDF. API access is also available.

#### Q: How do I share analysis results?
**A:** Use the sharing features in the Results page. You can generate shareable links or export results for external sharing.

#### Q: What are the system requirements?
**A:** See `docs/DEPLOYMENT_GUIDE.md` for complete system requirements. Minimum: 4 CPU cores, 8GB RAM, 100GB storage.

## Common Issues and Solutions

### Upload Issues

#### Problem: File Upload Fails
**Solution:**
1. Check file format (TSV, CSV, Excel)
2. Verify file size (default limits are on the order of 100MB per upload in app settings; check your environment)
3. Check network connectivity
4. Review file encoding (UTF-8 recommended)
5. Check server logs for errors

#### Problem: Upload is Slow
**Solution:**
1. Check network speed
2. Compress large files
3. Use optimized file formats
4. Check server load
5. Contact support if persistent

### Analysis Issues

#### Problem: Analysis Fails
**Solution:**
1. Check data format and quality
2. Review error logs
3. Verify data requirements
4. Check system resources
5. Contact support with error details

#### Problem: Analysis Takes Too Long
**Solution:**
1. Check data size
2. Review system resources
3. Optimize data preprocessing
4. Consider data sampling
5. Contact support for optimization

### Results Issues

#### Problem: Results Not Displaying
**Solution:**
1. Refresh the page
2. Check browser console for errors
3. Verify analysis completed successfully
4. Clear browser cache
5. Contact support if persistent

#### Problem: Export Fails
**Solution:**
1. Check file permissions
2. Verify disk space
3. Try different export format
4. Check browser settings
5. Contact support if persistent

## Maintenance Schedule

### Daily Schedule
- **Morning (8:00 AM)**: System health check, review alerts
- **Midday (12:00 PM)**: Performance metrics review
- **Evening (6:00 PM)**: Daily maintenance script execution

### Weekly Schedule
- **Monday**: Weekly maintenance tasks, backup verification
- **Wednesday**: Performance optimization, security updates
- **Friday**: Documentation updates, system review

### Monthly Schedule
- **First Week**: Comprehensive system backup, security audit
- **Second Week**: Performance analysis, optimization
- **Third Week**: Documentation review, roadmap updates
- **Fourth Week**: Disaster recovery testing, capacity planning

### Quarterly Schedule
- **Quarter Start**: Comprehensive system review
- **Quarter Middle**: Major updates, feature releases
- **Quarter End**: Planning for next quarter

## Contact information

See [README.md](../README.md). This open-source handover does not ship a dedicated
support hotline or generic `@biomarker-identifier.com` inboxes.

## Maintenance Log Template

```json
{
  "date": "2025-02-05",
  "maintenance_type": "daily",
  "tasks_completed": [
    {
      "task": "database_vacuum",
      "status": "success",
      "duration": "5 minutes",
      "notes": "Vacuumed all tables successfully"
    }
  ],
  "issues_found": [],
  "actions_taken": [],
  "next_maintenance": "2025-02-06"
}
```

## Additional Resources

### External Documentation
- **Kubernetes**: https://kubernetes.io/docs/
- **Docker**: https://docs.docker.com/
- **PostgreSQL**: https://www.postgresql.org/docs/
- **Redis**: https://redis.io/documentation

### Training Resources
- **System Administration Training**: Available quarterly
- **User Training**: Available monthly
- **Developer Training**: Available on-demand
- **Video Tutorials**: Available on documentation portal

---

**Last Updated**: February 2025  
**Next Review**: March 2025  
**Maintained By**: System Administration Team

