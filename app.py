import streamlit as st
import pandas as pd
import plotly.express as px
import qrcode
from io import BytesIO
from datetime import datetime

from backend import UserModule, SubscriptionManager, ActivityTracker, AdminAnalytics, ContentManager, MutualConnectionManager
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
mutual_mgr  = MutualConnectionManager()

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

    /* ── Sidebar: rounded pill nav for BOTH user & admin panels ── */
    div[data-testid="stSidebar"] .stRadio > label {
        display: none;
    }
    div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
        display: flex !important;
        align-items: center;
        padding: 10px 16px;
        border-radius: 25px !important;
        background-color: #2b2b2b;
        color: #dddddd !important;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.2s, color 0.2s;
        border: 1.5px solid transparent;
        margin: 0 !important;
    }
    div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
        background-color: #3a3a3a;
        border-color: #E50914;
        color: #ffffff !important;
    }
    div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:has(input:checked) {
        background-color: #E50914 !important;
        color: #ffffff !important;
        border-color: #E50914 !important;
        font-weight: 700;
    }
    /* Hide the radio circle dot */
    div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label div:first-child {
        display: none !important;
    }

    /* ── Sidebar buttons (Logout, Cancel Subscription) → rounded pill ── */
    div[data-testid="stSidebar"] .stButton > button {
        border-radius: 25px !important;
        background-color: #2b2b2b !important;
        color: #dddddd !important;
        border: 1.5px solid transparent !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        padding: 10px 16px !important;
        width: 100% !important;
        transition: background 0.2s, color 0.2s, border-color 0.2s !important;
    }
    div[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #3a3a3a !important;
        border-color: #E50914 !important;
        color: #ffffff !important;
    }
    div[data-testid="stSidebar"] .stButton > button:active {
        background-color: #E50914 !important;
        color: #ffffff !important;
        border-color: #E50914 !important;
    }
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
    # Fetched once here and reused throughout the entire user session page
    active_plan = sub_sys.get_active_plan(st.session_state['user_id'])

    if active_plan:
        st.sidebar.warning("You have an active plan.")
        if st.sidebar.button("❌ Cancel Subscription", use_container_width=True):
            if sub_sys.cancel_subscription(st.session_state['user_id']):
                st.success("Subscription Cancelled Successfully!")
                st.rerun()
            else:
                st.error("Could not cancel. Please try again.")

    user_menu = st.sidebar.radio("Menu", ["🏠 Dashboard", "📺 Browse Content", "💬 Feedback", "🧾 My Transactions", "⚙️ My Profile", "🔔 Notifications"])

    # Notification badge — shows unread invite count next to bell
    _notif_count = mutual_mgr.get_notification_count(st.session_state['user_id'])
    if _notif_count > 0:
        st.sidebar.markdown(
            f'<div style="background:#E50914;color:white;padding:6px 12px;border-radius:8px;'
            f'text-align:center;font-weight:bold;margin-top:-8px;">'
            f'🔔 {_notif_count} New Invite{"s" if _notif_count > 1 else ""}!</div>',
            unsafe_allow_html=True
        )

    if st.sidebar.button("Logout"):
        tracker.log_out(st.session_state['act_id'])
        del st.session_state['user_id']
        st.rerun()

    # ── EXPIRY REMINDER ALERT (fires once per login session) ─────
    if 'expiry_alert_shown' not in st.session_state:
        st.session_state['expiry_alert_shown'] = True
        if active_plan:
            _days_left = (active_plan['end_date'] - datetime.now()).days
            if _days_left <= 3:
                st.toast(f"🚨 URGENT! Your plan expires in {_days_left} day(s)! Renew NOW.", icon="🚨")
            elif _days_left <= 7:
                st.toast(f"⚠️ Your plan expires in {_days_left} days on {active_plan['end_date'].strftime('%d %b %Y')}.", icon="⚠️")
        else:
            _expired = sub_sys.get_expired_plan(st.session_state['user_id'])
            if _expired:
                st.toast("🔴 Your subscription has expired! Go to Dashboard to renew.", icon="🔴")
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
                    st.warning("❌ Auto-Renewal is **OFF** — Scroll down to enable it.")

                st.markdown("#### 📊 Quick Stats")
                st.info(f"""
                - 🎬 Total Subscriptions Ever: **{dash['total_subs']}**
                - 💰 Lifetime Spend: **₹{dash['total_spend']:,.0f}**
                - ⏱️ Total Watch Time: **{dash['total_watch']} mins ({round(dash['total_watch']/60,1)} hrs)**
                """)
        else:
            # --- NO PLAN STATE ---
            st.warning("⚠️ You don't have an active subscription.")

            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Total Spent", f"₹{dash['total_spend']:,.0f}")
            c2.metric("⏱️ Watch Time", f"{dash['total_watch']} mins")
            c3.metric("📦 Past Subscriptions", dash['total_subs'])

        # ═══════════════════════════════════════════════════════
        # NETFLIX PLANS — merged into Dashboard
        # ═══════════════════════════════════════════════════════
        st.divider()

        if active_plan:
            # --- AUTO-RENEWAL TOGGLE ---
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

        else:
            expired_plan = sub_sys.get_expired_plan(st.session_state['user_id'])

            if expired_plan and not st.session_state.get('pending_purchase'):
                st.subheader("🔴 Your Subscription Has Expired")
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

            # --- STEP 2: CONFIRMATION SCREEN ---
            if st.session_state.get('pending_purchase'):
                purchase = st.session_state['pending_purchase']
                st.subheader("✅ Confirm Your Subscription")

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
                        txt, _ = sub_sys.buy_plan(st.session_state['user_id'], purchase['name'], purchase['price'], "Netflix")

                        qr_data = f"PAID|{purchase['name']}|{purchase['price']}|{st.session_state['email']}"
                        qr = qrcode.make(qr_data)
                        img_buffer = BytesIO()
                        qr.save(img_buffer, format="PNG")

                        st.balloons()
                        st.success("Payment Successful!")
                        st.image(img_buffer, caption="Scan to verify Subscription", width=200)

                        st.download_button(
                            "📥 Download Receipt (PDF)",
                            data=txt,
                            file_name=f"Netflix_Receipt_{purchase['name']}.pdf",
                            mime="application/pdf"
                        )

                        st.session_state['pending_purchase'] = None
                        st.rerun()

            # --- STEP 1: DISPLAY PLANS ---
            else:
                st.subheader("🔴 Choose Your Netflix Plan")
                st.info("No active subscription found. Please select a plan to start watching.")

                plans = [
                    {"name": "Mobile",   "price": 149, "res": "480p",   "features": "1 Phone, 1 Tablet, Download"},
                    {"name": "Standard", "price": 499, "res": "1080p",  "features": "2 Screens, HD, Download"},
                    {"name": "Premium",  "price": 649, "res": "4K+HDR", "features": "4 Screens, Ultra HD, Spatial Audio"}
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

        # ── Mutual Connection Status Card (always visible in dashboard) ──
        st.divider()
        _grp_info, _members_df = mutual_mgr.get_user_active_connection(st.session_state['user_id'])
        _notif_badge = mutual_mgr.get_notification_count(st.session_state['user_id'])

        if _grp_info:
            savings = float(_grp_info['full_price']) - float(_grp_info['split_price'])
            st.markdown(f"""
            <div style="padding:20px;border-radius:12px;background:linear-gradient(135deg,#0f3460,#16213e);
                        border:2px solid #00ff88;margin-bottom:10px;">
                <h3 style="color:#00ff88;margin:0 0 8px 0;">🤝 Active Mutual Connection</h3>
                <p style="color:white;margin:4px 0;">
                    <b>Plan:</b> Netflix {_grp_info['plan_name']}
                    &nbsp;|&nbsp;
                    <b>You Pay:</b>
                    <span style="color:#00ff88;font-weight:bold;font-size:18px;">
                        ₹{float(_grp_info['split_price']):,.2f}/month
                    </span>
                    &nbsp;
                    <span style="background:#00ff88;color:#000;padding:2px 8px;border-radius:4px;font-size:12px;">
                        Saving ₹{savings:,.2f}
                    </span>
                </p>
                <p style="color:#aaa;font-size:12px;margin:4px 0;">
                    👥 {int(_grp_info['max_members'])} members sharing this plan
                    &nbsp;|&nbsp; Go to 🔔 Notifications to see full group details
                </p>
            </div>
            """, unsafe_allow_html=True)
        elif _notif_badge > 0:
            st.markdown(f"""
            <div style="padding:15px;border-radius:10px;background:#2d1a1a;border:2px solid #E50914;">
                <h4 style="color:#E50914;margin:0;">
                    🔔 You have {_notif_badge} pending mutual connection invite{"s" if _notif_badge>1 else ""}!
                </h4>
                <p style="color:#aaa;margin:4px 0 0 0;font-size:13px;">
                    Go to 🔔 Notifications in the menu to review and accept/decline.
                </p>
            </div>
            """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════
    # MUTUAL CONNECTION STATUS — shown inside Dashboard
    # ═══════════════════════════════════════════════════════
    elif user_menu == "🔔 Notifications":
        st.title("🔔 Notifications & Mutual Connection Invites")
        st.caption("Here you will receive plan-sharing invites from the admin.")
        st.divider()

        all_invites = mutual_mgr.get_all_user_invites(st.session_state['user_id'])

        if all_invites.empty:
            st.info("📭 No notifications yet. Check back later!")
        else:
            pending_df  = all_invites[all_invites['invite_status'] == 'PENDING']
            past_df     = all_invites[all_invites['invite_status'] != 'PENDING']

            # ── PENDING INVITES ──────────────────────────────────
            if not pending_df.empty:
                st.subheader(f"📩 Pending Invites ({len(pending_df)})")
                for _, inv in pending_df.iterrows():
                    savings = float(inv['full_price']) - float(inv['split_price'])
                    with st.container():
                        st.markdown(f"""
                        <div style="padding:20px;border-radius:12px;background:#1a1a2e;
                                    border:2px solid #E50914;margin-bottom:15px;">
                            <h3 style="color:#E50914;margin:0;">🤝 Mutual Connection Invite</h3>
                            <p style="color:#aaa;font-size:12px;margin:4px 0 12px 0;">
                                Received on {inv['sent_at'].strftime('%d %b %Y, %I:%M %p')}
                                &nbsp;|&nbsp; Group #{inv['group_id']}
                            </p>
                            <p style="color:white;"><b>Plan:</b> Netflix {inv['plan_name']}</p>
                            <p style="color:white;">
                                <b>Full Price:</b>
                                <span style="text-decoration:line-through;color:#888;">
                                    ₹{float(inv['full_price']):,.0f}
                                </span>
                                &nbsp;→&nbsp;
                                <span style="color:#00ff88;font-size:18px;font-weight:bold;">
                                    ₹{float(inv['split_price']):,.2f}/month
                                </span>
                                &nbsp;
                                <span style="background:#00ff88;color:#000;padding:2px 8px;
                                             border-radius:4px;font-size:12px;">
                                    Save ₹{savings:,.2f}!
                                </span>
                            </p>
                            <p style="color:white;">
                                <b>Group Size:</b> {inv['max_members']} members sharing this plan
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        if inv['admin_message']:
                            st.info(f"💬 Message from Admin: \"{inv['admin_message']}\"")

                        btn_col1, btn_col2, _ = st.columns([1, 1, 2])
                        with btn_col1:
                            if st.button("✅ Accept", key=f"acc_{inv['invite_id']}",
                                         type="primary", use_container_width=True):
                                ok, msg = mutual_mgr.respond_to_invite(
                                    inv['invite_id'], st.session_state['user_id'], True
                                )
                                if ok:
                                    st.success(f"🎉 {msg}")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with btn_col2:
                            if st.button("❌ Decline", key=f"dec_{inv['invite_id']}",
                                         use_container_width=True):
                                ok, msg = mutual_mgr.respond_to_invite(
                                    inv['invite_id'], st.session_state['user_id'], False
                                )
                                if ok:
                                    st.warning(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        st.divider()

            # ── PAST INVITES (already responded) ─────────────────
            if not past_df.empty:
                st.subheader("📋 Past Invites")
                for _, inv in past_df.iterrows():
                    status_color = "#00ff88" if inv['invite_status'] == 'ACCEPTED' else "#ff4444"
                    status_icon  = "✅" if inv['invite_status'] == 'ACCEPTED' else "❌"
                    st.markdown(f"""
                    <div style="padding:15px;border-radius:10px;background:#111;
                                border:1px solid #333;margin-bottom:10px;">
                        <span style="color:{status_color};font-weight:bold;">
                            {status_icon} {inv['invite_status']}
                        </span>
                        &nbsp;|&nbsp;
                        <span style="color:white;">Netflix {inv['plan_name']}</span>
                        &nbsp;|&nbsp;
                        <span style="color:#E50914;">₹{float(inv['split_price']):,.2f}/month</span>
                        &nbsp;|&nbsp;
                        <span style="color:#888;font-size:12px;">Group #{inv['group_id']}</span>
                        &nbsp;|&nbsp;
                        <span style="color:#888;font-size:12px;">
                            Responded: {inv['responded_at'].strftime('%d %b %Y') if inv['responded_at'] is not None else '—'}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

        # ── Active Group Details ─────────────────────────────────
        st.divider()
        group_info, members_df = mutual_mgr.get_user_active_connection(
            st.session_state['user_id']
        )
        if group_info:
            st.subheader("🤝 Your Active Mutual Connection Group")
            savings = float(group_info['full_price']) - float(group_info['split_price'])
            g1, g2, g3 = st.columns(3)
            g1.metric("📦 Plan",         f"Netflix {group_info['plan_name']}")
            g2.metric("💰 You Pay",       f"₹{float(group_info['split_price']):,.2f}/mo",
                      delta=f"Save ₹{savings:,.2f}")
            g3.metric("👥 Group Size",    f"{int(group_info['max_members'])} members")

            st.markdown("#### 👥 Group Members")
            for _, m in members_df.iterrows():
                badge_color = "#00ff88" if m['invite_status'] == 'ACCEPTED' else "#ff9900"
                badge_text  = m['invite_status']
                st.markdown(f"""
                <div style="padding:10px 15px;border-radius:8px;background:#1a1a2e;
                            border-left:3px solid {badge_color};margin-bottom:8px;
                            display:flex;justify-content:space-between;">
                    <span style="color:white;">👤 {m['fullname']}
                        <span style="color:#888;font-size:12px;"> — {m['country']}</span>
                    </span>
                    <span style="color:{badge_color};font-size:12px;font-weight:bold;">
                        {badge_text}
                    </span>
                </div>
                """, unsafe_allow_html=True)

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
        if not active_plan:
            st.error("🔒 **Content Library is locked.** You need an active subscription to browse.")
            st.info("Go to **🏠 Dashboard** to choose a plan and subscribe.")
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
                            <div style="padding:15px; border-radius:10px; background:#1a1a2e;
                                        border:1px solid #333; margin-bottom:10px; min-height:200px;">
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
                                <p style="color:#ccc; font-size:12px; line-height:1.4;">
                                    {str(row['description'])[:130]}{'...' if len(str(row['description'])) > 130 else ''}
                                </p>
                                <p style="color:#E50914; font-size:10px; margin-top:8px;">
                                    🎭 {str(row['genre'])[:60]}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

# ================= 3. ADMIN DASHBOARD =================
elif is_admin_logged_in:
    with st.sidebar:
        st.title("🛠️ Admin Panel")

        _admin_nav_options = [
            "📊 Analytics Dashboard",
            "📬 User Feedback",
            "👥 User Management",
            "💳 Payment History",
            "🚨 At-Risk Users",
            "📈 Revenue Forecast",
            "📺 Content Library",
            "🤝 Mutual Connections",
        ]
        _admin_nav_map = {
            "📊 Analytics Dashboard": "Analytics",
            "📬 User Feedback":       "Feedback",
            "👥 User Management":     "Manage",
            "💳 Payment History":     "Payments",
            "🚨 At-Risk Users":       "AtRisk",
            "📈 Revenue Forecast":    "Forecast",
            "📺 Content Library":     "ContentLib",
            "🤝 Mutual Connections":  "MutualConn",
        }
        # Find the currently selected label so radio stays in sync
        _reverse_map = {v: k for k, v in _admin_nav_map.items()}
        _current_label = _reverse_map.get(st.session_state['admin_view'], "📊 Analytics Dashboard")

        _selected = st.sidebar.radio(
            "Navigation",
            _admin_nav_options,
            index=_admin_nav_options.index(_current_label),
            label_visibility="collapsed"
        )
        st.session_state['admin_view'] = _admin_nav_map[_selected]

        st.divider()
        if st.button("🚪 Logout Admin", use_container_width=True):
            del st.session_state['admin_auth']; st.rerun()

    if st.session_state['admin_view'] == 'Analytics':
        st.title("🚀 Business Intelligence Dashboard")

        # ══════════════════════════════════════════════════════════
        # SHARED THEME — Simple 3-Color Palette
        # Background: dark grey | Accent: blue | Status: green / red
        # ══════════════════════════════════════════════════════════
        _CHART_BG   = "#1C1C1C"   # dark grey plot area
        _PAPER_BG   = "#252525"   # slightly lighter grey card bg
        _FONT_COLOR = "#F0F0F0"   # clean white text
        _GRID_COLOR = "#333333"   # subtle grey gridlines

        # 3 accent colors only — used consistently across all charts
        _BLUE       = "#4F8EF7"   # main accent — bars, lines, highlights
        _GREEN      = "#27AE60"   # positive state — active subscriptions
        _RED        = "#E74C3C"   # negative state — cancelled, danger

        # Plan colors — shades of blue so it stays in one family
        _PLAN_COLORS = {
            "Mobile":   "#4F8EF7",   # base blue
            "Standard": "#1E5DC9",   # darker blue
            "Premium":  "#8AB4F8",   # lighter blue
        }

        def _base_layout(**kwargs):
            """Consistent dark-grey layout applied to every chart."""
            base = dict(
                paper_bgcolor=_PAPER_BG,
                plot_bgcolor=_CHART_BG,
                font=dict(color=_FONT_COLOR, family="Arial, sans-serif", size=12),
                margin=dict(l=48, r=48, t=56, b=44),
                legend=dict(
                    bgcolor="rgba(0,0,0,0)",
                    bordercolor=_GRID_COLOR,
                    borderwidth=1,
                    font=dict(color=_FONT_COLOR, size=12),
                ),
            )
            base.update(kwargs)
            return base

        # ── DOWNLOAD CSV ──────────────────────────────────────────
        df_subs = admin_sys.get_all_data("subscriptions")
        if not df_subs.empty:
            csv = df_subs.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Revenue Report (CSV)",
                data=csv,
                file_name="revenue_report.csv",
                mime="text/csv",
            )
        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 1 — GENERAL OVERVIEW  (Metric Cards)
        # ════════════════════════════════════════════════════════
        curr_rev, prev_rev, growth, last_year_rev, count, lifetime_rev = admin_sys.get_monthly_comparison()
        total_users = admin_sys.get_total_user_count()
        arpu = round(lifetime_rev / total_users, 2) if total_users > 0 else 0

        st.subheader("📊 Section 1 — General Overview")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Current Month Revenue",  f"₹{curr_rev:,.0f}",  f"{growth}% vs Last Month")
        m2.metric("📅 Last Month Revenue",      f"₹{prev_rev:,.0f}")
        m3.metric("🛒 This Month Sales Count",  count)
        m4.metric("👤 ARPU (Avg Rev/Paying User)", f"₹{arpu}")

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 2 — REVENUE CHARTS
        # Left  (60 %) : Revenue by Country  — horizontal bar, cyan gradient
        # Right (40 %) : Plan Popularity     — 3-color vertical bars
        # ════════════════════════════════════════════════════════
        st.subheader("📈 Section 2 — Revenue Charts")
        g2, g3 = st.columns([3, 2])

        df_subs_chart = admin_sys.get_all_data("subscriptions")

        with g2:
            st.markdown("🌍 **Revenue by Country**")
            try:
                df_map = admin_sys.get_revenue_by_country()
                if not df_map.empty:
                    fig_country = px.bar(
                        df_map,
                        x="revenue", y="country",
                        orientation="h",
                        text="revenue",
                        color="revenue",
                        color_continuous_scale=[
                            [0.0, "#1a2e4a"],
                            [1.0, _BLUE],
                        ],
                        labels={"revenue": "Revenue (₹)", "country": ""},
                    )
                    fig_country.update_traces(
                        texttemplate="₹%{text:,.0f}",
                        textposition="outside",
                        textfont=dict(color=_FONT_COLOR, size=11),
                        marker_line_width=0,
                    )
                    fig_country.update_layout(
                        _base_layout(
                            title=dict(
                                text="Total Revenue by Country (from Payments)",
                                font=dict(size=15, color=_FONT_COLOR),
                            ),
                            coloraxis_showscale=False,
                            xaxis=dict(
                                showgrid=True, gridcolor=_GRID_COLOR,
                                zeroline=False, tickfont=dict(color=_FONT_COLOR),
                            ),
                            yaxis=dict(showgrid=False, tickfont=dict(color=_FONT_COLOR, size=12)),
                            height=400,
                        )
                    )
                    st.plotly_chart(fig_country, use_container_width=True)
                else:
                    st.info("No payment data by country yet.")
            except Exception as e:
                st.info(f"Geographic data unavailable: {e}")

        with g3:
            st.markdown("💎 **Plan Popularity (Sales Count)**")
            df_plan_pop = admin_sys.get_plan_popularity()
            if not df_plan_pop.empty:
                fig_plan = px.bar(
                    df_plan_pop,
                    x="plan_name", y="total_sales",
                    text="total_sales",
                    color="plan_name",
                    color_discrete_map=_PLAN_COLORS,
                    labels={"plan_name": "Plan", "total_sales": "Units Sold"},
                )
                fig_plan.update_traces(
                    texttemplate="%{text}",
                    textposition="outside",
                    textfont=dict(color=_FONT_COLOR, size=13, family="Arial Black"),
                    marker_line_width=0,
                    width=0.42,
                )
                fig_plan.update_layout(
                    _base_layout(
                        title=dict(
                            text="Best Selling Plans",
                            font=dict(size=15, color=_FONT_COLOR),
                        ),
                        showlegend=False,
                        xaxis=dict(
                            showgrid=False,
                            tickfont=dict(color=_FONT_COLOR, size=14, family="Arial Black"),
                        ),
                        yaxis=dict(
                            showgrid=True, gridcolor=_GRID_COLOR,
                            tickfont=dict(color=_FONT_COLOR),
                        ),
                        height=400,
                    )
                )
                st.plotly_chart(fig_plan, use_container_width=True)

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 3 — REVENUE TREND  (full-width area chart)
        # Line: electric cyan  |  Fill: translucent cyan
        # Peak annotation in amber
        # ════════════════════════════════════════════════════════
        st.subheader("📉 Section 3 — Revenue Trend")
        df_trend = admin_sys.get_monthly_revenue_trend()
        if not df_trend.empty:
            fig_trend = px.area(
                df_trend, x="Month", y="Revenue",
                markers=True,
                line_shape="spline",
                labels={"Revenue": "Revenue (₹)", "Month": ""},
            )
            fig_trend.update_traces(
                line=dict(color=_BLUE, width=3),
                marker=dict(
                    size=10, color=_BLUE,
                    line=dict(color=_PAPER_BG, width=2),
                ),
                fillcolor="rgba(79,142,247,0.12)",
            )
            # Amber peak annotation
            peak_idx = df_trend["Revenue"].idxmax()
            peak_row = df_trend.loc[peak_idx]
            fig_trend.add_annotation(
                x=peak_row["Month"], y=peak_row["Revenue"],
                text=f"  ⭐ Peak  ₹{float(peak_row['Revenue']):,.0f}",
                showarrow=True, arrowhead=3, arrowwidth=2,
                arrowcolor=_BLUE,
                font=dict(color=_BLUE, size=13, family="Arial Black"),
                bgcolor="rgba(79,142,247,0.12)",
                bordercolor=_BLUE, borderwidth=1, borderpad=5,
                ax=0, ay=-48,
            )
            # Horizontal dashed average line
            avg_rev = df_trend["Revenue"].mean()
            fig_trend.add_hline(
                y=avg_rev,
                line_dash="dot", line_color="#888888", line_width=1.5,
                annotation_text=f"  Avg ₹{avg_rev:,.0f}",
                annotation_font_color="#AAAAAA",
                annotation_position="top left",
            )
            fig_trend.update_layout(
                _base_layout(
                    title=dict(
                        text="Monthly Revenue Trend — Last 6 Months",
                        font=dict(size=16, color=_FONT_COLOR),
                    ),
                    xaxis=dict(
                        showgrid=False,
                        tickfont=dict(color=_FONT_COLOR, size=12),
                    ),
                    yaxis=dict(
                        showgrid=True, gridcolor=_GRID_COLOR,
                        tickprefix="₹",
                        tickfont=dict(color=_FONT_COLOR),
                    ),
                    height=380,
                )
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No trend data available.")

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 4 — RETENTION & CHURN
        # Left donut : Active vs Cancelled  (emerald / rose / amber)
        # Right donut: Plan Revenue Share   (cyan / purple / amber)
        # ════════════════════════════════════════════════════════
        st.subheader("📉 Section 4 — Retention & Churn Metrics")
        total, churned, cancelled_only, expired_only, churn_rate = admin_sys.get_churn_stats()
        churn_color = "inverse" if churn_rate > 10 else "normal"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 Total Subscriptions", total)
        c2.metric("⏳ Expired (Not Renewed)", expired_only)
        c3.metric("❌ Cancelled by User",     cancelled_only)
        c4.metric("📊 Churn Rate",
                  f"{churn_rate}%",
                  delta=f"{churn_rate}% of all subs",
                  delta_color=churn_color,
                  help="Churn = (Expired + Cancelled) ÷ Total × 100")

        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown("🍩 **Active vs Cancelled Subscriptions**")
            df_status = admin_sys.get_active_vs_cancelled()
            if not df_status.empty:
                fig_ret = px.pie(
                    df_status, names="status", values="count",
                    hole=0.58,
                    color="status",
                    color_discrete_map={
                        "ACTIVE":    _GREEN,
                        "CANCELLED": _RED,
                        "EXPIRED":   "#888888",
                    },
                )
                fig_ret.update_traces(
                    textinfo="percent+label",
                    textfont=dict(size=13, color="white"),
                    marker=dict(line=dict(color=_PAPER_BG, width=4)),
                    pull=[0.05] * len(df_status),
                    rotation=90,
                )
                fig_ret.update_layout(
                    _base_layout(
                        title=dict(
                            text="Subscription Status Breakdown",
                            font=dict(size=15, color=_FONT_COLOR),
                        ),
                        legend=dict(
                            orientation="h", yanchor="bottom",
                            y=-0.22, xanchor="center", x=0.5,
                            font=dict(color=_FONT_COLOR, size=12),
                        ),
                        height=400,
                    )
                )
                st.plotly_chart(fig_ret, use_container_width=True)

        with ch2:
            st.markdown("🥧 **Plan Revenue Share**")
            df_rev = admin_sys.get_plan_revenue_share()
            if not df_rev.empty:
                fig_rev = px.pie(
                    df_rev, names="plan_name", values="total_revenue",
                    hole=0.58,
                    color="plan_name",
                    color_discrete_map=_PLAN_COLORS,
                )
                fig_rev.update_traces(
                    textinfo="percent+label",
                    textfont=dict(size=13, color="white"),
                    marker=dict(line=dict(color=_PAPER_BG, width=4)),
                    pull=[0.05] * len(df_rev),
                    rotation=45,
                )
                fig_rev.update_layout(
                    _base_layout(
                        title=dict(
                            text="Revenue Share by Plan",
                            font=dict(size=15, color=_FONT_COLOR),
                        ),
                        legend=dict(
                            orientation="h", yanchor="bottom",
                            y=-0.22, xanchor="center", x=0.5,
                            font=dict(color=_FONT_COLOR, size=12),
                        ),
                        height=400,
                    )
                )
                st.plotly_chart(fig_rev, use_container_width=True)

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 5 — USER ENGAGEMENT & ACTIVITY
        # Avg session card: purple border
        # Peak hours bar: indigo→purple→cyan gradient
        # ════════════════════════════════════════════════════════
        st.subheader("⏱️ Section 5 — User Engagement & Activity")

        avg_mins = admin_sys.get_avg_session_duration()
        avg_mins_rounded = round(avg_mins, 2) if avg_mins else 0

        ea1, ea2 = st.columns([1, 3])
        with ea1:
            st.markdown(
                f"""
                <div style="
                    background: #1C1C1C;
                    border: 2px solid #4F8EF7;
                    border-radius: 12px;
                    padding: 32px 20px;
                    text-align: center;
                    margin-top: 10px;
                ">
                    <div style="color:#AAAAAA;font-size:13px;margin-bottom:8px;">
                        ⏱️ Avg Session Duration
                    </div>
                    <div style="color:#4F8EF7;font-size:52px;font-weight:bold;line-height:1;">
                        {avg_mins_rounded}
                    </div>
                    <div style="color:#888888;font-size:13px;margin-top:8px;">
                        minutes per session
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with ea2:
            st.markdown("📊 **Login Activity by Hour (Full Day)**")
            df_hours = admin_sys.get_peak_hours()
            if not df_hours.empty:
                def format_hour_ampm(h):
                    if h == 0:    return "12 AM"
                    elif h < 12:  return f"{int(h)} AM"
                    elif h == 12: return "12 PM"
                    else:         return f"{int(h) - 12} PM"
                df_hours["time_slot"] = df_hours["login_hour"].apply(format_hour_ampm)
                fig_peak = px.bar(
                    df_hours, x="time_slot", y="count",
                    text="count",
                    color="count",
                    color_continuous_scale=[
                        [0.0, "#1a2e4a"],
                        [1.0, _BLUE],
                    ],
                    labels={"count": "Logins", "time_slot": "Hour"},
                )
                fig_peak.update_traces(
                    texttemplate="%{text}",
                    textposition="outside",
                    textfont=dict(color=_FONT_COLOR, size=10),
                    marker_line_width=0,
                )
                fig_peak.update_layout(
                    _base_layout(
                        title=dict(
                            text="Login Activity — All Hours of the Day",
                            font=dict(size=15, color=_FONT_COLOR),
                        ),
                        coloraxis_showscale=False,
                        xaxis=dict(
                            showgrid=False,
                            tickfont=dict(color=_FONT_COLOR, size=10),
                            tickangle=-45,
                        ),
                        yaxis=dict(
                            showgrid=True, gridcolor=_GRID_COLOR,
                            tickfont=dict(color=_FONT_COLOR),
                        ),
                        height=380,
                    )
                )
                st.plotly_chart(fig_peak, use_container_width=True)
            else:
                st.info("No activity data yet.")

        st.divider()

        # ════════════════════════════════════════════════════════
        # SECTION 6 — CUSTOMER LIFETIME VALUE  (styled full-width table)
        # ════════════════════════════════════════════════════════
        st.subheader("🐋 Section 6 — Customer Lifetime Value (CLV)")
        st.caption("Top 10 most valuable users ranked by total spend per active day.")

        df_clv = admin_sys.get_customer_lifetime_value()
        if not df_clv.empty:
            df_clv_sorted = df_clv.sort_values(by="clv", ascending=False).head(10)
            df_display = df_clv_sorted[["fullname", "total_spend", "days_active", "clv"]].copy()
            df_display.columns = ["👤 User Name", "💰 Total Spend (₹)", "📅 Days Active", "⭐ CLV (₹/Day)"]
            df_display["💰 Total Spend (₹)"] = df_display["💰 Total Spend (₹)"].apply(
                lambda x: f"₹{float(x):,.2f}"
            )
            df_display["⭐ CLV (₹/Day)"] = df_display["⭐ CLV (₹/Day)"].apply(
                lambda x: f"₹{float(x):.2f}"
            )
            df_display.index = range(1, len(df_display) + 1)
            st.dataframe(
                df_display,
                use_container_width=True,
                height=min(420, 42 * (len(df_display) + 1)),
            )
        else:
            st.info("No CLV data available yet.")

    elif st.session_state['admin_view'] == 'Feedback':
        st.title("📬 User Requests & Feedback")
        st.info("View and manage requests submitted by users regarding new movies or shows.")

        df_feedback = admin_sys.get_all_feedback()

        if not df_feedback.empty:
            # ── Summary metrics ──────────────────────────────────
            total_fb = len(df_feedback)
            today_fb = len(df_feedback[
                pd.to_datetime(df_feedback['created_at']).dt.date == pd.Timestamp.now().date()
            ])
            f1, f2 = st.columns(2)
            f1.metric("📬 Total Feedback", total_fb)
            f2.metric("📅 Received Today",  today_fb)

            st.divider()

            # ── Search filter ────────────────────────────────────
            search_fb = st.text_input("🔍 Search by user name, email or keyword")
            if search_fb.strip():
                mask = (
                    df_feedback['fullname'].str.contains(search_fb, case=False, na=False) |
                    df_feedback['email'].str.contains(search_fb, case=False, na=False) |
                    df_feedback['request_content'].str.contains(search_fb, case=False, na=False)
                )
                df_feedback = df_feedback[mask]
                st.caption(f"Showing **{len(df_feedback)}** results for '{search_fb}'")

            df_show = df_feedback.rename(columns={
                "fullname":        "User Name",
                "email":           "User Email",
                "request_content": "Request",
                "created_at":      "Submitted Date"
            })
            st.dataframe(df_show[["id","User Name","User Email","Request","Submitted Date"]],
                         use_container_width=True)

            # ── Delete feedback ──────────────────────────────────
            st.divider()
            st.subheader("🗑️ Delete a Feedback Entry")
            del_id = st.number_input("Enter Feedback ID to delete", min_value=1, step=1)
            if st.button("🗑️ Delete Feedback", type="primary"):
                try:
                    db.cursor.execute("DELETE FROM feedback WHERE id = %s", (int(del_id),))
                    db.conn.commit()
                    st.success(f"Feedback ID {del_id} deleted successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not delete: {e}")
        else:
            st.success("✅ No user feedback found yet.")

    elif st.session_state['admin_view'] == 'Manage':
        st.title("👥 User Management")
        st.info("Search, filter and manage user accounts.")

        df_users = admin_sys.get_all_data("users")

        # ── Filters row ──────────────────────────────────────
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        with fc1:
            search_email = st.text_input("🔍 Search by name or email")
        with fc2:
            role_filter = st.selectbox("Filter by Role", ["All", "USER", "ADMIN", "SUSPENDED"])
        with fc3:
            st.write("")  # spacer

        # Apply filters
        if search_email.strip():
            df_users = df_users[
                df_users['email'].str.contains(search_email, case=False, na=False) |
                df_users['fullname'].str.contains(search_email, case=False, na=False)
            ]
        if role_filter != "All":
            df_users = df_users[df_users['role'] == role_filter]

        # ── Hide sensitive columns ───────────────────────────
        display_cols = [c for c in df_users.columns if c not in ('password', 'profile_pic_url')]
        st.caption(f"Showing **{len(df_users)}** users")
        st.dataframe(df_users[display_cols], use_container_width=True)

        st.divider()
        st.subheader("🛠️ Perform Action on User")

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            target_id = st.number_input("Enter User ID to Act On", min_value=1, step=1)
        with c2:
            action = st.selectbox("Select Action", ["Choose...", "Suspend", "Activate", "Delete"])
        with c3:
            st.write("")
            if action == "Suspend":
                if st.button("⛔ Suspend User", type="primary"):
                    if user_sys.change_user_status(target_id, "SUSPENDED"):
                        st.success("User Suspended!")
                        st.rerun()
                    else:
                        st.error("Failed to suspend.")

            elif action == "Activate":
                if st.button("✅ Activate User", type="primary"):
                    if user_sys.change_user_status(target_id, "USER"):
                        st.success("User Activated!")
                        st.rerun()
                    else:
                        st.error("Failed to activate.")

            elif action == "Delete":
                st.warning("⚠️ This is permanent and cannot be undone!")
                confirm = st.checkbox(f"I confirm I want to permanently delete User ID {int(target_id)}")
                if confirm:
                    if st.button("🗑️ Confirm Delete", type="primary"):
                        if user_sys.delete_user(target_id):
                            st.warning("User Deleted Successfully.")
                            st.rerun()
                        else:
                            st.error("Failed to delete. User may have active subscriptions linked.")

        if df_users.empty:
            st.warning("No users found matching your filters.")

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
                fig_bar = px.bar(
                    df_new_vs_renewal,
                    x='payment_type', y='total_revenue',
                    color='payment_type',
                    color_discrete_map={'NEW': '#4F8EF7', 'RENEWAL': '#27AE60'},
                    title="Total Revenue: NEW vs RENEWAL",
                    labels={'payment_type': 'Payment Type', 'total_revenue': 'Revenue (₹)'},
                    text='total_revenue'
                )
                fig_bar.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside',
                                      marker_line_width=0)
                fig_bar.update_layout(
                    showlegend=False,
                    paper_bgcolor="#252525", plot_bgcolor="#1C1C1C",
                    font=dict(color="#F0F0F0"),
                    xaxis=dict(showgrid=False, tickfont=dict(color="#F0F0F0", size=13)),
                    yaxis=dict(showgrid=True, gridcolor="#333333",
                               tickprefix="₹", tickfont=dict(color="#F0F0F0")),
                    margin=dict(l=40, r=40, t=50, b=40), height=380,
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with col2:
                fig_pie = px.pie(
                    df_new_vs_renewal,
                    names='payment_type', values='total_revenue',
                    hole=0.5,
                    title="Revenue Split (%)",
                    color='payment_type',
                    color_discrete_map={'NEW': '#4F8EF7', 'RENEWAL': '#27AE60'}
                )
                fig_pie.update_traces(
                    textinfo='percent+label',
                    textfont=dict(color='white', size=13),
                    marker=dict(line=dict(color='#252525', width=3)),
                )
                fig_pie.update_layout(
                    paper_bgcolor="#252525", plot_bgcolor="#252525",
                    font=dict(color="#F0F0F0"),
                    legend=dict(font=dict(color="#F0F0F0"), bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=20, r=20, t=50, b=20), height=380,
                )
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
                title="Monthly Revenue Trend — NEW vs RENEWAL",
                labels={'month': '', 'total_revenue': 'Revenue (₹)', 'payment_type': 'Type'},
                color_discrete_map={'NEW': '#4F8EF7', 'RENEWAL': '#27AE60'}
            )
            # Thicker lines, bigger markers, white border on dots
            fig_line.update_traces(
                line=dict(width=3),
                marker=dict(size=10, line=dict(color="#1C1C1C", width=2)),
                selector=dict(mode='lines+markers')
            )
            # Add value labels on each data point
            for ptype, color in [('NEW', '#4F8EF7'), ('RENEWAL', '#27AE60')]:
                df_sub = df_monthly_trend[df_monthly_trend['payment_type'] == ptype]
                for _, row in df_sub.iterrows():
                    fig_line.add_annotation(
                        x=row['month'], y=row['total_revenue'],
                        text=f"₹{int(row['total_revenue']):,}",
                        showarrow=False,
                        font=dict(size=10, color=color),
                        yshift=16,
                    )
            fig_line.update_layout(
                paper_bgcolor="#252525",
                plot_bgcolor="#1C1C1C",
                font=dict(color="#F0F0F0", family="Arial, sans-serif"),
                hovermode='x unified',
                legend=dict(
                    title="",
                    orientation="h",
                    yanchor="bottom", y=1.02,
                    xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#F0F0F0", size=13),
                ),
                xaxis=dict(
                    showgrid=False,
                    tickfont=dict(color="#F0F0F0", size=12),
                    linecolor="#333333",
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#333333",
                    tickprefix="₹",
                    tickfont=dict(color="#F0F0F0"),
                    zeroline=False,
                ),
                margin=dict(l=50, r=50, t=60, b=40),
                height=420,
            )
            st.plotly_chart(fig_line, use_container_width=True)
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
            Renewal Rate = (Renewal Transactions / Total Transactions) × 100
            ```
            A renewal transaction = a user who paid again after their plan expired.
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

            c1, c2 = st.columns(2)

            with c1:
                st.markdown("🥧 **At-Risk Users by Risk Level**")
                risk_counts = df_risk['Risk Level'].value_counts().reset_index()
                risk_counts.columns = ['Risk Level', 'Count']
                color_map = {
                    "🔴 Critical": "#E74C3C",
                    "🟠 High":     "#E67E22",
                    "🟡 Medium":   "#F1C40F"
                }
                fig_risk_pie = px.pie(
                    risk_counts, names='Risk Level', values='Count',
                    hole=0.45, title="Risk Distribution",
                    color='Risk Level', color_discrete_map=color_map
                )
                fig_risk_pie.update_traces(
                    textinfo='percent+label',
                    textfont=dict(color='white', size=13),
                    marker=dict(line=dict(color='#252525', width=3)),
                )
                fig_risk_pie.update_layout(
                    paper_bgcolor="#252525", plot_bgcolor="#252525",
                    font=dict(color="#F0F0F0"),
                    legend=dict(font=dict(color="#F0F0F0"), bgcolor="rgba(0,0,0,0)"),
                    title_font=dict(color="#F0F0F0", size=15),
                    margin=dict(l=20, r=20, t=50, b=20), height=380,
                )
                st.plotly_chart(fig_risk_pie, use_container_width=True)

            with c2:
                st.markdown("📊 **Revenue at Risk by Plan**")
                df_plan_risk = df_risk.groupby('plan_name')['amount'].sum().reset_index()
                df_plan_risk.columns = ['Plan', 'Revenue at Risk']
                _PLAN_RISK_COLORS = {"Mobile": "#4F8EF7", "Standard": "#1E5DC9", "Premium": "#8AB4F8"}
                fig_plan_risk = px.bar(
                    df_plan_risk, x='Plan', y='Revenue at Risk',
                    color='Plan', title="Revenue at Risk by Plan",
                    color_discrete_map=_PLAN_RISK_COLORS,
                    text='Revenue at Risk'
                )
                fig_plan_risk.update_traces(
                    texttemplate='₹%{text:,.0f}', textposition='outside',
                    marker_line_width=0,
                )
                fig_plan_risk.update_layout(
                    showlegend=False,
                    paper_bgcolor="#252525", plot_bgcolor="#1C1C1C",
                    font=dict(color="#F0F0F0"),
                    title_font=dict(color="#F0F0F0", size=15),
                    xaxis=dict(showgrid=False, tickfont=dict(color="#F0F0F0", size=13)),
                    yaxis=dict(showgrid=True, gridcolor="#333333",
                               tickprefix="₹", tickfont=dict(color="#F0F0F0")),
                    margin=dict(l=40, r=40, t=50, b=40), height=380,
                )
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

    # ═══════════════════════════════════════════════════════
    # ADMIN — REVENUE FORECAST
    # ═══════════════════════════════════════════════════════
    elif st.session_state['admin_view'] == 'Forecast':
        st.title("📈 Revenue Forecast")
        st.info("Predicted next month revenue based on active subscriptions, renewal rate and new user trends.")

        forecast = admin_sys.get_revenue_forecast()

        # ── ROW 1: KEY METRIC CARDS ──────────────────────────
        st.subheader("📊 Forecast Inputs")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("👥 Active Subscribers",  forecast['active_count'])
        m2.metric("💰 Avg Plan Price",       f"₹{forecast['avg_price']}")
        m3.metric("🔄 Renewal Rate",         f"{forecast['renewal_rate']}%")
        m4.metric("🆕 Avg New Users/Month",  forecast['avg_new_per_month'])

        st.divider()

        # ── ROW 2: BIG FORECAST NUMBER ───────────────────────
        st.subheader("🎯 Next Month Forecast")
        fc1, fc2, fc3 = st.columns(3)

        fc1.markdown(f"""
        <div style="padding:25px;border-radius:12px;background:#1C1C1C;
                    border:2px solid #27AE60;text-align:center;color:white;">
            <p style="color:#aaa;font-size:14px;">🔄 From Renewals</p>
            <h2 style="color:#27AE60;">₹{forecast['renewal_revenue']:,.0f}</h2>
            <p style="color:#aaa;">{forecast['renewal_count']} users expected to renew</p>
        </div>
        """, unsafe_allow_html=True)

        fc2.markdown(f"""
        <div style="padding:25px;border-radius:12px;background:#1E5DC9;
                    border:2px solid #4F8EF7;text-align:center;color:white;">
            <p style="font-size:14px;opacity:0.9;">📈 TOTAL FORECAST</p>
            <h1>₹{forecast['total_forecast']:,.0f}</h1>
            <p style="opacity:0.9;">Next Month Prediction</p>
        </div>
        """, unsafe_allow_html=True)

        fc3.markdown(f"""
        <div style="padding:25px;border-radius:12px;background:#1C1C1C;
                    border:2px solid #4F8EF7;text-align:center;color:white;">
            <p style="color:#aaa;font-size:14px;">🆕 From New Users</p>
            <h2 style="color:#4F8EF7;">₹{forecast['new_user_revenue']:,.0f}</h2>
            <p style="color:#aaa;">{forecast['avg_new_per_month']} new users expected</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── ROW 3: BREAKDOWN BAR CHART ───────────────────────
        st.subheader("📊 Revenue Breakdown")
        df_fc = pd.DataFrame({
            'Source':  ['🔄 Renewals',              '🆕 New Users'],
            'Revenue': [forecast['renewal_revenue'], forecast['new_user_revenue']]
        })
        fig_fc = px.bar(
            df_fc, x='Source', y='Revenue',
            color='Source',
            color_discrete_map={'🔄 Renewals': '#27AE60', '🆕 New Users': '#4F8EF7'},
            title="Forecast Revenue by Source",
            labels={'Revenue': 'Predicted Revenue (₹)'},
            text='Revenue'
        )
        fig_fc.update_traces(
            texttemplate='₹%{text:,.0f}', textposition='outside',
            width=0.35, marker_line_width=0,
        )
        fig_fc.update_layout(
            showlegend=False,
            paper_bgcolor="#252525", plot_bgcolor="#1C1C1C",
            font=dict(color="#F0F0F0"),
            xaxis=dict(showgrid=False, tickfont=dict(size=14, color="#F0F0F0")),
            yaxis=dict(showgrid=True, gridcolor="#333333",
                       tickprefix="₹", tickfont=dict(color="#F0F0F0")),
            height=380, margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig_fc, use_container_width=True)

        st.divider()

        # ── ROW 4: CONFIDENCE METER ──────────────────────────
        st.subheader("🎯 Forecast Confidence")
        confidence = forecast['confidence']
        conf_color = "#27AE60" if confidence >= 70 else "#F1C40F" if confidence >= 50 else "#E74C3C"
        conf_label = "High ✅" if confidence >= 70 else "Medium ⚠️" if confidence >= 50 else "Low ❌"

        st.progress(confidence / 100, text=f"Confidence Level: {confidence}% — {conf_label}")

        st.markdown(f"""
        <div style="padding:20px;border-radius:10px;background:#1C1C1C;
                    border:1px solid #333333;color:white;margin-top:10px;">
            <h4 style="color:{conf_color};">Why {confidence}% Confidence?</h4>
            <p style="color:#aaa;">The forecast is based on your real database data:</p>
            <ul style="color:#ccc;">
                <li>✅ Active subscriber count: <b>{forecast['active_count']} users</b></li>
                <li>✅ Renewal rate from payment history: <b>{forecast['renewal_rate']}%</b></li>
                <li>✅ New user trend from last 3 months: <b>{forecast['avg_new_per_month']} avg/month</b></li>
                <li>⚠️ Assumes plan prices stay same next month</li>
                <li>⚠️ Assumes renewal rate stays consistent</li>
            </ul>
            <p style="color:#888;font-size:12px;">Confidence increases as more payment history is recorded.</p>
        </div>
        """, unsafe_allow_html=True)

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

        # ── Shared theme (matches rest of admin dashboard) ────
        _CL_BG      = "#1C1C1C"
        _CL_PAPER   = "#252525"
        _CL_FONT    = "#F0F0F0"
        _CL_GRID    = "#333333"
        _CL_BLUE    = "#4F8EF7"
        _CL_GREEN   = "#27AE60"

        _cl_layout = dict(
            paper_bgcolor=_CL_PAPER,
            plot_bgcolor=_CL_BG,
            font=dict(color=_CL_FONT),
            title_font=dict(color=_CL_FONT, size=15),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=_CL_FONT)),
            margin=dict(l=10, r=10, t=40, b=10),
        )

        with g1:
            st.subheader("🎭 Top 15 Genres")
            df_genres = content_mgr.get_genre_distribution()
            if not df_genres.empty:
                fig_genre = px.bar(
                    df_genres, x='count', y='genre',
                    orientation='h',
                    title="Most Common Genres",
                    color='count',
                    color_continuous_scale=[[0.0, "#1a3a6b"], [1.0, _CL_BLUE]],
                    labels={'count': 'Number of Titles', 'genre': 'Genre'}
                )
                fig_genre.update_layout(
                    **_cl_layout,
                    yaxis=dict(categoryorder='total ascending', gridcolor=_CL_GRID, color=_CL_FONT),
                    xaxis=dict(gridcolor=_CL_GRID, color=_CL_FONT),
                    coloraxis_showscale=False,
                )
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
                fig_year.update_traces(
                    line=dict(color=_CL_BLUE, width=3),
                    marker=dict(size=8, color=_CL_BLUE, line=dict(color=_CL_PAPER, width=2)),
                    fill='tozeroy',
                    fillcolor="rgba(79,142,247,0.12)",
                )
                fig_year.update_layout(
                    **_cl_layout,
                    xaxis=dict(gridcolor=_CL_GRID, color=_CL_FONT),
                    yaxis=dict(gridcolor=_CL_GRID, color=_CL_FONT),
                )
                st.plotly_chart(fig_year, use_container_width=True)

        st.divider()

        # ── Movie vs TV Show split ────────────────────────────
        st.subheader("🎞️ Movie vs TV Show Split")
        split_data = pd.DataFrame({'Type': ['Movie', 'TV Show'], 'Count': [movies, shows]})
        fig_split = px.pie(split_data, names='Type', values='Count',
                           hole=0.5,
                           color='Type',
                           color_discrete_map={'Movie': _CL_BLUE, 'TV Show': _CL_GREEN},
                           title="Content Type Distribution")
        fig_split.update_traces(marker=dict(line=dict(color=_CL_PAPER, width=3)))
        fig_split.update_layout(**_cl_layout)
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
    # ═══════════════════════════════════════════════════════
    # ADMIN — MUTUAL CONNECTIONS PANEL
    # ═══════════════════════════════════════════════════════
    elif st.session_state['admin_view'] == 'MutualConn':
        st.title("🤝 Mutual Connection Manager")
        st.info("Find users who are paying but barely watching, group them together, and send in-app invites to share a plan at a reduced cost.")

        tab_find, tab_send, tab_groups = st.tabs([
            "🔍 Find Low-Usage Users",
            "📩 Send Invites",
            "📊 All Groups"
        ])

        # ── TAB 1: Find Low-Usage Users ──────────────────────────
        with tab_find:
            st.subheader("🔍 Low-Usage Paid Subscribers")
            st.caption("These users have an active paid plan but low watch time this month — ideal candidates for plan sharing.")

            threshold = st.slider(
                "Watch time threshold (minutes/month)",
                min_value=0, max_value=300, value=60, step=10,
                help="Users watching LESS than this will be flagged."
            )

            df_low = mutual_mgr.get_low_usage_users(threshold)

            if df_low.empty:
                st.success(f"✅ No users below {threshold} mins. All subscribers are actively watching!")
            else:
                st.warning(f"⚠️ Found **{len(df_low)} users** watching less than {threshold} mins this month.")

                m1, m2, m3 = st.columns(3)
                m1.metric("👥 Low-Usage Users",   len(df_low))
                m2.metric("💸 Wasted Revenue",
                          f"₹{df_low['plan_price'].sum():,.0f}",
                          delta="potential savings if shared")
                m3.metric("📊 Avg Watch Time",
                          f"{df_low['watch_mins_this_month'].mean():.0f} mins")

                st.divider()

                # Colour-coded table
                def colour_watch(val):
                    if val == 0:
                        return 'background-color:#4a0000;color:white'
                    elif val < 30:
                        return 'background-color:#3d1a00;color:white'
                    return 'background-color:#1a2d00;color:white'

                display_df = df_low[['fullname','email','country','plan_name',
                                     'plan_price','watch_mins_this_month']].copy()
                display_df.columns = ['Name','Email','Country','Plan','Price (₹)','Watch Mins']

                st.dataframe(
                    display_df.style.applymap(colour_watch, subset=['Watch Mins']),
                    use_container_width=True
                )

        # ── TAB 2: Send Invites ──────────────────────────────────
        with tab_send:
            st.subheader("📩 Create a Group & Send In-App Invites")
            st.caption("Select users, choose a plan, write a message — users will see it in their 🔔 Notifications.")

            # Fetch low-usage users for selection
            df_candidates = mutual_mgr.get_low_usage_users(threshold_mins=300)

            if df_candidates.empty:
                st.info("No active subscribers found to invite.")
            else:
                # Build email→user_id map
                email_to_uid = dict(zip(df_candidates['email'], df_candidates['user_id']))
                email_options = df_candidates['email'].tolist()

                selected_emails = st.multiselect(
                    "Select users to invite (minimum 2)",
                    options=email_options,
                    help="Select 2–4 users who will share the plan."
                )

                col1, col2 = st.columns(2)
                with col1:
                    invite_plan = st.selectbox("Plan to Share", ["Mobile", "Standard", "Premium"])
                with col2:
                    if selected_emails:
                        n = len(selected_emails)
                        prices = {"Mobile": 149, "Standard": 499, "Premium": 649}
                        split = round(prices[invite_plan] / n, 2)
                        st.metric(
                            "Split Price Per User",
                            f"₹{split:.2f}/month",
                            delta=f"₹{prices[invite_plan]} ÷ {n} users"
                        )

                admin_msg = st.text_area(
                    "Message to users",
                    placeholder="e.g. Hi! We noticed you haven't been watching much this month. "
                                "Would you like to share a plan with others and save money?",
                    height=100
                )

                if st.button("📩 Send Invites to Selected Users", type="primary",
                             use_container_width=True):
                    if len(selected_emails) < 2:
                        st.error("Please select at least 2 users.")
                    elif not admin_msg.strip():
                        st.error("Please write a message for the users.")
                    else:
                        user_ids = [int(email_to_uid[e]) for e in selected_emails]
                        ok, msg, gid = mutual_mgr.create_group_and_invite(
                            user_ids, invite_plan, admin_msg.strip()
                        )
                        if ok:
                            st.success(f"✅ {msg}")
                            st.balloons()
                        else:
                            st.error(f"❌ {msg}")

        # ── TAB 3: All Groups Overview ───────────────────────────
        with tab_groups:
            st.subheader("📊 All Mutual Connection Groups")

            df_groups = mutual_mgr.get_all_groups()

            if df_groups.empty:
                st.info("No groups created yet. Use the 'Send Invites' tab to create one.")
            else:
                # Summary metrics
                total_groups  = len(df_groups)
                active_groups = len(df_groups[df_groups['status'] == 'ACTIVE'])
                forming       = len(df_groups[df_groups['status'] == 'FORMING'])

                g1, g2, g3 = st.columns(3)
                g1.metric("📦 Total Groups",   total_groups)
                g2.metric("✅ Active Groups",   active_groups)
                g3.metric("⏳ Forming Groups",  forming)

                st.divider()

                for _, grp in df_groups.iterrows():
                    status_color = {"ACTIVE": "#00ff88", "FORMING": "#ff9900"}.get(grp['status'], "#888")
                    status_icon  = {"ACTIVE": "✅", "FORMING": "⏳"}.get(grp['status'], "❓")

                    with st.expander(
                        f"{status_icon} Group #{grp['group_id']} — Netflix {grp['plan_name']} "
                        f"| ₹{float(grp['split_price']):,.2f}/user | {grp['status']}"
                    ):
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("📦 Plan",        grp['plan_name'])
                        c2.metric("💰 Full Price",   f"₹{float(grp['full_price']):,.0f}")
                        c3.metric("✂️ Split Price",  f"₹{float(grp['split_price']):,.2f}")
                        c4.metric("👥 Max Members",  int(grp['max_members']))

                        st.markdown(f"""
                        <div style="display:flex;gap:16px;margin:8px 0;">
                            <span style="background:#1a3a1a;color:#00ff88;padding:4px 10px;border-radius:6px;">
                                ✅ Accepted: {int(grp['accepted'])}
                            </span>
                            <span style="background:#3a2a1a;color:#ff9900;padding:4px 10px;border-radius:6px;">
                                ⏳ Pending: {int(grp['pending'])}
                            </span>
                            <span style="background:#3a1a1a;color:#ff4444;padding:4px 10px;border-radius:6px;">
                                ❌ Declined: {int(grp['declined'])}
                            </span>
                            <span style="color:{status_color};font-weight:bold;padding:4px 0;">
                                Status: {grp['status']}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)

                        # Show member details
                        members = mutual_mgr.get_group_members(int(grp['group_id']))
                        if not members.empty:
                            st.markdown("**👥 Members:**")
                            for _, m in members.iterrows():
                                m_color = "#00ff88" if m['invite_status'] == 'ACCEPTED' else \
                                          "#ff9900" if m['invite_status'] == 'PENDING' else "#ff4444"
                                st.markdown(f"""
                                <div style="padding:8px 12px;background:#111;border-radius:6px;
                                            border-left:3px solid {m_color};margin-bottom:6px;">
                                    <b style="color:white;">{m['fullname']}</b>
                                    <span style="color:#888;font-size:12px;"> — {m['email']}
                                    &nbsp;|&nbsp; {m['country']}</span>
                                    &nbsp;
                                    <span style="color:{m_color};font-size:12px;font-weight:bold;">
                                        {m['invite_status']}
                                    </span>
                                </div>
                                """, unsafe_allow_html=True)