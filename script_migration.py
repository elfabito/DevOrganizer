import os, sqlite3, json
from storage_redis import RedisProjectStorage, get_redis_client

def migrate(db_path='projects.db'):
    rclient = get_redis_client()
    storage = RedisProjectStorage(rclient)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Projects
    for row in cur.execute("SELECT id, name, brief, created_at, user_id, ai_data FROM projects"):
        pid, name, brief, created_at, user_id, ai_data = row
        try:
            ai = json.loads(ai_data) if ai_data else {}
        except Exception:
            ai = ai_data
        storage.save_project({
            "id": pid,
            "name": name,
            "brief": brief,
            "created_at": created_at,
            "user_id": user_id,
            "ai_data": ai
        })

    # Weekly summaries
    for row in cur.execute("SELECT id, project_id, week_start_date, week_notes, ai_summary, created_at FROM weekly_summaries"):
        sid, project_id, week_start_date, week_notes, ai_summary, created_at = row
        try:
            wn = json.loads(week_notes) if week_notes else {}
        except Exception:
            wn = week_notes
        storage.create_weekly_summary(project_id, {
            "project_id": project_id,
            "week_start_date": week_start_date,
            "week_notes": wn,
            "ai_summary": ai_summary,
            "created_at": created_at
        })

    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    migrate(os.getenv("SQLITE_DB", "projects.db"))