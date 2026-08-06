from app.db import get_db

def all_settings(): return {r["key"]:r["value"] for r in get_db().execute("SELECT key,value FROM settings")}
def get_int(key, default=0):
    try: return int(all_settings().get(key,default))
    except ValueError: return default
def update_settings(values):
    db=get_db()
    with db:
        for key,value in values.items(): db.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP",(key,str(value).lower() if isinstance(value,bool) else str(value)))

