import psycopg2
import hashlib
import sys

# --- CONFIGURATION ---
DB_HOST = "localhost"
DB_NAME = "sub_system"
DB_USER = "postgres"
DB_PASS = "shrey28"

class DB:
    def __init__(self):
        self.conn = None
        self.cursor = None
        try:
            self.conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
            self.conn.autocommit = True
            self.cursor = self.conn.cursor()
            self.create_tables()
            self.update_user_schema()
            print("✅ Database Connected Successfully")
        except Exception as e:
            print(f"\n❌ CRITICAL DATABASE ERROR: {e}\n")
            sys.exit(1)

    def create_tables(self):
        commands = [
            '''CREATE TABLE IF NOT EXISTS visitors (
                visitor_id SERIAL PRIMARY KEY,
                visit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                fullname VARCHAR(100),
                email VARCHAR(100) UNIQUE,
                password VARCHAR(255),
                mobile VARCHAR(15),
                age INTEGER,
                country VARCHAR(50),
                role VARCHAR(20) DEFAULT 'USER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gender VARCHAR(10),
                dob DATE,
                favorite_genre VARCHAR(50),
                profile_pic_url TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS subscriptions (
                subscription_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                service_type VARCHAR(50),
                plan_name VARCHAR(50),
                amount DECIMAL(10,2),
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                auto_renewal BOOLEAN DEFAULT FALSE
            )''',
            '''CREATE TABLE IF NOT EXISTS payments (
                payment_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                subscription_id INTEGER REFERENCES subscriptions(subscription_id),
                plan_name VARCHAR(50),
                amount DECIMAL(10,2),
                payment_type VARCHAR(20) DEFAULT 'NEW',
                payment_status VARCHAR(20) DEFAULT 'SUCCESS',
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            '''CREATE TABLE IF NOT EXISTS user_activity (
                activity_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                login_time TIMESTAMP,
                logout_time TIMESTAMP,
                session_minutes INTEGER DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS feedback (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                request_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',

            # ─────────────────────────────────────────────────────────────
            # NEW: Content table — stores Netflix movies & shows from Kaggle
            # ─────────────────────────────────────────────────────────────
            '''CREATE TABLE IF NOT EXISTS content (
                content_id   SERIAL PRIMARY KEY,
                show_id      VARCHAR(20),
                content_type VARCHAR(10),          -- 'Movie' or 'TV Show'
                title        VARCHAR(300),
                director     TEXT,
                cast_members TEXT,
                country      VARCHAR(200),
                date_added   VARCHAR(50),
                release_year INTEGER,
                rating       VARCHAR(20),          -- PG-13, TV-MA, etc.
                duration     VARCHAR(30),          -- '90 min' or '3 Seasons'
                genre        VARCHAR(200),         -- listed_in column from Kaggle
                description  TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',

            # ── Mutual Connection Groups ──────────────────────────
            # Each row = one group of users sharing a plan
            '''CREATE TABLE IF NOT EXISTS mutual_groups (
                group_id     SERIAL PRIMARY KEY,
                plan_name    VARCHAR(50),
                full_price   DECIMAL(10,2),
                split_price  DECIMAL(10,2),
                max_members  INTEGER DEFAULT 4,
                status       VARCHAR(20) DEFAULT 'FORMING',
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',

            # ── Per-user invite & membership record ───────────────
            # invite_status: PENDING → ACCEPTED / DECLINED
            # member_status: ACTIVE (after group forms) / LEFT
            '''CREATE TABLE IF NOT EXISTS mutual_invites (
                invite_id     SERIAL PRIMARY KEY,
                user_id       INTEGER REFERENCES users(user_id),
                group_id      INTEGER REFERENCES mutual_groups(group_id),
                plan_name     VARCHAR(50),
                split_price   DECIMAL(10,2),
                admin_message TEXT,
                invite_status VARCHAR(20) DEFAULT 'PENDING',
                member_status VARCHAR(20) DEFAULT 'NONE',
                sent_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at  TIMESTAMP
            )'''
        ]
        for cmd in commands:
            self.cursor.execute(cmd)

        # Create Admin
        try:
            admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
            self.cursor.execute("""
                INSERT INTO users (fullname, email, password, role)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING
            """, ("System Admin", "admin", admin_pass, "ADMIN"))
        except Exception as e:
            print(f"Admin Setup Note: {e}")

    def log_visitor(self):
        if self.cursor:
            self.cursor.execute("INSERT INTO visitors (visit_time) VALUES (CURRENT_TIMESTAMP)")

    def close(self):
        if self.cursor: self.cursor.close()
        if self.conn:   self.conn.close()

    def update_user_schema(self):
        """Updates existing tables to add missing columns safely."""
        new_columns = [
            ("gender",         "VARCHAR(10)"),
            ("dob",            "DATE"),
            ("favorite_genre", "VARCHAR(50)"),
            ("profile_pic_url","TEXT")
        ]

        try:
            self.cursor.execute("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS auto_renewal BOOLEAN DEFAULT FALSE")
            self.conn.commit()
        except Exception as e:
            print(f"ℹ️ Info: {e}")

        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(user_id),
                    subscription_id INTEGER REFERENCES subscriptions(subscription_id),
                    plan_name VARCHAR(50),
                    amount DECIMAL(10,2),
                    payment_type VARCHAR(20) DEFAULT 'NEW',
                    payment_status VARCHAR(20) DEFAULT 'SUCCESS',
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
        except Exception as e:
            print(f"ℹ️ Info: {e}")

        # ── NEW: Ensure content table exists even on older databases ──
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS content (
                    content_id   SERIAL PRIMARY KEY,
                    show_id      VARCHAR(20),
                    content_type VARCHAR(10),
                    title        VARCHAR(300),
                    director     TEXT,
                    cast_members TEXT,
                    country      VARCHAR(200),
                    date_added   VARCHAR(50),
                    release_year INTEGER,
                    rating       VARCHAR(20),
                    duration     VARCHAR(30),
                    genre        VARCHAR(200),
                    description  TEXT,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
            print("✅ Content table checked/created.")
        except Exception as e:
            print(f"ℹ️ Info: {e}")

        # ── NEW: Ensure mutual connection tables exist ──
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS mutual_groups (
                    group_id     SERIAL PRIMARY KEY,
                    plan_name    VARCHAR(50),
                    full_price   DECIMAL(10,2),
                    split_price  DECIMAL(10,2),
                    max_members  INTEGER DEFAULT 4,
                    status       VARCHAR(20) DEFAULT 'FORMING',
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS mutual_invites (
                    invite_id     SERIAL PRIMARY KEY,
                    user_id       INTEGER REFERENCES users(user_id),
                    group_id      INTEGER REFERENCES mutual_groups(group_id),
                    plan_name     VARCHAR(50),
                    split_price   DECIMAL(10,2),
                    admin_message TEXT,
                    invite_status VARCHAR(20) DEFAULT 'PENDING',
                    member_status VARCHAR(20) DEFAULT 'NONE',
                    sent_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    responded_at  TIMESTAMP
                )
            """)
            self.conn.commit()
            print("✅ Mutual connection tables checked/created.")
        except Exception as e:
            print(f"ℹ️ Info: {e}")

        print("🔄 Updating 'users' table schema...")
        for col_name, col_type in new_columns:
            try:
                self.cursor.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                self.conn.commit()
                print(f"✅ Column '{col_name}' checked/added.")
            except Exception as e:
                print(f"ℹ️ Info: {e}")


# ── Run this block when database.py is executed directly ──────
if __name__ == "__main__":
    print("=" * 50)
    print("   SUBSCRIPTION MANAGEMENT SYSTEM")
    print("   Database Setup")
    print("=" * 50)
    db = DB()
    print("=" * 50)
    print("✅ All tables created successfully!")
    print("✅ Admin account ready  →  ID: admin | Pass: admin123")
    print("=" * 50)
    print("▶️  Next step: python seed_netflix_realistic.py")
    print("=" * 50)
    db.close()