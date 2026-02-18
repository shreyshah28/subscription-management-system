import streamlit as st
import pandas as pd
import plotly.express as px
import qrcode
from io import BytesIO
from datetime import datetime

from backend import UserModule, SubscriptionManager, ActivityTracker, AdminAnalytics, ContentManager
from database import DB

# --- PAGE CONFIG ---
st.set_page_config(page_title="Netflix Subscription System", page_icon="🎬", layout="wide")

# --- INIT ---
@st.cache_resource
def init_db():
    return DB()

db = init_db()
user_sys = UserModule()
sub_sys = SubscriptionManager()
tracker = ActivityTracker()
admin_sys = AdminAnalytics()
content_mgr = ContentManager()

# --- CSS STYLING ---
st.markdown("""
<style>
    .plan-card {
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        color: white;
        font-weight: bold;
        margin-bottom: 10px;
        border: 2px solid #333;
        transition: 0.3s;
        background-color: #221f1f; /* Netflix Black */
    }
    .plan-card:hover { border: 2px solid #E50914; transform: scale(1.02); cursor: pointer; }
    .netflix-red { color: #E50914; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ================= STATE MANAGEMENT =================
is_user_logged_in = 'user_id' in st.session_state
is_admin_logged_in = 'admin_auth' in st.session_state

if 'admin_view' not in st.session_state:
    st.session_state['admin_view'] = 'Analytics'

# ================= 1. GATEWAY (LOGIN/REG) =================
if not is_user_logged_in and not is_admin_logged_in:
    st.sidebar.title("🚪 Gateway")
    role_choice = st.sidebar.radio("Select Module", ["👤 User Module", "🛠️ Admin Module"])

    if role_choice == "👤 User Module":
        st.title("👤 User Access Portal")
        tab1, tab2 = st.tabs(["Login", "New Registration"])
        
        with tab1:
            email = st.text_input("Email Address")
            password = st.text_input("Password", type="password")
            if st.button("Login", type="primary"):
                user = user_sys.login(email, password)
                if user:
                    # user tuple: (user_id, fullname, email, password, mobile, age, country, role, created_at)
                    st.session_state.update({
                        'user_id': user[0], 
                        'name': user[1], 
                        'email': user[2],     
                        'age': user[5],        
                        'act_id': tracker.log_in(user[0]),
                        'pending_purchase': None
                    })
                    st.success("Login Successful!")
                    st.rerun()
                else: 
                    st.error("Invalid Credentials")

        with tab2:
            st.subheader("Create New Account")
            c1, c2 = st.columns(2)
            with c1:
                reg_name = st.text_input("Full Name", placeholder="e.g. Shrey Shah")
                reg_pass = st.text_input("Create Password", type="password", help="Minimum 6 characters")
                reg_age = st.number_input("Age", min_value=0, max_value=120, value=18)
            with c2:
                reg_email = st.text_input("Email", placeholder="example@gmail.com")
                reg_mobile = st.text_input("Mobile No", placeholder="10-digit number")
                reg_country = st.selectbox("Country", ["India", "USA", "UK", "Canada", "Germany"])

            if st.button("Register Now", type="primary"):
                if not reg_email.endswith("@gmail.com"):
                    st.error("Invalid Email: Must be a @gmail.com account.")
                elif len(reg_mobile) != 10 or not reg_mobile.isdigit():
                    st.error("Invalid Mobile: Must be exactly 10 digits.")
                elif reg_age < 0:
                    st.error("Invalid Age: Age cannot be negative.")
                elif len(reg_pass) < 6:
                    st.error("Invalid Password: Must be at least 6 characters.")
                else:
                    res, msg = user_sys.register(reg_name, reg_email, reg_pass, reg_mobile, reg_age, reg_country)
                    if res:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
    elif role_choice == "🛠️ Admin Module":
        st.title("🛠️ Administrator Login")
        ad_id = st.text_input("Admin ID")
        ad_pass = st.text_input("Admin Password", type="password")
        if st.button("Access Dashboard"):
            if ad_id == "admin" and ad_pass == "admin123":
                st.session_state['admin_auth'] = True; st.rerun()
            else: st.error("Access Denied")

# ================= 2. USER DASHBOARD =================
elif is_user_logged_in:
    
    # --- AUTO-RECOVERY BLOCK ---
    if 'email' not in st.session_state or 'age' not in st.session_state:
        uid = st.session_state['user_id']
        try:
            db.cursor.execute("SELECT email, age, fullname FROM users WHERE user_id=%s", (uid,))
            result = db.cursor.fetchone()
            if result:
                st.session_state['email'] = result[0]
                st.session_state['age'] = result[1]
                st.session_state['name'] = result[2]
        except Exception as e:
            st.error(f"Error fetching user details: {e}")
    # ----------------------------------------------------------

    st.sidebar.title(f"👋 Hi, {st.session_state['name']}")
    
    # --- SIDEBAR CANCEL BUTTON ---
    active_plan = sub_sys.get_active_plan(st.session_state['user_id'])
    
    if active_plan:
        st.sidebar.warning("You have an active plan.")
        if st.sidebar.button("❌ Cancel Subscription", use_container_width=True):
            if sub_sys.cancel_subscription(st.session_state['user_id']):
                st.success("Subscription Cancelled Successfully!")
                st.rerun()
            else:
                st.error("Could not cancel. Please try again.")
    
    user_menu = st.sidebar.radio("Menu", ["🏠 Dashboard", "📺 Browse Content", "🎬 Netflix Plans", "💬 Feedback", "🧾 My Transactions", "⚙️ My Profile"])
    
    if st.sidebar.button("Logout"):
        tracker.log_out(st.session_state['act_id'])
        del st.session_state['user_id']
        st.rerun()

    # ── EXPIRY REMINDER ALERT (fires once per login session) ─────
    if 'expiry_alert_shown' not in st.session_state:
        st.session_state['expiry_alert_shown'] = True
        _plan_check = sub_sys.get_active_plan(st.session_state['user_id'])
        if _plan_check:
            _days_left = (_plan_check['end_date'] - datetime.now()).days
            if _days_left <= 3:
                st.toast(f"🚨 URGENT! Your plan expires in {_days_left} day(s)! Renew NOW.", icon="🚨")
            elif _days_left <= 7:
                st.toast(f"⚠️ Your plan expires in {_days_left} days on {_plan_check['end_date'].strftime('%d %b %Y')}.", icon="⚠️")
        else:
            _expired = sub_sys.get_expired_plan(st.session_state['user_id'])
            if _expired:
                st.toast("🔴 Your subscription has expired! Go to Netflix Plans to renew.", icon="🔴")
    if user_menu == "🏠 Dashboard":
        dash = user_sys.get_user_dashboard(st.session_state['user_id'])

        st.title(f"👋 Welcome Back, {st.session_state['name']}!")
        st.caption(f"🕐 Last Login: {dash['last_login']}")
        st.divider()

        # --- ROW 1: 4 METRIC CARDS ---
        st.subheader("📊 Your Overview")
        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            label="📦 Current Plan",
            value=dash['plan_name'] if dash['plan_name'] else "No Plan",
            delta="ACTIVE ✅" if dash['sub_status'] == 'ACTIVE' else dash['sub_status']
        )
        m2.metric(
            label="📅 Days Remaining",
            value=f"{dash['days_left']} days",
            delta=f"Expires {dash['end_date_str']}"
        )
        m3.metric(
            label="💰 Total Spent",
            value=f"₹{dash['total_spend']:,.0f}",
            delta=f"{dash['total_subs']} subscription(s)"
        )
        m4.metric(
            label="⏱️ Total Watch Time",
            value=f"{dash['total_watch']} mins",
            delta=f"{round(dash['total_watch']/60, 1)} hours"
        )

        st.divider()

        # --- ROW 2: SUBSCRIPTION PROGRESS BAR ---
        if dash['plan_name']:
            st.subheader("📈 Subscription Usage")

            progress_val = min(1.0, dash['days_used'] / dash['total_days'])
            progress_pct = round(progress_val * 100)

            # Color warning based on days left
            if dash['days_left'] <= 3:
                st.error(f"🚨 **Critical!** Your plan expires in only **{dash['days_left']} days!** Please renew soon.")
            elif dash['days_left'] <= 7:
                st.warning(f"⚠️ Your plan expires in **{dash['days_left']} days** on {dash['end_date_str']}.")
            else:
                st.success(f"✅ Your plan is active. **{dash['days_left']} days remaining** until {dash['end_date_str']}.")

            st.progress(progress_val, text=f"{progress_pct}% of subscription used ({dash['days_used']} of {dash['total_days']} days)")

            st.divider()

            # --- ROW 3: PLAN DETAILS + AUTO RENEWAL STATUS ---
            st.subheader("🎬 Plan Details")
            plan_features = {
                "Mobile":   {"res": "480p",    "screens": "1 Phone + 1 Tablet", "color": "#1a1a2e"},
                "Standard": {"res": "1080p",   "screens": "2 Screens, HD",      "color": "#16213e"},
                "Premium":  {"res": "4K+HDR",  "screens": "4 Screens, Ultra HD","color": "#0f3460"},
            }
            feat = plan_features.get(dash['plan_name'], {"res": "—", "screens": "—", "color": "#221f1f"})

            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown(f"""
                <div style="padding:25px; border-radius:12px; background:{feat['color']}; color:white; border: 2px solid #E50914;">
                    <h2 style="color:#E50914;">Netflix {dash['plan_name']}</h2>
                    <h1>₹{dash['plan_amount']:,.0f}<span style="font-size:16px;">/month</span></h1>
                    <hr style="border-color:#555;">
                    <p>🖥️ Screens: {feat['screens']}</p>
                    <p>📺 Resolution: {feat['res']}</p>
                    <p>📅 Valid Until: {dash['end_date_str']}</p>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                st.markdown("#### 🔄 Auto-Renewal")
                if dash['auto_renewal']:
                    st.success("✅ Auto-Renewal is **ON** — Your plan will renew automatically.")
                else:
                    st.warning("❌ Auto-Renewal is **OFF** — Go to Netflix Plans to enable it.")

                st.markdown("#### 📊 Quick Stats")
                st.info(f"""
                - 🎬 Total Subscriptions Ever: **{dash['total_subs']}**
                - 💰 Lifetime Spend: **₹{dash['total_spend']:,.0f}**
                - ⏱️ Total Watch Time: **{dash['total_watch']} mins ({round(dash['total_watch']/60,1)} hrs)**
                """)
        else:
            # --- NO PLAN STATE ---
            st.warning("⚠️ You don't have an active subscription.")
            st.info("Go to **🎬 Netflix Plans** from the menu to choose a plan and start watching!")

            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Total Spent", f"₹{dash['total_spend']:,.0f}")
            c2.metric("⏱️ Watch Time", f"{dash['total_watch']} mins")
            c3.metric("📦 Past Subscriptions", dash['total_subs'])

        # --- PERSONAL ANALYTICS (merged from separate page) ---
        st.divider()
        st.subheader("📊 Your Personal Analytics")
        spend, minutes = user_sys.get_user_analytics(st.session_state['user_id'])
        pa1, pa2, pa3 = st.columns(3)
        pa1.metric("💰 Total Lifetime Spend", f"₹{spend:,.0f}")
        pa2.metric("⏱️ Total Watch Time", f"{int(minutes)} mins")
        pa3.metric("🕐 Watch Time in Hours", f"{round(int(minutes)/60, 1)} hrs")

    # --- MY TRANSACTIONS (merged Billing History + Payment History) ---
    elif user_menu == "🧾 My Transactions":
        st.title("🧾 My Transactions")
        st.info("Complete record of your subscriptions and all payment transactions.")

        tab_subs, tab_payments = st.tabs(["📦 Subscription History", "💳 Payment History"])

        # ── TAB 1: Subscription History (was Billing History) ──
        with tab_subs:
            st.subheader("📜 All Subscriptions")
            df_inv = sub_sys.get_user_invoices(st.session_state['user_id'])
            if not df_inv.empty:
                st.dataframe(df_inv, use_container_width=True)
            else:
                st.info("No subscription records found. Buy a plan to get started!")

        # ── TAB 2: Payment History (was Payment History page) ──
        with tab_payments:
            st.subheader("💳 Payment Records")
            df_payments = sub_sys.get_payment_history(st.session_state['user_id'])

            if not df_payments.empty:
                total_paid = df_payments[df_payments['payment_status'] == 'SUCCESS']['amount'].sum()
                total_txns = len(df_payments)
                renewals = len(df_payments[df_payments['payment_type'] == 'RENEWAL'])

                m1, m2, m3 = st.columns(3)
                m1.metric("💰 Total Spent", f"₹{total_paid:,.0f}")
                m2.metric("🔢 Total Transactions", total_txns)
                m3.metric("🔄 Renewals", renewals)

                st.divider()
                st.subheader("📋 Transaction Details")

                for idx, row in df_payments.iterrows():
                    with st.expander(f"💳 {row['plan_name']} - ₹{row['amount']} | {row['payment_date'].strftime('%d %b %Y')}"):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"""
                            **Transaction ID:** {row['payment_id']}  
                            **Plan:** {row['plan_name']}  
                            **Amount:** ₹{row['amount']}  
                            **Type:** {row['payment_type']}  
                            **Status:** {row['payment_status']}  
                            **Date:** {row['payment_date'].strftime('%d %B %Y, %I:%M %p')}
                            """)
                        with col2:
                            if st.button(f"📥 Download Receipt", key=f"receipt_{row['payment_id']}", use_container_width=True):
                                receipt_text = sub_sys.regenerate_receipt(row['payment_id'])
                                if receipt_text:
                                    st.download_button(
                                        label="💾 Save Receipt",
                                        data=receipt_text,
                                        file_name=f"Netflix_Receipt_{row['payment_id']}.pdf",
                                        mime="application/pdf",
                                        key=f"download_{row['payment_id']}"
                                    )
                                    st.success("✅ Receipt ready!")
                                else:
                                    st.error("Failed to generate receipt.")
            else:
                st.info("No payment records found. Buy a plan to get started!")

    # --- FEEDBACK SECTION ---
    elif user_menu == "💬 Feedback":
        st.title("💬 Request a Movie or Show")
        st.info("Tell us what you want to watch next!")
        feedback_text = st.text_area("Your Request (e.g. 'Add Inception to library')")
        if st.button("Submit Request"):
            if feedback_text:
                if user_sys.submit_feedback(st.session_state['user_id'], feedback_text):
                    st.success("Thank you! Your request has been sent to the content team.")
                else:
                    st.error("Could not submit feedback.")
            else:
                st.warning("Please type something before submitting.")

    # --- PROFILE PAGE ---
    elif user_menu == "⚙️ My Profile":
        st.title("⚙️ My Profile")
        st.info("View and edit your personal details below.")

        profile = user_sys.get_profile(st.session_state['user_id'])

        if profile:
            st.subheader("👤 Personal Information")

            c1, c2 = st.columns(2)
            with c1:
                new_name = st.text_input("Full Name", value=profile['fullname'])
                new_mobile = st.text_input("Mobile Number", value=profile['mobile'],
                                           placeholder="10-digit number")
                new_country = st.selectbox("Country",
                    ["India", "USA", "UK", "Canada", "Germany", "France", "Australia", "Japan", "Brazil"],
                    index=["India", "USA", "UK", "Canada", "Germany", "France", "Australia", "Japan", "Brazil"].index(profile['country'])
                    if profile['country'] in ["India", "USA", "UK", "Canada", "Germany", "France", "Australia", "Japan", "Brazil"] else 0
                )

            with c2:
                new_gender = st.selectbox("Gender",
                    ["", "Male", "Female", "Other"],
                    index=["", "Male", "Female", "Other"].index(profile['gender'])
                    if profile['gender'] in ["", "Male", "Female", "Other"] else 0
                )
                genres = ["", "Action", "Comedy", "Drama", "Horror", "Romance",
                          "Sci-Fi", "Thriller", "Documentary", "Animation", "Fantasy"]
                new_genre = st.selectbox("Favorite Genre",
                    genres,
                    index=genres.index(profile['favorite_genre'])
                    if profile['favorite_genre'] in genres else 0
                )
                default_dob = profile['dob'] if profile['dob'] else datetime(2000, 1, 1).date()
                new_dob = st.date_input("Date of Birth", value=default_dob,
                                        min_value=datetime(1920, 1, 1).date(),
                                        max_value=datetime.now().date())

            st.divider()

            # Read-only fields
            st.subheader("🔒 Account Details (Read Only)")
            r1, r2 = st.columns(2)
            r1.text_input("Email Address", value=profile['email'], disabled=True)
            r2.text_input("Age", value=str(profile['age']), disabled=True)

            st.divider()

            if st.button("💾 Save Profile", type="primary", use_container_width=True):
                success, msg = user_sys.update_profile(
                    st.session_state['user_id'],
                    new_name, new_mobile, new_country,
                    new_gender, new_dob, new_genre
                )
                if success:
                    st.success(f"✅ {msg}")
                    # Update session name immediately
                    st.session_state['name'] = new_name
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
        else:
            st.error("Could not load profile. Please try again.")
    # ═══════════════════════════════════════════════════════
    # BROWSE CONTENT — powered by Kaggle Netflix Dataset
    # ═══════════════════════════════════════════════════════
    elif user_menu == "📺 Browse Content":
        st.title("📺 Netflix Content Library")

        # ── Check if content table has data ─────────────────
        if not content_mgr.is_content_loaded():
            st.warning("⚠️ The content library is empty!")
            st.info("""
            **To load the Netflix dataset, follow these steps:**

            **Step 1** — Download the free dataset from Kaggle:
            👉 https://www.kaggle.com/datasets/shivamb/netflix-shows

            **Step 2** — Save `netflix_titles.csv` in your project folder.

            **Step 3** — Open your terminal and run:
            ```
            python load_kaggle_content.py
            ```

            **Step 4** — Come back here and refresh the page!
            """)
            st.stop()

        # ── Check if user has active subscription ───────────
        active_plan = sub_sys.get_active_plan(st.session_state['user_id'])
        if not active_plan:
            st.error("🔒 **Content Library is locked.** You need an active subscription to browse.")
            st.info("Go to **🎬 Netflix Plans** from the sidebar to subscribe.")
            st.stop()

        # ── Stats bar ────────────────────────────────────────
        total, movies, shows = content_mgr.get_content_stats()
        c1, c2, c3 = st.columns(3)
        c1.metric("🎬 Total Titles", f"{total:,}")
        c2.metric("🎥 Movies", f"{movies:,}")
        c3.metric("📺 TV Shows", f"{shows:,}")

        st.divider()

        # ── TABS: Browse | Recommendations ──────────────────
        tab_browse, tab_recommend = st.tabs(["🔍 Browse & Search", "⭐ Recommended For You"])

        # ──────────────────────────────────────────────────────
        # TAB 1 — BROWSE & SEARCH
        # ──────────────────────────────────────────────────────
        with tab_browse:
            col_f1, col_f2, col_f3 = st.columns([2, 2, 3])

            with col_f1:
                type_filter = st.selectbox("🎞️ Type", ["All", "Movie", "TV Show"])

            with col_f2:
                genres = ["All"] + content_mgr.get_all_genres()
                genre_filter = st.selectbox("🎭 Genre", genres)

            with col_f3:
                search_q = st.text_input("🔍 Search title, cast, or director", placeholder="e.g. Inception, Tom Hanks...")

            # Pagination state
            if 'content_page' not in st.session_state:
                st.session_state['content_page'] = 1

            # Reset page on filter change
            filter_key = f"{type_filter}|{genre_filter}|{search_q}"
            if st.session_state.get('last_filter') != filter_key:
                st.session_state['content_page'] = 1
                st.session_state['last_filter'] = filter_key

            PAGE_SIZE = 20
            df_content, total_count = content_mgr.browse_content(
                content_type=type_filter,
                genre_filter=genre_filter,
                search_query=search_q,
                page=st.session_state['content_page'],
                page_size=PAGE_SIZE
            )

            total_pages = max(1, -(-total_count // PAGE_SIZE))  # ceil division
            st.caption(f"Showing **{len(df_content)}** of **{total_count:,}** results  |  Page {st.session_state['content_page']} of {total_pages}")

            if df_content.empty:
                st.info("No content found matching your filters. Try a different search.")
            else:
                # Display content as cards (3 per row)
                for i in range(0, len(df_content), 3):
                    cols = st.columns(3)
                    for j, col in enumerate(cols):
                        if i + j >= len(df_content):
                            break
                        row = df_content.iloc[i + j]
                        with col:
                            type_badge = "🎬" if row['content_type'] == 'Movie' else "📺"
                            st.markdown(f"""
                            <div style="padding:15px; border-radius:10px; background:#1a1a2e;
                                        border:1px solid #333; margin-bottom:10px; min-height:220px;">
                                <p style="color:#E50914; font-size:11px; margin:0;">
                                    {type_badge} {row['content_type']}
                                    &nbsp;|&nbsp; ⭐ {row['rating'] or 'NR'}
                                    &nbsp;|&nbsp; 📅 {int(row['release_year']) if row['release_year'] else 'N/A'}
                                </p>
                                <h4 style="color:white; margin:6px 0 4px 0; font-size:15px;">
                                    {row['title']}
                                </h4>
                                <p style="color:#aaa; font-size:11px; margin:0 0 6px 0;">
                                    ⏱️ {row['duration'] or 'N/A'}
                                </p>
                                <p style="color:#ccc; font-size:12px; line-height:1.4;">
                                    {str(row['description'])[:130]}{'...' if len(str(row['description'])) > 130 else ''}
                                </p>
                                <p style="color:#E50914; font-size:10px; margin-top:8px;">
                                    🎭 {str(row['genre'])[:60]}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Expandable details
                            with st.expander("More Info"):
                                if row['director']:
                                    st.markdown(f"**🎬 Director:** {row['director']}")
                                if row['cast_members']:
                                    st.markdown(f"**🌟 Cast:** {str(row['cast_members'])[:200]}")
                                if row['country']:
                                    st.markdown(f"**🌍 Country:** {row['country']}")
                                st.markdown(f"**📖 Description:** {row['description']}")

            st.divider()

            # Pagination controls
            p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
            with p_col1:
                if st.button("⬅️ Previous", disabled=(st.session_state['content_page'] <= 1), use_container_width=True):
                    st.session_state['content_page'] -= 1
                    st.rerun()
            with p_col2:
                st.markdown(f"<p style='text-align:center; color:#aaa;'>Page {st.session_state['content_page']} / {total_pages}</p>", unsafe_allow_html=True)
            with p_col3:
                if st.button("Next ➡️", disabled=(st.session_state['content_page'] >= total_pages), use_container_width=True):
                    st.session_state['content_page'] += 1
                    st.rerun()

        # ──────────────────────────────────────────────────────
        # TAB 2 — PERSONALISED RECOMMENDATIONS
        # ──────────────────────────────────────────────────────
        with tab_recommend:
            # Fetch user's favorite genre from profile
            profile = user_sys.get_profile(st.session_state['user_id'])
            fav_genre = profile.get('favorite_genre', '') if profile else ''

            if fav_genre:
                st.success(f"🎯 Showing recommendations based on your favourite genre: **{fav_genre}**")
            else:
                st.info("💡 You haven't set a favourite genre yet. Go to **⚙️ My Profile** to set one! Showing trending titles for now.")

            df_recs = content_mgr.get_recommendations(fav_genre, limit=12)

            if df_recs.empty:
                st.warning("No recommendations found. Try updating your favourite genre in your profile.")
            else:
                for i in range(0, len(df_recs), 3):
                    cols = st.columns(3)
                    for j, col in enumerate(cols):
                        if i + j >= len(df_recs):
                            break
                        row = df_recs.iloc[i + j]
                        with col:
                            type_badge = "🎬" if row['content_type'] == 'Movie' else "📺"
                            st.markdown(f"""
                            <div style="padding:15px; border-radius:10px; background:#0f3460;
                                        border:2px solid #E50914; margin-bottom:10px; min-height:200px;">
                                <p style="color:#E50914; font-size:11px; margin:0;">
                                    {type_badge} {row['content_type']}
                                    &nbsp;|&nbsp; ⭐ {row['rating'] or 'NR'}
                                    &nbsp;|&nbsp; 📅 {int(row['release_year']) if row['release_year'] else 'N/A'}
                                </p>
                                <h4 style="color:white; margin:6px 0 4px 0; font-size:15px;">
                                    {row['title']}
                                </h4>
                                <p style="color:#aaa; font-size:11px; margin-bottom:6px;">
                                    ⏱️ {row['duration'] or 'N/A'}
                                </p>
                                <p style="color:#ddd; font-size:12px; line-height:1.4;">
                                    {str(row['description'])[:130]}{'...' if len(str(row['description'])) > 130 else ''}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

    elif user_menu == "🎬 Netflix Plans":
        
        # --- CHECK FOR ACTIVE PLAN ---
        # Note: We refetch active_plan here because it might have changed via Cancel
        active_plan = sub_sys.get_active_plan(st.session_state['user_id'])
        
        # --- CASE A: USER HAS AN ACTIVE PLAN ---
        if active_plan:
            st.title("🟢 Your Current Subscription")
            st.info("You are enjoying uninterrupted streaming.")
            
            plan_features = {
                "Mobile": "480p, 1 Phone + 1 Tablet",
                "Standard": "1080p, 2 Screens, HD",
                "Premium": "4K+HDR, 4 Screens, Ultra HD"
            }
            
            p_name = active_plan['plan_name']
            p_price = active_plan['amount']
            start_date = active_plan['start_date'].strftime("%Y-%m-%d")
            end_date = active_plan['end_date'].strftime("%Y-%m-%d")
            resolution = "Unknown"
            full_desc = ""
            
            if p_name in plan_features:
                full_desc = plan_features[p_name]
                if "480p" in full_desc: resolution = "480p"
                elif "1080p" in full_desc: resolution = "1080p"
                elif "4K" in full_desc: resolution = "4K+HDR"

            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f"""
                <div style="padding: 20px; border-radius: 10px; background-color: #E50914; color: white;">
                    <h2>{p_name} Plan</h2>
                    <h1>₹{p_price}</h1>
                    <p>Status: {active_plan['status']}</p>
                    <p>Resolution: {resolution}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.metric("Valid Until", end_date)
                st.metric("Started On", start_date)
                st.caption(f"{full_desc}")
            
            # --- AUTO-RENEWAL TOGGLE ---
            st.divider()
            st.subheader("🔄 Auto-Renewal Settings")
            current_auto = active_plan.get('auto_renewal', False)
            auto_label = "✅ Auto-Renewal is ON" if current_auto else "❌ Auto-Renewal is OFF"
            st.info(auto_label)
            st.caption("When enabled, your plan will automatically renew 30 days after expiry.")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if not current_auto:
                    if st.button("🟢 Enable Auto-Renewal", use_container_width=True):
                        if sub_sys.toggle_auto_renewal(st.session_state['user_id'], True):
                            st.success("Auto-Renewal Enabled!")
                            st.rerun()
            with col_b:
                if current_auto:
                    if st.button("🔴 Disable Auto-Renewal", use_container_width=True):
                        if sub_sys.toggle_auto_renewal(st.session_state['user_id'], False):
                            st.warning("Auto-Renewal Disabled.")
                            st.rerun()

        # --- CASE B: USER HAS EXPIRED/CANCELLED PLAN (SHOW RENEW) ---
        else:
            expired_plan = sub_sys.get_expired_plan(st.session_state['user_id'])
            
            if expired_plan and not st.session_state.get('pending_purchase'):
                st.title("🔴 Your Subscription Has Expired")
                st.warning(f"Your **{expired_plan['plan_name']}** plan expired on {expired_plan['end_date'].strftime('%Y-%m-%d')}.")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.markdown(f"""
                    <div style="padding: 20px; border-radius: 10px; background-color: #333; color: white;">
                        <h3>Last Plan: {expired_plan['plan_name']}</h3>
                        <h2>₹{expired_plan['amount']}/month</h2>
                        <p>Status: <span style="color: #E50914;">EXPIRED</span></p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.subheader("🔄 Quick Renew")
                    st.caption("Renew the same plan with one click")
                    if st.button(f"🔄 Renew {expired_plan['plan_name']} Plan for ₹{expired_plan['amount']}", type="primary", use_container_width=True):
                        success, result, txt_receipt = sub_sys.renew_subscription(st.session_state['user_id'])
                        if success:
                            st.balloons()
                            st.success("🎉 Subscription Renewed Successfully!")
                            st.download_button(
                                "📥 Download Receipt (PDF)",
                                data=result,
                                file_name=f"Netflix_Renewal_{expired_plan['plan_name']}.pdf",
                                mime="application/pdf"
                            )
                            st.rerun()
                        else:
                            st.error(result)
                
                st.divider()
                st.subheader("Or choose a different plan:")

            # --- STEP 2: CONFIRMATION SCREEN (If a buy button was clicked) ---
            if st.session_state.get('pending_purchase'):
                purchase = st.session_state['pending_purchase']
                st.title("✅ Confirm Your Subscription")
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("👤 User Details")
                    st.info(f"""
                        **Name:** {st.session_state['name']}
                        **Email:** {st.session_state['email']}
                        **Age:** {st.session_state['age']}
                    """)
                
                with col2:
                    st.subheader("🎬 Plan Details")
                    st.success(f"""
                        **Service:** Netflix
                        **Plan:** {purchase['name']}
                        **Resolution:** {purchase['res']}
                        **Price:** ₹{purchase['price']}
                    """)
                
                st.divider()
                st.warning("Please verify your details before confirming.")
                
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state['pending_purchase'] = None
                        st.rerun()
                
                with col_b:
                    if st.button("✅ Confirm Payment", type="primary", use_container_width=True):
                        # Process Transaction
                        txt, pdf_bytes = sub_sys.buy_plan(st.session_state['user_id'], purchase['name'], purchase['price'], "Netflix")
                        
                        # Generate QR Code
                        qr_data = f"PAID|{purchase['name']}|{purchase['price']}|{st.session_state['email']}"
                        qr = qrcode.make(qr_data)
                        img_buffer = BytesIO()
                        qr.save(img_buffer, format="PNG")
                        
                        st.balloons()
                        st.success("Payment Successful!")
                        st.image(img_buffer, caption="Scan to verify Subscription", width=200)

                        # PDF receipt download
                        st.download_button(
                            "📥 Download Receipt (PDF)",
                            data=txt,
                            file_name=f"Netflix_Receipt_{purchase['name']}.pdf",
                            mime="application/pdf"
                        )
                        
                        # Clear pending state
                        st.session_state['pending_purchase'] = None
                        st.rerun()

            # --- STEP 1: DISPLAY PLANS ---
            else:
                st.title("🔴 Choose Your Netflix Plan")
                st.info("No active subscription found. Please select a plan to start watching.")
                
                plans = [
                    {"name": "Mobile", "price": 149, "res": "480p", "features": "1 Phone, 1 Tablet, Download"},
                    {"name": "Standard", "price": 499, "res": "1080p", "features": "2 Screens, HD, Download"},
                    {"name": "Premium", "price": 649, "res": "4K+HDR", "features": "4 Screens, Ultra HD, Spatial Audio"}
                ]

                p1, p2, p3 = st.columns(3)
                cols = [p1, p2, p3]

                for i, plan in enumerate(plans):
                    with cols[i]:
                        st.markdown(f"""
                        <div class="plan-card">
                            <h1>{plan['name']}</h1>
                            <h2 style="margin-top: -20px;">₹{plan['price']}</h2>
                            <hr style="border-color: #555;">
                            <p>{plan['features']}</p>
                            <p class="netflix-red">{plan['res']} Resolution</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"Buy {plan['name']}", key=f"buy_{plan['name']}", use_container_width=True):
                            st.session_state['pending_purchase'] = plan
                            st.rerun()

# ================= 3. ADMIN DASHBOARD =================
elif is_admin_logged_in:
    with st.sidebar:
        st.title("🛠️ Admin Panel")
        if st.button("📊 Analytics Dashboard", use_container_width=True):
            st.session_state['admin_view'] = 'Analytics'
        if st.button("📬 User Feedback", use_container_width=True):
            st.session_state['admin_view'] = 'Feedback'
        if st.button("👥 User Management", use_container_width=True):
            st.session_state['admin_view'] = 'Manage'
        if st.button("💳 Payment History", use_container_width=True):
            st.session_state['admin_view'] = 'Payments'
        if st.button("🚨 At-Risk Users", use_container_width=True):
            st.session_state['admin_view'] = 'AtRisk'
        if st.button("📈 Revenue Forecast", use_container_width=True):
            st.session_state['admin_view'] = 'Forecast'
        if st.button("🔍 Global Search", use_container_width=True):
            st.session_state['admin_view'] = 'GlobalSearch'
        if st.button("📺 Content Library", use_container_width=True):
            st.session_state['admin_view'] = 'ContentLib'
        st.divider()
        if st.button("Logout Admin"):
            del st.session_state['admin_auth']; st.rerun()

    if st.session_state['admin_view'] == 'Analytics':
        st.title("🚀 Business Intelligence Dashboard")

        # ── DOWNLOAD CSV ──────────────────────────────────────
        df_subs = admin_sys.get_all_data("subscriptions")
        if not df_subs.empty:
            csv = df_subs.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Revenue Report (CSV)",
                data=csv,
                file_name='revenue_report.csv',
                mime='text/csv'
            )
        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 1 — GENERAL OVERVIEW (Metric Cards)
        # ════════════════════════════════════════════════════════
        curr_rev, prev_rev, growth, last_year_rev, count, lifetime_rev = admin_sys.get_monthly_comparison()
        total_users = admin_sys.get_total_user_count()
        arpu = round(lifetime_rev / total_users, 2) if total_users > 0 else 0

        st.subheader("📊 Section 1 — General Overview")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Current Month Revenue",  f"₹{curr_rev:,.0f}",  f"{growth}% vs Last Month")
        m2.metric("📅 Last Month Revenue",      f"₹{prev_rev:,.0f}")
        m3.metric("🛒 This Month Sales Count",  count)
        m4.metric("👤 ARPU (Avg Rev/User)",     f"₹{arpu}")

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 2 — REVENUE CHARTS (3 columns)
        # ════════════════════════════════════════════════════════
        st.subheader("📈 Section 2 — Revenue Charts")
        g1, g2, g3 = st.columns(3)

        df_subs_chart = admin_sys.get_all_data("subscriptions")

        with g1:
            st.markdown("📈 **Platform Market Share (Revenue)**")
            if not df_subs_chart.empty:
                fig_pie = px.pie(
                    df_subs_chart, names='service_type', values='Revenue',
                    hole=0.5,
                    color_discrete_map={"Netflix": "#E50914", "Amazon Prime": "#00A8E1", "Disney+ Hotstar": "#001339"}
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        with g2:
            st.markdown("🌍 **Revenue by Country**")
            try:
                df_u   = admin_sys.get_all_data("users")
                df_geo = df_u.merge(df_subs_chart, on="user_id")
                df_map = df_geo.groupby("country")["Revenue"].sum().reset_index()
                fig_bar = px.bar(df_map, x='country', y='Revenue', color='Revenue', template="plotly_dark")
                st.plotly_chart(fig_bar, use_container_width=True)
            except:
                st.info("Geographic data unavailable.")

        with g3:
            st.markdown("💎 **Plan Popularity (Sales Count)**")
            df_plan_pop = admin_sys.get_plan_popularity()
            if not df_plan_pop.empty:
                fig_plan = px.bar(
                    df_plan_pop, x='plan_name', y='total_sales',
                    color='total_sales',
                    title="Best Selling Plans",
                    labels={'plan_name': 'Plan', 'total_sales': 'Count'},
                    text='total_sales',
                    color_continuous_scale='Reds'
                )
                fig_plan.update_traces(texttemplate='%{text}', textposition='outside')
                st.plotly_chart(fig_plan, use_container_width=True)

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 3 — USER DEMOGRAPHICS & REVENUE TREND
        # ════════════════════════════════════════════════════════
        st.subheader("👥 Section 3 — User Demographics & Trends")
        g4, g5 = st.columns(2)

        with g4:
            st.markdown("👨‍👩 **User Age Distribution**")
            df_ages = admin_sys.get_age_distribution()
            if not df_ages.empty:
                fig_age = px.histogram(
                    df_ages, x="age", nbins=5,
                    title="User Age Groups",
                    color_discrete_sequence=px.colors.sequential.RdBu
                )
                st.plotly_chart(fig_age, use_container_width=True)
            else:
                st.info("No age data available.")

        with g5:
            st.markdown("📉 **Revenue Trend (Last 6 Months)**")
            df_trend = admin_sys.get_monthly_revenue_trend()
            if not df_trend.empty:
                fig_trend = px.line(
                    df_trend, x='Month', y='Revenue',
                    markers=True, line_shape="spline",
                    title="Monthly Revenue Trend"
                )
                fig_trend.update_traces(line_color='#E50914')
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("No trend data available.")

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 4 — RETENTION & CHURN
        # ════════════════════════════════════════════════════════
        st.subheader("📉 Section 4 — Retention & Churn Metrics")
        total, cancelled, churn_rate = admin_sys.get_churn_stats()
        churn_color = "inverse" if churn_rate > 10 else "normal"

        c1, c2, c3 = st.columns(3)
        c1.metric("📦 Total Subscriptions", total)
        c2.metric("❌ Total Cancelled",     cancelled)
        c3.metric("📊 Churn Rate",          f"{churn_rate}%",
                  delta=f"{churn_rate}%", delta_color=churn_color)

        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown("🍩 **Active vs Cancelled Users**")
            df_status = admin_sys.get_active_vs_cancelled()
            if not df_status.empty:
                fig_ret = px.pie(
                    df_status, names='status', values='count',
                    hole=0.4,
                    color='status',
                    color_discrete_map={"ACTIVE": "#28a745", "CANCELLED": "#E50914"},
                    title="Subscription Status Split"
                )
                st.plotly_chart(fig_ret, use_container_width=True)

        with ch2:
            st.markdown("🥧 **Plan Revenue Share**")
            df_rev = admin_sys.get_plan_revenue_share()
            if not df_rev.empty:
                fig_rev = px.pie(
                    df_rev, names='plan_name', values='total_revenue',
                    hole=0.5,
                    title="Revenue Share by Plan",
                    color_discrete_sequence=px.colors.sequential.Aggrnyl
                )
                st.plotly_chart(fig_rev, use_container_width=True)

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 5 — USER ENGAGEMENT  (merged from Session Analytics)
        # ════════════════════════════════════════════════════════
        st.subheader("⏱️ Section 5 — User Engagement & Activity")

        avg_mins = admin_sys.get_avg_session_duration()
        avg_mins_rounded = round(avg_mins, 2) if avg_mins else 0

        ea1, ea2 = st.columns([1, 2])
        with ea1:
            st.metric("⏱️ Average Session Duration", f"{avg_mins_rounded} mins")
            st.caption("Average time a user spends per login session.")

        with ea2:
            st.markdown("📊 **Peak Login Hours**")
            df_hours = admin_sys.get_peak_hours()
            if not df_hours.empty:
                def format_hour_ampm(h):
                    if h == 0:   return "12 AM"
                    elif h < 12: return f"{h} AM"
                    elif h == 12: return "12 PM"
                    else:        return f"{h - 12} PM"
                df_hours['time_slot'] = df_hours['login_hour'].apply(format_hour_ampm)
                fig_peak = px.bar(
                    df_hours, x='time_slot', y='count',
                    title="Busiest Login Hours",
                    labels={'count': 'Logins', 'time_slot': 'Time'},
                    color='count', color_continuous_scale='Reds'
                )
                st.plotly_chart(fig_peak, use_container_width=True)
            else:
                st.info("No activity data yet.")

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 6 — CUSTOMER LIFETIME VALUE  (merged from AdvFin)
        # ════════════════════════════════════════════════════════
        st.subheader("🐋 Section 6 — Customer Lifetime Value (CLV)")
        st.caption("Top 10 most valuable users ranked by spend per active day.")

        df_clv = admin_sys.get_customer_lifetime_value()
        if not df_clv.empty:
            df_clv_sorted = df_clv.sort_values(by='clv', ascending=False).head(10)
            clv1, clv2 = st.columns(2)

            with clv1:
                df_display = df_clv_sorted[['fullname', 'total_spend', 'days_active', 'clv']].rename(columns={
                    'fullname':    'User Name',
                    'total_spend': 'Total Spend (₹)',
                    'days_active': 'Days Active',
                    'clv':         'CLV (₹/Day)'
                })
                st.dataframe(df_display, use_container_width=True)

            with clv2:
                fig_clv = px.bar(
                    df_clv_sorted, x='fullname', y='clv',
                    title="Top 10 Users by CLV",
                    labels={'fullname': 'User', 'clv': 'CLV (₹/Day)'},
                    color='clv', color_continuous_scale='Reds',
                    text='clv'
                )
                fig_clv.update_traces(texttemplate='₹%{text:.1f}', textposition='outside')
                fig_clv.update_layout(xaxis_tickangle=-30)
                st.plotly_chart(fig_clv, use_container_width=True)
        else:
            st.info("No CLV data available yet.")

    elif st.session_state['admin_view'] == 'Feedback':

        st.title("📬 User Requests & Feedback")
        st.info("View requests submitted by users regarding new movies or shows.")
        
        df_feedback = admin_sys.get_all_feedback()
        
        if not df_feedback.empty:
            df_feedback = df_feedback.rename(columns={
                "fullname": "User Name", 
                "email": "User Email", 
                "request_content": "Request", 
                "created_at": "Submitted Date"
            })
            st.dataframe(df_feedback, use_container_width=True)
        else:
            st.success("No user feedback found. Users have not requested anything yet.")

    elif st.session_state['admin_view'] == 'Manage':
        st.title("👥 User Management")
        st.info("Search for users to Suspend, Activate, or Delete accounts.")
        
        # Search Box
        search_email = st.text_input("🔍 Search by Email")
        df_users = admin_sys.get_all_data("users")
        
        if search_email:
            # Filter dataframe to show only matches
            df_users = df_users[df_users['email'].str.contains(search_email, case=False, na=False)]
        
        # Display Users Table
        if not df_users.empty:
            st.dataframe(df_users, use_container_width=True)
            
            st.divider()
            st.subheader("🛠️ Perform Action")
            
            c1, c2, c3 = st.columns([1, 1, 1])
            
            with c1:
                target_id = st.number_input("Enter User ID to Act On", min_value=1, step=1)
            
            with c2:
                action = st.selectbox("Select Action", ["Choose...", "Suspend", "Activate", "Delete"])
                
            with c3:
                st.write("") # Spacer
                if action == "Suspend":
                    if st.button("⛔ Suspend", type="primary"):
                        if user_sys.change_user_status(target_id, "SUSPENDED"):
                            st.success("User Suspended!")
                            st.rerun()
                        else:
                            st.error("Failed to suspend.")
                            
                elif action == "Activate":
                    if st.button("✅ Activate", type="primary"):
                        if user_sys.change_user_status(target_id, "USER"):
                            st.success("User Activated!")
                            st.rerun()
                        else:
                            st.error("Failed to activate.")
                            
                elif action == "Delete":
                    if st.button("🗑️ Delete", type="primary"):
                        if user_sys.delete_user(target_id):
                            st.warning("User Deleted Successfully.")
                            st.rerun()
                        else:
                            st.error("Failed to delete (User might have active subscriptions).")
        else:
            st.warning("No users found.")

    elif st.session_state['admin_view'] == 'Payments':
        st.title("💳 Payment Dashboard — NEW vs RENEWAL Analysis")
        st.info("Complete breakdown of all revenue — new subscriptions vs renewals.")

        # ── FETCH ALL DATA ──────────────────────────────────────────
        df_payments        = admin_sys.get_all_payments()
        df_new_vs_renewal  = admin_sys.get_new_vs_renewal_revenue()
        df_monthly_trend   = admin_sys.get_monthly_new_vs_renewal()
        renewal_rate, renewal_rev, renewal_count, total_count = admin_sys.get_renewal_rate()

        # ── SECTION 1: METRIC CARDS ─────────────────────────────────
        st.subheader("📊 Revenue Summary")

        # Parse values safely
        total_rev    = df_payments['amount'].sum() if not df_payments.empty else 0
        new_rev      = 0
        new_count    = 0
        ren_rev      = 0
        ren_count    = 0

        if not df_new_vs_renewal.empty:
            for _, row in df_new_vs_renewal.iterrows():
                if row['payment_type'] == 'NEW':
                    new_rev   = float(row['total_revenue'])
                    new_count = int(row['txn_count'])
                elif row['payment_type'] == 'RENEWAL':
                    ren_rev   = float(row['total_revenue'])
                    ren_count = int(row['txn_count'])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Total Revenue",      f"₹{total_rev:,.0f}", f"{total_count} transactions")
        m2.metric("🆕 New Subscriptions",  f"₹{new_rev:,.0f}",   f"{new_count} transactions")
        m3.metric("🔄 Renewal Revenue",    f"₹{ren_rev:,.0f}",   f"{ren_count} transactions")
        m4.metric("📈 Renewal Rate",       f"{renewal_rate}%",
                  delta="Healthy ✅" if renewal_rate >= 30 else "Low ⚠️",
                  delta_color="normal" if renewal_rate >= 30 else "inverse")

        st.divider()

        # ── SECTION 2: NEW vs RENEWAL BAR CHART ─────────────────────
        st.subheader("📊 NEW vs RENEWAL — Revenue Comparison")
        st.caption("How much total money came from brand new subscriptions vs renewals.")

        if not df_new_vs_renewal.empty:
            col1, col2 = st.columns([1, 1])

            with col1:
                # Bar chart — Revenue comparison
                fig_bar = px.bar(
                    df_new_vs_renewal,
                    x='payment_type',
                    y='total_revenue',
                    color='payment_type',
                    color_discrete_map={'NEW': '#E50914', 'RENEWAL': '#28a745'},
                    title="Total Revenue: NEW vs RENEWAL",
                    labels={'payment_type': 'Payment Type', 'total_revenue': 'Revenue (₹)'},
                    text='total_revenue'
                )
                fig_bar.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            with col2:
                # Pie chart — Revenue split
                fig_pie = px.pie(
                    df_new_vs_renewal,
                    names='payment_type',
                    values='total_revenue',
                    hole=0.5,
                    title="Revenue Split (%)",
                    color='payment_type',
                    color_discrete_map={'NEW': '#E50914', 'RENEWAL': '#28a745'}
                )
                fig_pie.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No payment data available yet.")

        st.divider()

        # ── SECTION 3: MONTHLY TREND LINE CHART ─────────────────────
        st.subheader("📈 Monthly Revenue Trend — NEW vs RENEWAL")
        st.caption("Month by month — are renewals growing? Are new signups increasing?")

        if not df_monthly_trend.empty:
            fig_line = px.line(
                df_monthly_trend,
                x='month',
                y='total_revenue',
                color='payment_type',
                markers=True,
                line_shape='spline',
                title="Monthly Revenue Trend by Payment Type",
                labels={'month': 'Month', 'total_revenue': 'Revenue (₹)', 'payment_type': 'Type'},
                color_discrete_map={'NEW': '#E50914', 'RENEWAL': '#28a745'}
            )
            fig_line.update_layout(hovermode='x unified')
            st.plotly_chart(fig_line, use_container_width=True)

            # Monthly table below chart
            st.caption("📋 Monthly Breakdown Table")
            df_pivot = df_monthly_trend.pivot(index='month', columns='payment_type', values='total_revenue').fillna(0).reset_index()
            df_pivot.columns.name = None
            st.dataframe(df_pivot, use_container_width=True)
        else:
            st.info("Not enough monthly data yet.")

        st.divider()

        # ── SECTION 4: RENEWAL RATE EXPLANATION ─────────────────────
        st.subheader("📉 Renewal Rate Analysis")

        col1, col2 = st.columns([1, 2])
        with col1:
            # Gauge-style metric
            if renewal_rate >= 50:
                st.success(f"### 🟢 {renewal_rate}% Renewal Rate")
                st.write("**Excellent!** More than half your revenue comes from returning users.")
            elif renewal_rate >= 30:
                st.warning(f"### 🟡 {renewal_rate}% Renewal Rate")
                st.write("**Good.** A decent portion of revenue comes from renewals. Room to improve.")
            else:
                st.error(f"### 🔴 {renewal_rate}% Renewal Rate")
                st.write("**Low!** Most revenue is from new users. Focus on retaining existing subscribers.")

        with col2:
            st.markdown("""
            #### 📖 What does Renewal Rate mean?
            | Rate | Meaning |
            |------|---------|
            | **Above 50%** | 🟢 Excellent — users love the service |
            | **30% – 50%** | 🟡 Good — healthy growth |
            | **Below 30%** | 🔴 Low — users are not coming back |

            **Formula used:**
            ```
            Renewal Rate = (Renewal Revenue / Total Revenue) × 100
            ```
            """)

        st.divider()

        # ── SECTION 5: FULL TRANSACTION TABLE ───────────────────────
        st.subheader("📋 All Transactions")

        if not df_payments.empty:
            df_display = df_payments.rename(columns={
                'payment_id': 'Txn ID',
                'fullname':   'User',
                'email':      'Email',
                'plan_name':  'Plan',
                'amount':     'Amount (₹)',
                'payment_type':   'Type',
                'payment_status': 'Status',
                'payment_date':   'Date'
            })
            st.dataframe(df_display, use_container_width=True)

            # Download CSV
            csv = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Full Payment Report (CSV)",
                data=csv,
                file_name='payment_report.csv',
                mime='text/csv'
            )
        else:
            st.info("No payment records found yet.")

    elif st.session_state['admin_view'] == 'AtRisk':
        st.title("🚨 At-Risk Users Report")
        st.info("Users with an ACTIVE subscription who have NOT logged in for 30+ days. These users are likely to cancel soon.")

        # --- THRESHOLD SLIDER ---
        days_filter = st.slider("Show users inactive for more than X days:", 
                                min_value=7, max_value=90, value=30, step=7)

        df_risk = admin_sys.get_at_risk_users(days_filter)

        st.divider()

        if not df_risk.empty:
            # --- SUMMARY METRIC CARDS ---
            total_risk       = len(df_risk)
            critical_risk    = len(df_risk[df_risk['days_inactive'] >= 60])
            high_risk        = len(df_risk[(df_risk['days_inactive'] >= 45) & (df_risk['days_inactive'] < 60)])
            medium_risk      = len(df_risk[(df_risk['days_inactive'] >= 30) & (df_risk['days_inactive'] < 45)])
            revenue_at_risk  = df_risk['amount'].sum()

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("⚠️ Total At-Risk",    total_risk)
            m2.metric("🔴 Critical (60+ d)", critical_risk)
            m3.metric("🟠 High (45-60d)",    high_risk)
            m4.metric("🟡 Medium (30-45d)",  medium_risk)
            m5.metric("💰 Revenue at Risk",  f"₹{revenue_at_risk:,.0f}")

            st.divider()

            # --- RISK LEVEL COLUMN ---
            def get_risk_level(days):
                if days is None or days >= 60:
                    return "🔴 Critical"
                elif days >= 45:
                    return "🟠 High"
                else:
                    return "🟡 Medium"

            df_risk['Risk Level']    = df_risk['days_inactive'].apply(get_risk_level)
            df_risk['last_login']    = pd.to_datetime(df_risk['last_login']).dt.strftime("%d %b %Y")
            df_risk['end_date']      = pd.to_datetime(df_risk['end_date']).dt.strftime("%d %b %Y")

            # --- TWO CHARTS SIDE BY SIDE ---
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("🥧 **At-Risk Users by Risk Level**")
                risk_counts = df_risk['Risk Level'].value_counts().reset_index()
                risk_counts.columns = ['Risk Level', 'Count']
                color_map = {
                    "🔴 Critical": "#E50914",
                    "🟠 High":     "#FF6B35",
                    "🟡 Medium":   "#FFC107"
                }
                fig_risk_pie = px.pie(
                    risk_counts, names='Risk Level', values='Count',
                    hole=0.4, title="Risk Distribution",
                    color='Risk Level', color_discrete_map=color_map
                )
                st.plotly_chart(fig_risk_pie, use_container_width=True)

            with c2:
                st.markdown("📊 **Revenue at Risk by Plan**")
                df_plan_risk = df_risk.groupby('plan_name')['amount'].sum().reset_index()
                df_plan_risk.columns = ['Plan', 'Revenue at Risk']
                fig_plan_risk = px.bar(
                    df_plan_risk, x='Plan', y='Revenue at Risk',
                    color='Plan', title="Revenue at Risk by Plan",
                    color_discrete_sequence=["#E50914", "#FF6B35", "#FFC107"],
                    text='Revenue at Risk'
                )
                fig_plan_risk.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig_plan_risk, use_container_width=True)

            st.divider()

            # --- FULL TABLE ---
            st.subheader("📋 Full At-Risk User List")
            df_display = df_risk[[
                'fullname', 'email', 'country', 'plan_name',
                'amount', 'last_login', 'end_date', 'days_inactive', 'Risk Level'
            ]].rename(columns={
                'fullname':     'Name',
                'email':        'Email',
                'country':      'Country',
                'plan_name':    'Plan',
                'amount':       'Amount (₹)',
                'last_login':   'Last Login',
                'end_date':     'Plan Expires',
                'days_inactive':'Days Inactive'
            })
            st.dataframe(df_display, use_container_width=True)

            # --- CSV DOWNLOAD ---
            csv = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download At-Risk Report (CSV)",
                data=csv,
                file_name="at_risk_users.csv",
                mime="text/csv"
            )
        else:
            st.success(f"✅ No at-risk users found! All active subscribers logged in within the last {days_filter} days.")

    elif st.session_state['admin_view'] == 'Forecast':
        st.title("📈 Revenue Forecast")
        st.info("Predicted next month revenue based on active subscriptions, renewal rate and new user trends.")

        forecast = admin_sys.get_revenue_forecast()

        # --- ROW 1: KEY METRIC CARDS ---
        st.subheader("📊 Forecast Inputs")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("👥 Active Subscribers",   forecast['active_count'])
        m2.metric("💰 Avg Plan Price",        f"₹{forecast['avg_price']}")
        m3.metric("🔄 Renewal Rate",          f"{forecast['renewal_rate']}%")
        m4.metric("🆕 Avg New Users/Month",   forecast['avg_new_per_month'])

        st.divider()

        # --- ROW 2: BIG FORECAST NUMBER ---
        st.subheader("🎯 Next Month Forecast")
        fc1, fc2, fc3 = st.columns(3)

        fc1.markdown(f"""
        <div style="padding:25px; border-radius:12px; background:#1a1a1a; 
                    border:2px solid #E50914; text-align:center; color:white;">
            <p style="color:#aaa; font-size:14px;">🔄 From Renewals</p>
            <h2 style="color:#28a745;">₹{forecast['renewal_revenue']:,.0f}</h2>
            <p style="color:#aaa;">{forecast['renewal_count']} users expected to renew</p>
        </div>
        """, unsafe_allow_html=True)

        fc2.markdown(f"""
        <div style="padding:25px; border-radius:12px; background:#E50914;
                    text-align:center; color:white;">
            <p style="font-size:14px; opacity:0.9;">📈 TOTAL FORECAST</p>
            <h1>₹{forecast['total_forecast']:,.0f}</h1>
            <p style="opacity:0.9;">Next Month Prediction</p>
        </div>
        """, unsafe_allow_html=True)

        fc3.markdown(f"""
        <div style="padding:25px; border-radius:12px; background:#1a1a1a;
                    border:2px solid #28a745; text-align:center; color:white;">
            <p style="color:#aaa; font-size:14px;">🆕 From New Users</p>
            <h2 style="color:#28a745;">₹{forecast['new_user_revenue']:,.0f}</h2>
            <p style="color:#aaa;">{forecast['avg_new_per_month']} new users expected</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # --- ROW 3: BREAKDOWN BAR CHART ---
        st.subheader("📊 Revenue Breakdown")
        c1, c2 = st.columns(2)

        with c1:
            breakdown_data = {
                'Source':  ['🔄 Renewals',               '🆕 New Users'],
                'Revenue': [forecast['renewal_revenue'],  forecast['new_user_revenue']]
            }
            df_breakdown = pd.DataFrame(breakdown_data)
            fig_breakdown = px.bar(
                df_breakdown, x='Source', y='Revenue',
                color='Source',
                color_discrete_map={'🔄 Renewals': '#28a745', '🆕 New Users': '#E50914'},
                title="Forecast Revenue by Source",
                labels={'Revenue': 'Predicted Revenue (₹)'},
                text='Revenue'
            )
            fig_breakdown.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
            fig_breakdown.update_layout(showlegend=False)
            st.plotly_chart(fig_breakdown, use_container_width=True)

        with c2:
            # Pie chart — share of forecast
            fig_pie = px.pie(
                df_breakdown, names='Source', values='Revenue',
                hole=0.5, title="Forecast Revenue Split",
                color='Source',
                color_discrete_map={'🔄 Renewals': '#28a745', '🆕 New Users': '#E50914'}
            )
            fig_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # --- ROW 4: CONFIDENCE METER ---
        st.subheader("🎯 Forecast Confidence")
        confidence = forecast['confidence']
        conf_color = "#28a745" if confidence >= 70 else "#FFC107" if confidence >= 50 else "#E50914"
        conf_label = "High ✅" if confidence >= 70 else "Medium ⚠️" if confidence >= 50 else "Low ❌"

        st.progress(confidence / 100, text=f"Confidence Level: {confidence}% — {conf_label}")

        st.markdown(f"""
        <div style="padding:20px; border-radius:10px; background:#1a1a1a; color:white; margin-top:10px;">
            <h4 style="color:{conf_color};">Why {confidence}% Confidence?</h4>
            <p style="color:#aaa;">The forecast is based on your real database data:</p>
            <ul style="color:#ccc;">
                <li>✅ Active subscriber count: <b>{forecast['active_count']} users</b></li>
                <li>✅ Renewal rate from payments history: <b>{forecast['renewal_rate']}%</b></li>
                <li>✅ New user trend from last 3 months: <b>{forecast['avg_new_per_month']} avg/month</b></li>
                <li>⚠️ Assumes plan prices stay same next month</li>
                <li>⚠️ Assumes renewal rate stays consistent</li>
            </ul>
            <p style="color:#aaa; font-size:12px;">Confidence increases as more payment history is recorded.</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # --- ROW 5: FORMULA EXPLANATION ---
        with st.expander("📖 How is this Forecast Calculated? (Click to see)"):
            st.markdown(f"""
            #### Step by Step Formula:

            **Step 1 — Count Active Subscribers**
            ```
            Active Users = {forecast['active_count']}
            ```

            **Step 2 — Average Plan Price**
            ```
            Avg Price = Total Active Revenue / Active Count
                      = ₹{forecast['avg_price']}
            ```

            **Step 3 — Apply Renewal Rate**
            ```
            Renewal Rate    = {forecast['renewal_rate']}%
            Expected Renewals = {forecast['active_count']} × {forecast['renewal_rate']}%
                              = {forecast['renewal_count']} users
            Renewal Revenue = {forecast['renewal_count']} × ₹{forecast['avg_price']}
                            = ₹{forecast['renewal_revenue']:,.0f}
            ```

            **Step 4 — New User Revenue**
            ```
            Avg New Users/Month (last 3 months) = {forecast['avg_new_per_month']}
            New User Revenue = {forecast['avg_new_per_month']} × ₹{forecast['avg_price']}
                             = ₹{forecast['new_user_revenue']:,.0f}
            ```

            **Step 5 — Total Forecast**
            ```
            Total = Renewal Revenue + New User Revenue
                  = ₹{forecast['renewal_revenue']:,.0f} + ₹{forecast['new_user_revenue']:,.0f}
                  = ₹{forecast['total_forecast']:,.0f}
            ```
            """)

    elif st.session_state['admin_view'] == 'GlobalSearch':
        st.title("🔍 Global User Search")
        st.info("Search across the entire database using multiple filters (Email, Country, Plan).")
        
        # Input Fields for Search
        c1, c2, c3 = st.columns(3)
        
        with c1:
            email_f = st.text_input("Search by Email")
        
        with c2:
            # Dropdown with "All" option for no filter
            country_f = st.selectbox("Filter by Country", ["All", "India", "USA", "UK", "Canada", "Germany"])
        
        with c3:
            # Dropdown with "All" option for no filter
            plan_f = st.selectbox("Filter by Plan", ["All", "Mobile", "Standard", "Premium"])
            
        # Search Button
        st.divider()
        if st.button("🔎 Perform Search", type="primary"):
            df_results = admin_sys.search_global_users(email_f, country_f, plan_f)
            
            if not df_results.empty:
                st.success(f"Found {len(df_results)} records matching your criteria.")
                
                # Display the combined data (User Details + Subscription Details)
                # Rename columns for cleaner display
                df_display = df_results.rename(columns={
                    "user_id": "User ID",
                    "fullname": "Name",
                    "email": "Email",
                    "country": "Country",
                    "age": "Age",
                    "plan_name": "Plan",
                    "status": "Sub Status",
                    "amount": "Amount"
                })
                
                st.dataframe(df_display, use_container_width=True)
            else:
                st.warning("No matches found for the selected filters.")
    # ═══════════════════════════════════════════════════════
    # ADMIN — CONTENT LIBRARY ANALYTICS
    # ═══════════════════════════════════════════════════════
    elif st.session_state['admin_view'] == 'ContentLib':
        st.title("📺 Content Library Manager")
        st.info("Overview of all Netflix titles loaded from the Kaggle dataset.")

        if not content_mgr.is_content_loaded():
            st.warning("⚠️ No content loaded yet.")
            st.code("python load_kaggle_content.py", language="bash")
            st.stop()

        total, movies, shows = content_mgr.get_content_stats()

        # ── Metric Cards ─────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("📊 Total Titles", f"{total:,}")
        m2.metric("🎬 Movies",       f"{movies:,}")
        m3.metric("📺 TV Shows",     f"{shows:,}")

        st.divider()

        # ── Genre Distribution Chart ──────────────────────────
        g1, g2 = st.columns(2)

        with g1:
            st.subheader("🎭 Top 15 Genres")
            df_genres = content_mgr.get_genre_distribution()
            if not df_genres.empty:
                fig_genre = px.bar(
                    df_genres, x='count', y='genre',
                    orientation='h',
                    title="Most Common Genres",
                    color='count',
                    color_continuous_scale='Reds',
                    labels={'count': 'Number of Titles', 'genre': 'Genre'}
                )
                fig_genre.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_genre, use_container_width=True)

        with g2:
            st.subheader("📅 Titles Added by Year")
            df_yearly = content_mgr.get_yearly_additions()
            if not df_yearly.empty:
                fig_year = px.line(
                    df_yearly, x='release_year', y='count',
                    title="Content Added Per Year",
                    markers=True, line_shape='spline',
                    labels={'release_year': 'Year', 'count': 'Titles'}
                )
                fig_year.update_traces(line_color='#E50914')
                st.plotly_chart(fig_year, use_container_width=True)

        st.divider()

        # ── Movie vs TV Show split ────────────────────────────
        st.subheader("🎞️ Movie vs TV Show Split")
        split_data = pd.DataFrame({'Type': ['Movie', 'TV Show'], 'Count': [movies, shows]})
        fig_split = px.pie(split_data, names='Type', values='Count',
                           hole=0.5,
                           color='Type',
                           color_discrete_map={'Movie': '#E50914', 'TV Show': '#0070f3'},
                           title="Content Type Distribution")
        st.plotly_chart(fig_split, use_container_width=True)

        st.divider()

        # ── Browse / Search table for admin ──────────────────
        st.subheader("🔍 Search Content")
        c1, c2, c3 = st.columns([2, 2, 3])
        with c1:
            adm_type = st.selectbox("Type", ["All", "Movie", "TV Show"], key="adm_type")
        with c2:
            adm_genres = ["All"] + content_mgr.get_all_genres()
            adm_genre = st.selectbox("Genre", adm_genres, key="adm_genre")
        with c3:
            adm_search = st.text_input("Search title / cast", key="adm_search")

        df_adm, adm_total = content_mgr.browse_content(
            content_type=adm_type,
            genre_filter=adm_genre,
            search_query=adm_search,
            page=1,
            page_size=50
        )
        st.caption(f"Showing top 50 of **{adm_total:,}** results")
        if not df_adm.empty:
            st.dataframe(
                df_adm[['content_type','title','genre','release_year','rating','duration','description']].rename(columns={
                    'content_type': 'Type', 'title': 'Title', 'genre': 'Genre',
                    'release_year': 'Year', 'rating': 'Rating', 'duration': 'Duration',
                    'description': 'Description'
                }),
                use_container_width=True
            )
            csv_content = df_adm.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download as CSV", data=csv_content,
                               file_name="netflix_content.csv", mime="text/csv")
        else:
            st.info("No results found.")