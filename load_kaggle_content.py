"""
╔══════════════════════════════════════════════════════════════╗
║         NETFLIX KAGGLE DATASET LOADER                        ║
║                                                              ║
║  HOW TO USE:                                                 ║
║  1. Go to: https://www.kaggle.com/datasets/shivamb/netflix-shows ║
║  2. Download 'netflix_titles.csv'                            ║
║  3. Place it in the same folder as this script               ║
║  4. Run:  python load_kaggle_content.py                      ║
║     Or:   python load_kaggle_content.py --force   (re-seed)  ║
╚══════════════════════════════════════════════════════════════╝
"""

import psycopg2
import pandas as pd
import sys
import os

# ── DB CONFIG (must match your database.py) ──────────────────
DB_HOST = "localhost"
DB_NAME = "sub_system"
DB_USER = "postgres"
DB_PASS = "shrey28"

CSV_FILE = "netflix_titles.csv"   # Name of the Kaggle CSV file


def clean(val):
    """Convert NaN / None to empty string so Postgres is happy."""
    if pd.isna(val):
        return ""
    return str(val).strip()


def main():
    force_mode = "--force" in sys.argv

    # ── 1. Check CSV exists ────────────────────────────────────
    if not os.path.exists(CSV_FILE):
        print(f"\n❌ CSV file '{CSV_FILE}' not found!")
        print("   ➡  Download it from Kaggle:")
        print("      https://www.kaggle.com/datasets/shivamb/netflix-shows")
        print(f"   ➡  Place '{CSV_FILE}' in the same folder as this script.\n")
        sys.exit(1)

    # ── 2. Connect to DB ───────────────────────────────────────
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        conn.autocommit = True
        cursor = conn.cursor()
        print(f"✅ Connected to database: {DB_NAME}")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # ── 3. Check if content already loaded ────────────────────
    cursor.execute("SELECT COUNT(*) FROM content")
    existing = cursor.fetchone()[0]

    if existing > 0 and not force_mode:
        print(f"\nℹ️  Content table already has {existing} rows.")
        print("   Run with '--force' to reload:\n")
        print("   python load_kaggle_content.py --force\n")
        conn.close()
        sys.exit(0)

    # ── 4. Clear old data if force mode ───────────────────────
    if force_mode and existing > 0:
        cursor.execute("TRUNCATE TABLE content RESTART IDENTITY CASCADE")
        print(f"⚠️  FORCE MODE: Cleared {existing} existing rows.")

    # ── 5. Read CSV ────────────────────────────────────────────
    print(f"\n📂 Reading '{CSV_FILE}'...")
    df = pd.read_csv(CSV_FILE)
    total_rows = len(df)
    print(f"   Found {total_rows} titles in the CSV.\n")
    print("─" * 60)

    # ── 6. Insert rows ─────────────────────────────────────────
    success_count = 0
    error_count   = 0

    for idx, row in df.iterrows():
        try:
            # Parse release_year safely
            try:
                release_year = int(row.get("release_year", 0))
            except (ValueError, TypeError):
                release_year = None

            cursor.execute("""
                INSERT INTO content
                    (show_id, content_type, title, director, cast_members,
                     country, date_added, release_year, rating, duration,
                     genre, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                clean(row.get("show_id")),
                clean(row.get("type")),           # 'Movie' or 'TV Show'
                clean(row.get("title")),
                clean(row.get("director")),
                clean(row.get("cast")),
                clean(row.get("country")),
                clean(row.get("date_added")),
                release_year,
                clean(row.get("rating")),
                clean(row.get("duration")),
                clean(row.get("listed_in")),      # genre
                clean(row.get("description")),
            ))
            success_count += 1

            # Progress update every 500 rows
            if success_count % 500 == 0:
                conn.commit()
                print(f"   ✅ Inserted {success_count}/{total_rows} titles...")

        except Exception as e:
            error_count += 1
            print(f"   ⚠️  Row {idx} failed: {e}")
            continue

    # Final commit
    conn.commit()

    # ── 7. Show Summary ────────────────────────────────────────
    print("\n" + "═" * 60)
    print("✅ KAGGLE CONTENT LOAD COMPLETE!")
    print("═" * 60)

    cursor.execute("SELECT COUNT(*) FROM content")
    final_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM content WHERE content_type = 'Movie'")
    movies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM content WHERE content_type = 'TV Show'")
    shows = cursor.fetchone()[0]

    print(f"   📊 Total titles in DB : {final_count}")
    print(f"   🎬 Movies             : {movies}")
    print(f"   📺 TV Shows           : {shows}")
    print(f"   ❌ Errors skipped     : {error_count}")
    print("═" * 60)
    print("\n🎉 Done! Users with an active subscription can now browse")
    print("   the content library inside your Streamlit app.\n")

    conn.close()


if __name__ == "__main__":
    main()