import psycopg2
import random
import hashlib
from datetime import datetime, timedelta
import sys

# --- CONFIGURATION ---
DB_PASS = "shrey28"
DB_NAME = "sub_system"
DB_USER = "postgres"
DB_HOST = "localhost"

def h(p): return hashlib.sha256(p.encode()).hexdigest()

# --- EXPANDED DATA LISTS ---
first_names = ["Aarav", "Aditya", "Amit", "Amita", "Anjali", "Ankita", "Arjun", "Bhavesh", "Chetan", "Deepak", "Dhruv",
    "Divya", "Gaurav", "Gauri", "Himanshu", "Ishaan", "Karan", "Kiran", "Lakshmi", "Madhur", "Meera",
    "Mohit", "Neha", "Nikhil", "Niraj", "Pooja", "Pradeep", "Prakash", "Priya", "Pratik", "Puneet", "Rahul",
    "Raj", "Ravi", "Reema", "Riya", "Rohit", "Rohan", "Sachin", "Sandeep", "Sanjay", "Saurabh", "Shivam", "Shreya", "Siddharth",
    "Sneha", "Sourabh", "Srijan", "Suman", "Sunil", "Swati", "Tanvi", "Tushar", "Uday", "Vikram", "Vikas", "Vinay", "Vishal", "Yash", "Yuvraj"
]

last_names = ["Agarwal", "Bhattacharya", "Chopra", "Das", "Deshpande", "Dixit", "Dubey", "Ganguly", "Garg", "Ghosh",
    "Gupta", "Iyer", "Jain", "Jha", "Joshi", "Kapoor", "Kumar", "Mishra", "Nair", "Panda", "Patel", "Prajapati",
    "Rao", "Reddy", "Roy", "Saxena", "Sen", "Sharma", "Singh", "Verma", "Yadav"]

countries = ["India", "USA", "UK", "Canada", "Germany", "France", "Australia", "Japan", "Brazil", "Italy", "Spain"]
genders   = ["Male", "Female", "Other"]

netflix_plans = [
    ("Mobile",   149),
    ("Standard", 499),
    ("Premium",  649)
]

