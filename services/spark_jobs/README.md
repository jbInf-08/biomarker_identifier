# Spark job submission (optional)

The API remains a **single FastAPI service**. For batch-heavy steps (e.g. large matrix normalization), submit Spark jobs to the cluster defined in `docker-compose.spark.yml` using `spark-submit` or PySpark from a dedicated worker container.

Suggested boundaries:

- **API service**: orchestration, auth, Celery for medium tasks.
- **Spark**: offline ETL, feature matrices, or exports that exceed single-node memory.

No code in this repo assumes Spark by default; wire your pipeline when a dataset exceeds local limits.
