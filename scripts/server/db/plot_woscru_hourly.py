import sqlite3
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+
import matplotlib.pyplot as plt

# Path to your database (this assumes the script sits next to working.db)
DB_PATH = "working.db"

# Species code for Woodhouse's Scrub-Jay
TARGET_SPECIES = "recros"
TIMESTAMP_COL = "detected_at_utc"

# Timezone for local time in Durango
LOCAL_TZ = ZoneInfo("America/Denver")

def fetch_timestamps():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    query = f"""
        SELECT {TIMESTAMP_COL}
        FROM detections
        WHERE species_code = ?
        ORDER BY {TIMESTAMP_COL}
    """

    cur.execute(query, (TARGET_SPECIES,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def bucket_by_hour(timestamps):
    counts = Counter()

    for ts in timestamps:
        # Parse ISO-8601 string with offset, e.g. "2025-12-07T14:19:03.485+00:00"
        dt_utc = datetime.fromisoformat(ts)

        # Convert to local time
        dt_local = dt_utc.astimezone(LOCAL_TZ)

        # Truncate to the top of the hour
        hour_bucket = dt_local.replace(minute=0, second=0, microsecond=0)

        counts[hour_bucket] += 1

    # Sort by time
    xs = sorted(counts.keys())
    ys = [counts[x] for x in xs]
    return xs, ys

def main():
    timestamps = fetch_timestamps()
    if not timestamps:
        print("No detections found for species:", TARGET_SPECIES)
        return

    n = len(timestamps)  # total number of events in this dataset

    xs, ys = bucket_by_hour(timestamps)

    plt.figure()
    plt.plot(xs, ys, marker="o")
    plt.xlabel("Local time (America/Denver)")
    plt.ylabel("Calls per hour")
    plt.title(f"{TARGET_SPECIES} detections per hour (n={n})")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