# =============================================================
#  HOW MONTHLY REVENUE SEEDING WORKS:
#
#  Each seeded user gets a subscription start_date somewhere
#  in the past 6 months. We NOW ALSO insert a matching row
#  into the payments table using that same historical date.
#
#  This means:
#  - Past month revenue charts show realistic historical data
#  - Re-running seed (--force) safely clears old payments first
#    so numbers never double-up
#  - Real users who buy plans through the app add to payments
#    table just like before - both work side by side correctly
# =============================================================

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
    conn.autocommit = False
    cursor = conn.cursor()
    print(f"Connected to Database: {DB_NAME}")
    print("--------------------------------------------------")

    # --- 1. FORCE MODE CHECK ---
    force_check = "--force" in sys.argv
    if force_check:
        print("FORCE MODE ON - clearing seeded data and re-seeding.")

    # --- 2. COUNT EXISTING USERS ---
    # We identify seeded users by their mobile = '9999988888'
    # Real users registered through the app will have a different mobile number
    # so they are NEVER touched by this script, even in --force mode.
    cursor.execute("SELECT COUNT(*) FROM users WHERE mobile = '9999988888'")
    existing_count = cursor.fetchone()[0]

    if existing_count > 0 and not force_check:
        print(f"Table already has {existing_count} seeded users. Skipping seeding.")
        print(f"TIP: Run with '--force' to clear and re-seed ONLY the fake seeded users:")
        print(f"   python seed_netflix_realistic.py --force")
        print(f"NOTE: Real users registered through the app are NEVER affected.")
        conn.close()
        sys.exit(0)

    # --- 3. IF FORCE - DELETE ONLY SEEDED DATA SAFELY ---
    #
    # IMPORTANT: We delete ONLY users where mobile = '9999988888'
    # This is the unique tag given to all seeded/fake users.
    # Real users who registered through the app have real mobile numbers
    # and are completely safe — they will NEVER be deleted by this script.
    #
    # Delete order respects foreign key constraints:
    # mutual_invites -> payments -> user_activity -> subscriptions -> feedback -> users
    #
    if force_check and existing_count > 0:
        print("--------------------------------------------------")
        print("FORCE MODE: Removing ONLY seeded fake users (mobile = 9999988888)...")
        print("Real users registered through the app are NOT affected.")
        print("--------------------------------------------------")

        cursor.execute("SELECT user_id FROM users WHERE mobile = '9999988888'")
        seeded_ids = [r[0] for r in cursor.fetchall()]

        if seeded_ids:
            ids_str = ','.join(str(i) for i in seeded_ids)
            cursor.execute(f"DELETE FROM mutual_invites WHERE user_id IN ({ids_str})")
            cursor.execute(f"DELETE FROM payments      WHERE user_id IN ({ids_str})")
            cursor.execute(f"DELETE FROM user_activity WHERE user_id IN ({ids_str})")
            cursor.execute(f"DELETE FROM subscriptions WHERE user_id IN ({ids_str})")
            cursor.execute(f"DELETE FROM feedback      WHERE user_id IN ({ids_str})")
            cursor.execute(f"DELETE FROM users         WHERE user_id IN ({ids_str})")

        conn.commit()
        print(f"✅ Cleared {len(seeded_ids)} seeded users and their linked data.")
        print(f"✅ All real user accounts and payments are untouched.")
        print("--------------------------------------------------")

    # --- 4. SEED 150 USERS ---
    print("Seeding 150 Users with realistic historical payment data...")
    print("--------------------------------------------------")

    now = datetime.now()

    for i in range(1, 151):
        try:
            # Generate user data
            full_name      = f"{random.choice(first_names)} {random.choice(last_names)}"
            email          = f"{full_name.replace(' ', '').lower()}{random.randint(10000,99999)}@gmail.com"
            age            = random.randint(15, 80)
            user_country   = random.choice(countries)
            user_gender    = random.choice(genders)
            plain_password = "1234"
            hashed_pw      = h(plain_password)
            mobile         = "9999988888"

            # Registration time: random in past 6 months
            reg_offset_days = random.randint(10, 180)
            reg_time        = now - timedelta(days=reg_offset_days)

            # Insert User
            cursor.execute("""
                INSERT INTO users
                    (fullname, email, password, mobile, age, country, gender, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING user_id
            """, (full_name, email, hashed_pw, mobile, age,
                  user_country, user_gender, reg_time))
            uid = cursor.fetchone()[0]

            # Subscription Logic: 80% chance
            has_subscription = False
            sub_start_date   = None
            plan_name        = None
            plan_price       = None

            if random.random() < 0.8:
                plan_name, plan_price = random.choice(netflix_plans)

                # Subscription starts 0-5 days after registration
                sub_start_date = reg_time + timedelta(days=random.randint(0, 5))
                sub_end_date   = sub_start_date + timedelta(days=30)

                # Status based on whether end_date has passed
                sub_status = "ACTIVE" if sub_end_date > now else "EXPIRED"

                # Insert Subscription
                cursor.execute("""
                    INSERT INTO subscriptions
                        (user_id, service_type, plan_name, amount,
                         start_date, end_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING subscription_id
                """, (uid, "Netflix", plan_name, plan_price,
                      sub_start_date, sub_end_date, sub_status))
                sub_id = cursor.fetchone()[0]

                # ================================================
                #  INSERT INTO PAYMENTS TABLE
                #
                #  60% NEW / 40% RENEWAL split for realistic data.
                #  RENEWAL users also get an older NEW record so
                #  the monthly trend chart has proper history.
                # ================================================

                # Decide payment type: 60% NEW, 40% RENEWAL
                payment_type = 'RENEWAL' if random.random() < 0.4 else 'NEW'

                cursor.execute("""
                    INSERT INTO payments
                        (user_id, subscription_id, plan_name, amount,
                         payment_type, payment_status, payment_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (uid, sub_id, plan_name, plan_price,
                      payment_type, 'SUCCESS', sub_start_date))

                # For RENEWAL users — also insert the original NEW
                # payment 30-90 days earlier so history is realistic
                if payment_type == 'RENEWAL':
                    original_date = sub_start_date - timedelta(days=random.randint(30, 90))
                    cursor.execute("""
                        INSERT INTO payments
                            (user_id, subscription_id, plan_name, amount,
                             payment_type, payment_status, payment_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (uid, sub_id, plan_name, plan_price,
                          'NEW', 'SUCCESS', original_date))

                has_subscription = True
            else:
                print(f"   User {i} has no subscription plan.")

            # Activity Logic: 85% chance if subscribed
            if has_subscription and random.random() < 0.85:
                login_offset = random.randint(1, 20)
                login_time   = sub_start_date + timedelta(days=login_offset)
                session_mins = random.randint(15, 120)
                logout_time  = login_time + timedelta(minutes=session_mins)

                cursor.execute("""
                    INSERT INTO user_activity
                        (user_id, login_time, logout_time, session_minutes)
                    VALUES (%s, %s, %s, %s)
                """, (uid, login_time, logout_time, session_mins))

            # Batch commit every 10 users
            if i % 10 == 0:
                conn.commit()
                print(f"Saved Batch {i // 10} (Users 1-{i}) to disk...")

            plan_info = f"{plan_name} Rs.{plan_price}" if has_subscription else "None"
            print(f"USER {i:>3}: {email} | Plan: {plan_info} | Reg: {reg_time.strftime('%b %Y')}")

        except Exception as user_error:
            print(f"Error inserting User {i}: {user_error}")
            conn.rollback()
            continue

    # Final commit
    conn.commit()

    # --- 5. SEED FEEDBACK ---
    print("--------------------------------------------------")
    print("Seeding Feedback...")

    cursor.execute("SELECT user_id FROM users WHERE role = 'USER'")
    user_ids = [row[0] for row in cursor.fetchall()]

    if not user_ids:
        print("No users found. Skipping feedback seeding.")
    else:
        feedback_samples = [
            "Please add Inception",
            "Need more Horror movies",
            "Where is Stranger Things season 5?",
            "App is slow on iPhone",
            "Love the new interface!",
            "Can we get 4K on Mobile plan?",
            "Buffering issues on Premium",
            "Add more Bollywood content"
        ]
        for _ in range(20):
            cursor.execute(
                "INSERT INTO feedback (user_id, request_content) VALUES (%s, %s)",
                (random.choice(user_ids), random.choice(feedback_samples))
            )
        conn.commit()
        print("Feedback Seeded Successfully.")

    # --- 6. FINAL SUMMARY ---
    print("--------------------------------------------------")
    print("SUCCESS! 150 Users Seeded.")
    print("--------------------------------------------------")
    print("DATABASE SUMMARY:")

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'USER'")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'ACTIVE'")
    active_subs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'EXPIRED'")
    expired_subs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments")
    total_payments = cursor.fetchone()[0]

    print(f"   Total Users          : {total_users}")
    print(f"   Active Subscriptions : {active_subs}")
    print(f"   Expired Subscriptions: {expired_subs}")
    print(f"   Total Payment Records: {total_payments}")
    print("--------------------------------------------------")

    # Show monthly revenue breakdown
    cursor.execute("""
        SELECT TO_CHAR(payment_date, 'Mon YYYY')   as month,
               COUNT(*)                             as txns,
               SUM(amount)                          as revenue
        FROM payments
        WHERE payment_status = 'SUCCESS'
        GROUP BY TO_CHAR(payment_date, 'Mon YYYY'),
                 DATE_TRUNC('month', payment_date)
        ORDER BY DATE_TRUNC('month', payment_date) ASC
    """)
    monthly = cursor.fetchall()

    print("MONTHLY REVENUE BREAKDOWN (from payments table):")
    print("--------------------------------------------------")
    for month, txns, revenue in monthly:
        bar = "=" * min(int(float(revenue) // 5000), 25)
        print(f"   {month:>10} | {txns:>3} txns | Rs.{float(revenue):>10,.0f}  {bar}")

    print("--------------------------------------------------")
    print("These amounts now appear in your Admin Revenue Charts.")
    print("Real user purchases add on TOP of this correctly.")
    print("--------------------------------------------------")

    conn.close()

except Exception as e:
    print(f"CRITICAL Error during seeding: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)