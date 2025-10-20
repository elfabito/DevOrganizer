# guardar como scripts/check_redis_migration.py y ejecutar
# filepath: d:\DevOrganizer\scripts\check_redis_migration.py
import os, json, redis
r = redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)
# listar algunos proyectos
for k in r.scan_iter("project:*"):
    print("KEY", k, r.get(k))
    break
# listar algunos weekly summaries
for k in r.scan_iter("weekly:*"):
    print("KEY", k, r.get(k))
    break