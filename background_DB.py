import os
import time
import sys
import psycopg2
from datetime import datetime

START = "2025-01-01 00:00+00"
END   = "2027-01-01 00:00+00"

LOG_PATH = "backfill_fact_bike_snapshot.log"

def log(msg: str):
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    line = f"{ts} {msg}"

    # 1) Print to stdout (Render Logs)
    print(line, flush=True)

    # 2) Append to file
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception as e:
        # Even logging failures should not kill the worker
        print(f"{ts} [logger] failed to write log file: {e!r}", flush=True)

def main():
    dsn = os.environ["RENDER_DB_URL"]

    log(f"[startup] backfill worker starting")
    log(f"[startup] log file: {LOG_PATH}")
    log(f"[startup] range: {START} -> {END}")

    while True:
        try:
            log("[db] connecting…")
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            cur = conn.cursor()

            log("[db] CALL backfill_fact_bike_snapshot_city_month starting")
            cur.execute(
                "CALL backfill_fact_bike_snapshot_city_month(%s, %s);",
                (START, END),
            )
            log("[db] CALL completed successfully")

            cur.close()
            conn.close()

            log("[worker] procedure finished; sleeping indefinitely")
            while True:
                time.sleep(3600)

        except Exception as e:
            log(f"[error] {type(e).__name__}: {e}")
            log("[worker] sleeping 60s before retry")
            time.sleep(60)

if __name__ == "__main__":
    main()