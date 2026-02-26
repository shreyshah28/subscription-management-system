import psycopg2

# Connection details
DB_PASS = "shrey28"
DB_NAME = "sub_system"  # ✅ FIXED: Changed from "subscription_sys" to match database.py

print("--- Starting Database Reset ---")

try:
    conn = psycopg2.connect(
        host="localhost", 
        database=DB_NAME, 
        user="postgres", 
        password=DB_PASS
    )
    conn.autocommit = True
    cursor = conn.cursor()

    print("🔄 Connection successful. Wiping tables...")
    
    # This command clears data and resets the ID counters
    cursor.execute("TRUNCATE TABLE users, subscriptions, user_activity, visitors, feedback RESTART IDENTITY CASCADE")
    
    print("✅ SUCCESS: All data has been deleted and ID counters reset.")
    conn.close()

except Exception as e:
    print(f"❌ ERROR: Could not clean database. Reason: {e}")

print("--- Script Finished ---")