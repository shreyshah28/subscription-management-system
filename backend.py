import pandas as pd
import hashlib
from datetime import datetime, timedelta
from database import DB

db = DB()

class UserModule:
    def register(self, name, email, password, mobile, age, country):
        # 1. Basic Empty Checks
        if not all([name, email, password, mobile, country]):
            return False, "All fields are required!"

        # 2. Email Validation (@gmail.com requirement)
        if not email.endswith("@gmail.com"):
            return False, "Only @gmail.com addresses are allowed."
        
        # 3. Mobile Number Validation (Exactly 10 digits)
        if not (mobile.isdigit() and len(mobile) == 10):
            return False, "Mobile number must be exactly 10 digits."

        # 4. Age Validation
        if int(age) <= 0 or int(age) > 120:
            return False, "Please enter a valid age (1-120)."

        # 5. Password Length
        if len(password) < 6:
            return False, "Password must be at least 6 characters long."

        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            db.cursor.execute(
                "INSERT INTO users (fullname, email, password, mobile, age, country) VALUES (%s, %s, %s, %s, %s, %s)", 
                (name, email, hashed_pw, mobile, age, country)
            )
            db.conn.commit()
            return True, "Registration Successful"
        except Exception: 
            return False, "This email is already registered."

    def login(self, email, password):
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        db.cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, hashed_pw))
        return db.cursor.fetchone()

    def submit_feedback(self, user_id, content):
        """Stores user movie/show requests"""
        try:
            db.cursor.execute("INSERT INTO feedback (user_id, request_content) VALUES (%s, %s)", (user_id, content))
            db.conn.commit()
            return True
        except:
            return False

    def get_user_analytics(self, user_id):
        """Returns personal analytics: Spend and Watch Time"""
        # Total Spend
        query_spend = "SELECT COALESCE(SUM(amount), 0) FROM subscriptions WHERE user_id=%s"
        db.cursor.execute(query_spend, (user_id,))
        total_spend = db.cursor.fetchone()[0]

        # Total Watch Time
        query_time = "SELECT COALESCE(SUM(session_minutes), 0) FROM user_activity WHERE user_id=%s"
        db.cursor.execute(query_time, (user_id,))
        total_mins = db.cursor.fetchone()[0]

        return total_spend, total_mins

    def get_user_dashboard(self, user_id):
        """Returns all data needed for the user dashboard home page"""
        from datetime import datetime

        # 1. Active Plan Info
        db.cursor.execute("""
            SELECT plan_name, amount, start_date, end_date, status, auto_renewal
            FROM subscriptions
            WHERE user_id = %s AND status = 'ACTIVE'
            ORDER BY start_date DESC LIMIT 1
        """, (user_id,))
        plan_row = db.cursor.fetchone()

        plan_name = None
        plan_amount = 0
        days_left = 0
        days_used = 0
        total_days = 30
        end_date_str = "N/A"
        sub_status = "NO PLAN"
        auto_renewal = False

        if plan_row:
            plan_name = plan_row[0]
            plan_amount = float(plan_row[1])
            start_date = plan_row[2]
            end_date = plan_row[3]
            sub_status = plan_row[4]
            auto_renewal = plan_row[5] if plan_row[5] is not None else False

            # Calculate days remaining
            now = datetime.now()
            days_left = max(0, (end_date - now).days)
            days_used = max(0, (now - start_date).days)
            total_days = max(1, (end_date - start_date).days)
            end_date_str = end_date.strftime("%d %b %Y")

        # 2. Total Money Spent
        db.cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM subscriptions WHERE user_id = %s", (user_id,)
        )
        total_spend = float(db.cursor.fetchone()[0])

        # 3. Total Watch Time (SUM of all session_minutes)
        db.cursor.execute(
            "SELECT COALESCE(SUM(session_minutes), 0) FROM user_activity WHERE user_id = %s", (user_id,)
        )
        total_watch = int(db.cursor.fetchone()[0])

        # 4. Total number of subscriptions ever
        db.cursor.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE user_id = %s", (user_id,)
        )
        total_subs = int(db.cursor.fetchone()[0])

        # 5. Last login time
        db.cursor.execute("""
            SELECT login_time FROM user_activity
            WHERE user_id = %s
            ORDER BY login_time DESC LIMIT 1
        """, (user_id,))
        last_login_row = db.cursor.fetchone()
        last_login = last_login_row[0].strftime("%d %b %Y, %I:%M %p") if last_login_row else "First Login"

        return {
            "plan_name": plan_name,
            "plan_amount": plan_amount,
            "days_left": days_left,
            "days_used": days_used,
            "total_days": total_days,
            "end_date_str": end_date_str,
            "sub_status": sub_status,
            "auto_renewal": auto_renewal,
            "total_spend": total_spend,
            "total_watch": total_watch,
            "total_subs": total_subs,
            "last_login": last_login
        }
    def change_user_status(self, user_id, new_status):
        """Changes user role (e.g., to SUSPENDED)"""
        try:
            db.cursor.execute(
                "UPDATE users SET role = %s WHERE user_id = %s",
                (new_status, user_id)
            )
            db.conn.commit()
            return True
        except Exception as e:
            print(f"Error changing user status: {e}")
            return False

    def delete_user(self, user_id):
        """Deletes a user from the database"""
        try:
            db.cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            db.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    def get_profile(self, user_id):
        """Fetch current profile data for a user"""
        db.cursor.execute("""
            SELECT fullname, email, mobile, age, country, gender, dob, favorite_genre
            FROM users WHERE user_id = %s
        """, (user_id,))
        row = db.cursor.fetchone()
        if not row:
            return None
        return {
            "fullname":       row[0] or "",
            "email":          row[1] or "",
            "mobile":         row[2] or "",
            "age":            row[3] or 0,
            "country":        row[4] or "",
            "gender":         row[5] or "",
            "dob":            row[6],
            "favorite_genre": row[7] or ""
        }

    def update_profile(self, user_id, fullname, mobile, country, gender, dob, favorite_genre):
        """Update user profile fields"""
        # Validation
        if not fullname or not fullname.strip():
            return False, "Full name cannot be empty."
        if mobile and (not mobile.isdigit() or len(mobile) != 10):
            return False, "Mobile must be exactly 10 digits."
        try:
            db.cursor.execute("""
                UPDATE users
                SET fullname = %s, mobile = %s, country = %s,
                    gender = %s, dob = %s, favorite_genre = %s
                WHERE user_id = %s
            """, (fullname.strip(), mobile, country, gender, dob, favorite_genre, user_id))
            db.conn.commit()
            return True, "Profile updated successfully!"
        except Exception as e:
            print(f"Profile update error: {e}")
            return False, "Could not update profile. Please try again."

class SubscriptionManager:
    def buy_plan(self, user_id, plan_name, amount, service_type, auto_renewal=False):
        start = datetime.now()
        end = start + timedelta(days=30)
        db.cursor.execute(
            "INSERT INTO subscriptions (user_id, plan_name, amount, start_date, end_date, service_type, auto_renewal) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING subscription_id",
            (user_id, plan_name, amount, start, end, service_type, auto_renewal)
        )
        sub_id = db.cursor.fetchone()[0]
        db.cursor.execute(
            "INSERT INTO payments (user_id, subscription_id, plan_name, amount, payment_type, payment_status) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, sub_id, plan_name, amount, 'NEW', 'SUCCESS')
        )
        db.conn.commit()
        # Fetch user info for PDF
        db.cursor.execute("SELECT fullname, email FROM users WHERE user_id=%s", (user_id,))
        urow = db.cursor.fetchone()
        uname  = urow[0] if urow else "User"
        uemail = urow[1] if urow else ""
        txt = self.generate_ott_invoice(user_id, service_type, plan_name, amount, start.strftime("%Y-%m-%d"))
        pdf = self.generate_pdf_invoice(user_id, uname, uemail, service_type, plan_name, amount, start.strftime("%d %b %Y"), "NEW")
        return txt, pdf

    def renew_subscription(self, user_id):
        """Renews an expired subscription for the user"""
        try:
            # Get the last expired subscription
            db.cursor.execute("""
                SELECT subscription_id, plan_name, amount, service_type, auto_renewal
                FROM subscriptions
                WHERE user_id = %s AND status IN ('EXPIRED', 'CANCELLED')
                ORDER BY end_date DESC
                LIMIT 1
            """, (user_id,))
            result = db.cursor.fetchone()
            if not result:
                return False, "No expired subscription found to renew."

            sub_id, plan_name, amount, service_type, auto_renewal = result
            start = datetime.now()
            end = start + timedelta(days=30)

            # Insert new subscription row
            db.cursor.execute("""
                INSERT INTO subscriptions (user_id, plan_name, amount, start_date, end_date, service_type, status, auto_renewal)
                VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE', %s) RETURNING subscription_id
            """, (user_id, plan_name, amount, start, end, service_type, auto_renewal))
            new_sub_id = db.cursor.fetchone()[0]

            # Record payment
            db.cursor.execute(
                "INSERT INTO payments (user_id, subscription_id, plan_name, amount, payment_type, payment_status) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, new_sub_id, plan_name, amount, 'RENEWAL', 'SUCCESS')
            )
            db.conn.commit()
            # Fetch user info for PDF
            db.cursor.execute("SELECT fullname, email FROM users WHERE user_id=%s", (user_id,))
            urow = db.cursor.fetchone()
            uname  = urow[0] if urow else "User"
            uemail = urow[1] if urow else ""
            txt = self.generate_ott_invoice(user_id, service_type, plan_name, amount, start.strftime("%Y-%m-%d"))
            pdf = self.generate_pdf_invoice(user_id, uname, uemail, service_type, plan_name, amount, start.strftime("%d %b %Y"), "RENEWAL")
            return True, txt, pdf
        except Exception as e:
            print(f"Renewal Error: {e}")
            return False, "Renewal failed. Please try again.", None

    def toggle_auto_renewal(self, user_id, enable: bool):
        """Enables or disables auto-renewal on the user's active subscription"""
        try:
            db.cursor.execute("""
                UPDATE subscriptions SET auto_renewal = %s
                WHERE user_id = %s AND status = 'ACTIVE'
            """, (enable, user_id))
            db.conn.commit()
            return True
        except Exception as e:
            print(f"Toggle Error: {e}")
            return False

    def get_expired_plan(self, user_id):
        """Fetches the most recent expired or cancelled subscription"""
        query = """
            SELECT * FROM subscriptions
            WHERE user_id = %s AND status IN ('EXPIRED', 'CANCELLED')
            ORDER BY end_date DESC
            LIMIT 1
        """
        df = pd.read_sql(query, db.conn, params=(user_id,))
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def get_payment_history(self, user_id):
        """Returns full payment history for a user"""
        query = """
            SELECT payment_id, plan_name, amount, payment_type, payment_status, payment_date
            FROM payments
            WHERE user_id = %s
            ORDER BY payment_date DESC
        """
        return pd.read_sql(query, db.conn, params=(user_id,))
    
    def regenerate_receipt(self, payment_id):
        """Regenerate PDF receipt for a specific payment ID — returns bytes."""
        try:
            db.cursor.execute("""
                SELECT p.user_id, p.plan_name, p.amount, p.payment_type,
                       p.payment_date, u.fullname, u.email
                FROM payments p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.payment_id = %s
            """, (payment_id,))
            result = db.cursor.fetchone()
            if not result:
                return None
            user_id, plan_name, amount, payment_type, payment_date, fullname, email = result
            date_str = payment_date.strftime("%d %b %Y") if hasattr(payment_date, 'strftime') else str(payment_date)
            return self.generate_pdf_invoice(
                user_id, fullname, email, "Netflix",
                plan_name, amount, date_str, payment_type
            )
        except Exception as e:
            print(f"Receipt regeneration error: {e}")
            return None

    def get_user_invoices(self, user_id):
        return pd.read_sql(f"SELECT service_type, plan_name, amount, start_date, end_date, status FROM subscriptions WHERE user_id={int(user_id)} ORDER BY start_date DESC", db.conn)

    def generate_ott_invoice(self, uid, service, plan, amt, date):
        """Kept for backward compatibility — returns simple text summary."""
        return f"Invoice | User: {uid} | Service: {service} | Plan: {plan} | Amount: Rs.{amt} | Date: {date}"

    def generate_pdf_invoice(self, uid, user_name, user_email, service, plan, amt, date, payment_type="NEW"):
        """
        Generates a professional PDF receipt using ReportLab.
        Returns bytes that can be directly downloaded via st.download_button.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            from io import BytesIO
            from datetime import timedelta

            # ── Fetch extra user details ──────────────────────────
            db.cursor.execute("SELECT mobile, country FROM users WHERE user_id=%s", (uid,))
            user_row = db.cursor.fetchone()
            mobile  = user_row[0] if user_row and user_row[0] else "N/A"
            country = user_row[1] if user_row and user_row[1] else "N/A"

            # ── Fetch payment ID ──────────────────────────────────
            db.cursor.execute("""
                SELECT payment_id FROM payments
                WHERE user_id = %s
                ORDER BY payment_date DESC LIMIT 1
            """, (uid,))
            pay_row    = db.cursor.fetchone()
            payment_id = pay_row[0] if pay_row else f"PAY{uid}{datetime.now().strftime('%Y%m%d%H%M')}"

            # ── Validity dates ────────────────────────────────────
            start_date = datetime.now()
            end_date   = start_date + timedelta(days=30)

            # ── PDF buffer ────────────────────────────────────────
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=A4,
                rightMargin=20*mm, leftMargin=20*mm,
                topMargin=20*mm,   bottomMargin=20*mm
            )

            # ── Styles ────────────────────────────────────────────
            styles = getSampleStyleSheet()

            NETFLIX_RED  = colors.HexColor("#E50914")
            DARK_BG      = colors.HexColor("#221F1F")
            LIGHT_GREY   = colors.HexColor("#F5F5F5")
            MID_GREY     = colors.HexColor("#888888")
            WHITE        = colors.white

            title_style = ParagraphStyle(
                "TitleStyle", parent=styles["Title"],
                fontSize=26, textColor=WHITE,
                alignment=TA_CENTER, spaceAfter=2
            )
            sub_title_style = ParagraphStyle(
                "SubTitle", parent=styles["Normal"],
                fontSize=11, textColor=MID_GREY,
                alignment=TA_CENTER, spaceAfter=4
            )
            section_style = ParagraphStyle(
                "Section", parent=styles["Normal"],
                fontSize=10, textColor=NETFLIX_RED,
                fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4
            )
            label_style = ParagraphStyle(
                "Label", parent=styles["Normal"],
                fontSize=9, textColor=MID_GREY,
                fontName="Helvetica"
            )
            value_style = ParagraphStyle(
                "Value", parent=styles["Normal"],
                fontSize=10, textColor=DARK_BG,
                fontName="Helvetica-Bold"
            )
            footer_style = ParagraphStyle(
                "Footer", parent=styles["Normal"],
                fontSize=8, textColor=MID_GREY,
                alignment=TA_CENTER
            )
            success_style = ParagraphStyle(
                "Success", parent=styles["Normal"],
                fontSize=13, textColor=colors.HexColor("#28a745"),
                fontName="Helvetica-Bold", alignment=TA_CENTER
            )

            # ── Story (content blocks) ────────────────────────────
            story = []

            # -- Header Banner (Netflix Red Box) --
            header_data = [[
                Paragraph("NETFLIX", title_style),
            ]]
            header_table = Table(header_data, colWidths=[170*mm])
            header_table.setStyle(TableStyle([
                ("BACKGROUND",  (0,0), (-1,-1), NETFLIX_RED),
                ("TOPPADDING",  (0,0), (-1,-1), 14),
                ("BOTTOMPADDING",(0,0),(-1,-1), 14),
                ("ALIGN",       (0,0), (-1,-1), "CENTER"),
                ("ROUNDEDCORNERS", [4]),
            ]))
            story.append(header_table)
            story.append(Spacer(1, 4*mm))
            story.append(Paragraph("OFFICIAL PAYMENT RECEIPT", sub_title_style))
            story.append(Spacer(1, 2*mm))

            # -- SUCCESS badge --
            badge_text = "PAYMENT SUCCESSFUL" if payment_type == "NEW" else "RENEWAL SUCCESSFUL"
            story.append(Paragraph(f"✓  {badge_text}", success_style))
            story.append(Spacer(1, 4*mm))
            story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GREY))
            story.append(Spacer(1, 4*mm))

            # -- Transaction Details Table --
            story.append(Paragraph("TRANSACTION DETAILS", section_style))
            txn_data = [
                ["Transaction ID",  str(payment_id),   "Payment Date",   date],
                ["Payment Type",    payment_type,       "Payment Status", "SUCCESS"],
            ]
            txn_table = Table(txn_data, colWidths=[40*mm, 55*mm, 40*mm, 35*mm])
            txn_table.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (0,-1), LIGHT_GREY),
                ("BACKGROUND",   (2,0), (2,-1), LIGHT_GREY),
                ("FONTNAME",     (0,0), (0,-1), "Helvetica-Bold"),
                ("FONTNAME",     (2,0), (2,-1), "Helvetica-Bold"),
                ("FONTSIZE",     (0,0), (-1,-1), 9),
                ("TEXTCOLOR",    (0,0), (0,-1), MID_GREY),
                ("TEXTCOLOR",    (2,0), (2,-1), MID_GREY),
                ("TEXTCOLOR",    (1,0), (1,-1), DARK_BG),
                ("TEXTCOLOR",    (3,0), (3,-1), colors.HexColor("#28a745")),
                ("FONTNAME",     (3,0), (3,-1), "Helvetica-Bold"),
                ("TOPPADDING",   (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                ("LEFTPADDING",  (0,0), (-1,-1), 8),
                ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#DDDDDD")),
                ("ROWBACKGROUNDS",(0,0),(-1,-1), [WHITE, LIGHT_GREY]),
            ]))
            story.append(txn_table)
            story.append(Spacer(1, 5*mm))

            # -- Customer Details Table --
            story.append(Paragraph("CUSTOMER DETAILS", section_style))
            cust_data = [
                ["Full Name",  user_name,   "Email",   user_email],
                ["Mobile",     mobile,       "Country", country],
            ]
            cust_table = Table(cust_data, colWidths=[35*mm, 60*mm, 30*mm, 45*mm])
            cust_table.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (0,-1), LIGHT_GREY),
                ("BACKGROUND",   (2,0), (2,-1), LIGHT_GREY),
                ("FONTNAME",     (0,0), (0,-1), "Helvetica-Bold"),
                ("FONTNAME",     (2,0), (2,-1), "Helvetica-Bold"),
                ("FONTSIZE",     (0,0), (-1,-1), 9),
                ("TEXTCOLOR",    (0,0), (0,-1), MID_GREY),
                ("TEXTCOLOR",    (2,0), (2,-1), MID_GREY),
                ("TEXTCOLOR",    (1,0), (1,-1), DARK_BG),
                ("TEXTCOLOR",    (3,0), (3,-1), DARK_BG),
                ("TOPPADDING",   (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                ("LEFTPADDING",  (0,0), (-1,-1), 8),
                ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#DDDDDD")),
                ("ROWBACKGROUNDS",(0,0),(-1,-1), [WHITE, LIGHT_GREY]),
            ]))
            story.append(cust_table)
            story.append(Spacer(1, 5*mm))

            # -- Subscription Details Box (highlighted) --
            story.append(Paragraph("SUBSCRIPTION DETAILS", section_style))
            plan_features = {
                "Mobile":   "480p | 1 Phone + 1 Tablet | Downloads",
                "Standard": "1080p HD | 2 Screens | Downloads",
                "Premium":  "4K + HDR | 4 Screens | Spatial Audio",
            }
            features = plan_features.get(plan, "Netflix Subscription")

            sub_data = [
                ["Service",      service,                    "Plan",     plan],
                ["Features",     features,                   "Duration", "30 Days"],
                ["Valid From",   start_date.strftime("%d %B %Y"), "Valid Until", end_date.strftime("%d %B %Y")],
            ]
            sub_table = Table(sub_data, colWidths=[35*mm, 60*mm, 30*mm, 45*mm])
            sub_table.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (0,-1), LIGHT_GREY),
                ("BACKGROUND",   (2,0), (2,-1), LIGHT_GREY),
                ("FONTNAME",     (0,0), (0,-1), "Helvetica-Bold"),
                ("FONTNAME",     (2,0), (2,-1), "Helvetica-Bold"),
                ("FONTSIZE",     (0,0), (-1,-1), 9),
                ("TEXTCOLOR",    (0,0), (0,-1), MID_GREY),
                ("TEXTCOLOR",    (2,0), (2,-1), MID_GREY),
                ("TEXTCOLOR",    (1,0), (1,-1), DARK_BG),
                ("TEXTCOLOR",    (3,0), (3,-1), DARK_BG),
                ("TOPPADDING",   (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                ("LEFTPADDING",  (0,0), (-1,-1), 8),
                ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#DDDDDD")),
                ("ROWBACKGROUNDS",(0,0),(-1,-1), [WHITE, LIGHT_GREY]),
            ]))
            story.append(sub_table)
            story.append(Spacer(1, 5*mm))

            # -- Amount Box (big red highlighted) --
            amount_data = [[
                Paragraph("AMOUNT PAID", ParagraphStyle(
                    "AmtLabel", parent=styles["Normal"],
                    fontSize=11, textColor=WHITE,
                    fontName="Helvetica-Bold", alignment=TA_CENTER
                )),
                Paragraph(f"Rs. {amt}", ParagraphStyle(
                    "AmtVal", parent=styles["Normal"],
                    fontSize=20, textColor=WHITE,
                    fontName="Helvetica-Bold", alignment=TA_CENTER
                )),
            ]]
            amt_table = Table(amount_data, colWidths=[85*mm, 85*mm])
            amt_table.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), NETFLIX_RED),
                ("TOPPADDING",   (0,0), (-1,-1), 10),
                ("BOTTOMPADDING",(0,0), (-1,-1), 10),
                ("ALIGN",        (0,0), (-1,-1), "CENTER"),
                ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ]))
            story.append(amt_table)
            story.append(Spacer(1, 6*mm))
            story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GREY))
            story.append(Spacer(1, 4*mm))

            # -- Footer --
            story.append(Paragraph(
                "Thank you for choosing Netflix! &nbsp;&nbsp;|&nbsp;&nbsp; "
                "support@netflix.com &nbsp;&nbsp;|&nbsp;&nbsp; www.netflix.com",
                footer_style
            ))
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                "This is a computer-generated receipt. No signature required.",
                footer_style
            ))
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                f"Generated on: {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
                footer_style
            ))

            # ── Build PDF ─────────────────────────────────────────
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes

        except Exception as e:
            print(f"PDF Receipt Generation Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_active_plan(self, user_id):
        """Fetches currently active subscription for a user"""
        query = """
            SELECT * FROM subscriptions 
            WHERE user_id = %s AND status = 'ACTIVE' 
            ORDER BY start_date DESC 
            LIMIT 1
        """
        df = pd.read_sql(query, db.conn, params=(user_id,))
        
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def cancel_subscription(self, user_id):
        """Updates the status of the user's active subscription to CANCELLED"""
        try:
            db.cursor.execute(
                "UPDATE subscriptions SET status = 'CANCELLED' WHERE user_id = %s AND status = 'ACTIVE'",
                (user_id,)
            )
            db.conn.commit()
            return True
        except Exception as e:
            print(f"Error cancelling subscription: {e}")
            return False

class ActivityTracker:
    def log_in(self, uid):
        now = datetime.now()
        db.cursor.execute(
            "INSERT INTO user_activity (user_id, login_time) VALUES (%s, %s) RETURNING activity_id", 
            (uid, now)
        )
        db.conn.commit()
        return db.cursor.fetchone()[0]

    def log_out(self, aid):
        now = datetime.now()
        db.cursor.execute("SELECT login_time FROM user_activity WHERE activity_id=%s", (aid,))
        res = db.cursor.fetchone()
        if res:
            start = res[0]
            mins = int((now - start).total_seconds() / 60)
            db.cursor.execute(
                "UPDATE user_activity SET logout_time=%s, session_minutes=%s WHERE activity_id=%s", 
                (now, mins, aid)
            )
            db.conn.commit()

class AdminAnalytics:
    def get_monthly_comparison(self):
        """
        Uses PAYMENTS table (not subscriptions) as source of truth for revenue.
        Seed script never writes to payments — so historical revenue is never
        affected by re-seeding. Only real app transactions are counted here.
        """
        df = pd.read_sql(
            "SELECT amount, payment_date FROM payments WHERE payment_status = 'SUCCESS'",
            db.conn
        )
        if df.empty: return 0, 0, 0, 0, 0, 0

        df['payment_date'] = pd.to_datetime(df['payment_date'])
        now = datetime.now()

        # Current month
        curr_mask = (
            (df['payment_date'].dt.month == now.month) &
            (df['payment_date'].dt.year  == now.year)
        )
        curr_rev = df[curr_mask]['amount'].sum()
        total_sales_count = int(df[curr_mask].shape[0])

        # Previous month
        first_day_curr   = now.replace(day=1)
        prev_month_date  = first_day_curr - timedelta(days=1)
        prev_mask = (
            (df['payment_date'].dt.month == prev_month_date.month) &
            (df['payment_date'].dt.year  == prev_month_date.year)
        )
        prev_rev = df[prev_mask]['amount'].sum()

        # Last year & lifetime
        last_year_rev = df[df['payment_date'].dt.year == (now.year - 1)]['amount'].sum()
        lifetime_rev  = df['amount'].sum()

        # Growth %
        growth = 0
        if prev_rev > 0:
            growth = round(((curr_rev - prev_rev) / prev_rev) * 100, 1)

        return curr_rev, prev_rev, growth, last_year_rev, total_sales_count, lifetime_rev

    def get_all_data(self, tbl):
        allowed = ["users", "subscriptions", "user_activity", "feedback", "payments"]
        if tbl not in allowed: return pd.DataFrame()
        df = pd.read_sql(f"SELECT * FROM {tbl}", db.conn)
        if tbl == 'subscriptions' and not df.empty:
            df.rename(columns={'amount': 'Revenue'}, inplace=True)
        return df
    
    def get_demographics_data(self):
        query_country = "SELECT country, COUNT(*) as count FROM users GROUP BY country ORDER BY count DESC"
        df_country = pd.read_sql(query_country, db.conn)
        total_users = pd.read_sql("SELECT COUNT(*) FROM users", db.conn).iloc[0,0]
        paid_users = pd.read_sql("SELECT COUNT(DISTINCT user_id) FROM subscriptions", db.conn).iloc[0,0]
        return df_country, total_users, paid_users
    
    def get_all_feedback(self):
        """Fetches all user feedback requests"""
        query = """
            SELECT f.id, u.fullname, u.email, f.request_content, f.created_at
            FROM feedback f
            JOIN users u ON f.user_id = u.user_id
            ORDER BY f.created_at DESC
        """
        return pd.read_sql(query, db.conn)
    def get_plan_popularity(self):
        """Fetches sales count grouped by plan name"""
        query = """
            SELECT plan_name, COUNT(*) as total_sales
            FROM subscriptions
            GROUP BY plan_name
            ORDER BY total_sales DESC
        """
        return pd.read_sql(query, db.conn)
    def get_age_distribution(self):
        """Fetches user ages for demographics analysis"""
        query = "SELECT age FROM users"
        return pd.read_sql(query, db.conn)

    def get_total_user_count(self):
        """Fetches total number of users for ARPU calculation"""
        query = "SELECT COUNT(*) as count FROM users"
        df = pd.read_sql(query, db.conn)
        return df.iloc[0]['count']

    def get_monthly_revenue_trend(self):
        """
        Fetches real revenue trend over last 6 months using PAYMENTS table.
        Seed data does not insert payments, so this chart only shows
        genuine transactions made through the app — never inflated by seeding.
        """
        query = """
            SELECT TO_CHAR(payment_date, 'YYYY-MM') as "Month",
                   SUM(amount) as "Revenue"
            FROM payments
            WHERE payment_status = 'SUCCESS'
              AND payment_date >= NOW() - INTERVAL '6 months'
            GROUP BY "Month"
            ORDER BY "Month" ASC
        """
        return pd.read_sql(query, db.conn)
    def get_churn_stats(self):
        """Calculates Churn Rate and counts"""
        # Total Count
        total_subs = pd.read_sql("SELECT COUNT(*) as count FROM subscriptions", db.conn).iloc[0]['count']
        
        # Cancelled Count
        cancelled = pd.read_sql("SELECT COUNT(*) as count FROM subscriptions WHERE status = 'CANCELLED'", db.conn).iloc[0]['count']
        
        # Calculate Rate
        churn_rate = 0
        if total_subs > 0:
            churn_rate = (cancelled / total_subs) * 100
            
        return total_subs, cancelled, round(churn_rate, 2)

    def get_active_vs_cancelled(self):
        """Fetches counts for pie chart grouped by status"""
        query = "SELECT status, COUNT(*) as count FROM subscriptions GROUP BY status"
        return pd.read_sql(query, db.conn)
    def get_avg_session_duration(self):
        """Calculates average watch time per session"""
        query = "SELECT COALESCE(AVG(session_minutes), 0) FROM user_activity"
        df = pd.read_sql(query, db.conn)
        return df.iloc[0][0]

    def get_peak_hours(self):
        """Finds top 5 hours with most logins"""
        query = """
            SELECT EXTRACT(HOUR FROM login_time) as login_hour, COUNT(*) as count
            FROM user_activity
            GROUP BY login_hour
            ORDER BY count DESC
            LIMIT 5
        """
        return pd.read_sql(query, db.conn)
    
    def get_plan_revenue_share(self):
        """
        Calculates real revenue by plan using PAYMENTS table.
        Seed data is excluded since it never inserts into payments.
        """
        query = """
            SELECT plan_name, SUM(amount) as total_revenue
            FROM payments
            WHERE payment_status = 'SUCCESS'
            GROUP BY plan_name
            ORDER BY total_revenue DESC
        """
        return pd.read_sql(query, db.conn)

    def get_customer_lifetime_value(self):
        """
        Calculates CLV using PAYMENTS table only.
        Total spend = sum of real payments made through app.
        Seed-only users who never paid through app will not appear here.
        """
        query = """
            SELECT u.user_id, u.fullname,
                   SUM(p.amount)       as total_spend,
                   MIN(p.payment_date) as first_payment,
                   MAX(p.payment_date) as last_payment
            FROM users u
            JOIN payments p ON u.user_id = p.user_id
            WHERE p.payment_status = 'SUCCESS'
            GROUP BY u.user_id, u.fullname
        """
        df = pd.read_sql(query, db.conn)
        if df.empty:
            return df

        df['today']       = pd.Timestamp.now()
        df['days_active'] = (df['today'] - df['first_payment']).dt.days
        df['days_active'] = df['days_active'].fillna(0).replace(0, 1)
        df['clv']         = (df['total_spend'] / df['days_active']).round(2)

        return df
    
    def get_all_payments(self):
        """Fetches all payment records across all users for admin view"""
        query = """
            SELECT p.payment_id, u.fullname, u.email, p.plan_name, p.amount,
                   p.payment_type, p.payment_status, p.payment_date
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            ORDER BY p.payment_date DESC
        """
        return pd.read_sql(query, db.conn)

    def get_new_vs_renewal_revenue(self):
        """Returns NEW vs RENEWAL total revenue and transaction count for metric cards"""
        query = """
            SELECT 
                payment_type,
                COUNT(*) as txn_count,
                COALESCE(SUM(amount), 0) as total_revenue
            FROM payments
            WHERE payment_status = 'SUCCESS'
            GROUP BY payment_type
            ORDER BY payment_type ASC
        """
        return pd.read_sql(query, db.conn)

    def get_monthly_new_vs_renewal(self):
        """Returns month-wise NEW vs RENEWAL breakdown for trend line chart"""
        query = """
            SELECT 
                TO_CHAR(payment_date, 'YYYY-MM') as month,
                payment_type,
                SUM(amount) as total_revenue
            FROM payments
            WHERE payment_status = 'SUCCESS'
            GROUP BY month, payment_type
            ORDER BY month ASC
        """
        return pd.read_sql(query, db.conn)

    def get_renewal_rate(self):
        """Calculates Renewal Rate % = Renewal Revenue / Total Revenue * 100"""
        query = """
            SELECT 
                COALESCE(SUM(CASE WHEN payment_type = 'RENEWAL' THEN amount ELSE 0 END), 0) as renewal_rev,
                COALESCE(SUM(amount), 0) as total_rev,
                COUNT(CASE WHEN payment_type = 'RENEWAL' THEN 1 END) as renewal_count,
                COUNT(*) as total_count
            FROM payments
            WHERE payment_status = 'SUCCESS'
        """
        df = pd.read_sql(query, db.conn)
        if df.empty or df.iloc[0]['total_rev'] == 0:
            return 0.0, 0.0, 0, 0
        row = df.iloc[0]
        renewal_rate = round((float(row['renewal_rev']) / float(row['total_rev'])) * 100, 1)
        return renewal_rate, float(row['renewal_rev']), int(row['renewal_count']), int(row['total_count'])

    def get_at_risk_users(self, days_threshold=30):
        """Finds active subscribers who haven't logged in for 30+ days"""
        query = """
            SELECT 
                u.user_id,
                u.fullname,
                u.email,
                u.country,
                s.plan_name,
                s.amount,
                s.end_date,
                MAX(a.login_time) as last_login,
                (CURRENT_DATE - MAX(a.login_time)::date) as days_inactive
            FROM users u
            JOIN subscriptions s ON u.user_id = s.user_id
            LEFT JOIN user_activity a ON u.user_id = a.user_id
            WHERE s.status = 'ACTIVE'
            GROUP BY u.user_id, u.fullname, u.email, u.country,
                     s.plan_name, s.amount, s.end_date
            HAVING (CURRENT_DATE - MAX(a.login_time)::date) >= %s
                OR MAX(a.login_time) IS NULL
            ORDER BY days_inactive DESC NULLS FIRST
        """
        return pd.read_sql(query, db.conn, params=(days_threshold,))

    def get_revenue_forecast(self):
        """Predicts next month revenue based on active subs, renewal rate and new user trend"""
        # Step 1: Active subscriptions count and avg price
        query_active = """
            SELECT COUNT(*) as active_count, 
                   COALESCE(AVG(amount), 0) as avg_price,
                   COALESCE(SUM(amount), 0) as active_revenue
            FROM subscriptions WHERE status = 'ACTIVE'
        """
        df_active = pd.read_sql(query_active, db.conn)
        active_count = int(df_active.iloc[0]['active_count'])
        avg_price    = float(df_active.iloc[0]['avg_price'])

        # Step 2: Renewal rate from payments table
        renewal_rate, _, _, _ = self.get_renewal_rate()
        renewal_rate_decimal = renewal_rate / 100

        # Step 3: Avg new users per month (last 3 months)
        query_new_users = """
            SELECT COUNT(*) as count
            FROM users
            WHERE role = 'USER'
              AND created_at >= NOW() - INTERVAL '3 months'
              AND created_at < NOW()
        """
        df_new = pd.read_sql(query_new_users, db.conn)
        total_new_3months = int(df_new.iloc[0]['count'])
        avg_new_per_month = round(total_new_3months / 3, 1)

        # Step 4: Calculate forecast
        renewal_count    = round(active_count * renewal_rate_decimal)
        renewal_revenue  = round(renewal_count * avg_price, 2)
        new_user_revenue = round(avg_new_per_month * avg_price, 2)
        total_forecast   = round(renewal_revenue + new_user_revenue, 2)

        # Step 5: Confidence score (more data = more confidence)
        query_total_payments = "SELECT COUNT(*) as cnt FROM payments"
        df_pay = pd.read_sql(query_total_payments, db.conn)
        total_payments = int(df_pay.iloc[0]['cnt'])
        confidence = min(95, 40 + (total_payments * 2))

        return {
            "active_count":      active_count,
            "avg_price":         round(avg_price, 2),
            "renewal_rate":      renewal_rate,
            "renewal_count":     renewal_count,
            "renewal_revenue":   renewal_revenue,
            "avg_new_per_month": avg_new_per_month,
            "new_user_revenue":  new_user_revenue,
            "total_forecast":    total_forecast,
            "confidence":        confidence
        }

    def search_global_users(self, email_filter, country_filter, plan_filter):
        """Advanced Global Search with Dynamic Filters combining Users and Subscriptions"""
        # Base query with LEFT JOIN to get user info + plan info
        query = """
            SELECT u.user_id, u.fullname, u.email, u.country, u.age, 
                   s.plan_name, s.status, s.amount
            FROM users u
            LEFT JOIN subscriptions s ON u.user_id = s.user_id
        """
        
        filters = []
        params = []
        
        # Dynamic WHERE Clause Logic
        if email_filter:
            filters.append("u.email LIKE %s")
            params.append(f"%{email_filter}%")
        
        if country_filter and country_filter != "All":
            filters.append("u.country = %s")
            params.append(country_filter)
            
        if plan_filter and plan_filter != "All":
            filters.append("s.plan_name = %s")
            params.append(plan_filter)
            
        # If any filters exist, append to query
        if filters:
            query += " WHERE " + " AND ".join(filters)
            
        return pd.read_sql(query, db.conn, params=tuple(params))

# ══════════════════════════════════════════════════════════════════
#  NEW: ContentManager — handles all Netflix content from Kaggle
# ══════════════════════════════════════════════════════════════════

class ContentManager:
    """
    Manages browsing, searching, and recommending Netflix content
    loaded from the Kaggle dataset via load_kaggle_content.py.
    """

    def is_content_loaded(self):
        """Returns True if the content table has at least one row."""
        try:
            db.cursor.execute("SELECT COUNT(*) FROM content")
            return db.cursor.fetchone()[0] > 0
        except Exception:
            return False

    def get_content_stats(self):
        """Returns total movies, total TV shows, and total titles."""
        try:
            db.cursor.execute("SELECT COUNT(*) FROM content")
            total = db.cursor.fetchone()[0]
            db.cursor.execute("SELECT COUNT(*) FROM content WHERE content_type = 'Movie'")
            movies = db.cursor.fetchone()[0]
            db.cursor.execute("SELECT COUNT(*) FROM content WHERE content_type = 'TV Show'")
            shows = db.cursor.fetchone()[0]
            return total, movies, shows
        except Exception:
            return 0, 0, 0

    def get_all_genres(self):
        """
        Returns a sorted unique list of individual genres
        extracted from the comma-separated 'genre' column.
        """
        try:
            df = pd.read_sql("SELECT DISTINCT genre FROM content WHERE genre != ''", db.conn)
            genres = set()
            for g_str in df['genre'].dropna():
                for g in g_str.split(','):
                    genres.add(g.strip())
            return sorted(genres)
        except Exception:
            return []

    def browse_content(self, content_type="All", genre_filter="All",
                       search_query="", page=1, page_size=20):
        """
        Returns a paginated DataFrame of content matching filters.
        content_type : 'All', 'Movie', or 'TV Show'
        genre_filter : single genre string or 'All'
        search_query : title / cast / director search string
        page         : page number (1-indexed)
        page_size    : rows per page
        """
        conditions = ["1=1"]
        params = []

        if content_type != "All":
            conditions.append("content_type = %s")
            params.append(content_type)

        if genre_filter != "All":
            conditions.append("genre ILIKE %s")
            params.append(f"%{genre_filter}%")

        if search_query.strip():
            conditions.append(
                "(title ILIKE %s OR cast_members ILIKE %s OR director ILIKE %s)"
            )
            q = f"%{search_query.strip()}%"
            params.extend([q, q, q])

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * page_size

        # Count total matching rows (for pagination)
        count_query = f"SELECT COUNT(*) FROM content WHERE {where_clause}"
        db.cursor.execute(count_query, tuple(params))
        total_count = db.cursor.fetchone()[0]

        # Fetch page
        data_query = f"""
            SELECT content_id, content_type, title, director, cast_members,
                   country, release_year, rating, duration, genre, description
            FROM content
            WHERE {where_clause}
            ORDER BY release_year DESC NULLS LAST, title ASC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        df = pd.read_sql(data_query, db.conn, params=tuple(params))

        return df, total_count

    def get_recommendations(self, favorite_genre, limit=10):
        """
        Returns content matching the user's favorite_genre from their profile.
        Falls back to trending (most recent) if no genre set.
        """
        try:
            if not favorite_genre or favorite_genre.strip() == "":
                # No genre set — return most recent titles
                query = """
                    SELECT content_id, content_type, title, genre,
                           release_year, rating, duration, description
                    FROM content
                    ORDER BY release_year DESC NULLS LAST
                    LIMIT %s
                """
                return pd.read_sql(query, db.conn, params=(limit,))
            else:
                query = """
                    SELECT content_id, content_type, title, genre,
                           release_year, rating, duration, description
                    FROM content
                    WHERE genre ILIKE %s
                    ORDER BY release_year DESC NULLS LAST
                    LIMIT %s
                """
                return pd.read_sql(query, db.conn, params=(f"%{favorite_genre}%", limit))
        except Exception as e:
            print(f"Recommendation error: {e}")
            return pd.DataFrame()

    def get_content_by_id(self, content_id):
        """Returns a single title's full details as a dict."""
        try:
            db.cursor.execute("""
                SELECT content_id, content_type, title, director, cast_members,
                       country, date_added, release_year, rating, duration,
                       genre, description
                FROM content WHERE content_id = %s
            """, (content_id,))
            row = db.cursor.fetchone()
            if not row:
                return None
            cols = ["content_id","content_type","title","director","cast_members",
                    "country","date_added","release_year","rating","duration",
                    "genre","description"]
            return dict(zip(cols, row))
        except Exception:
            return None

    # ── Admin helpers ──────────────────────────────────────────
    def get_genre_distribution(self):
        """Returns top 15 genres by content count for admin charts."""
        try:
            df = pd.read_sql(
                "SELECT genre, COUNT(*) as count FROM content "
                "WHERE genre != '' GROUP BY genre ORDER BY count DESC LIMIT 15",
                db.conn
            )
            # Expand comma-separated genres
            rows = []
            for _, r in df.iterrows():
                for g in str(r['genre']).split(','):
                    rows.append(g.strip())
            from collections import Counter
            counter = Counter(rows)
            top = pd.DataFrame(counter.most_common(15), columns=['genre', 'count'])
            return top
        except Exception:
            return pd.DataFrame()

    def get_yearly_additions(self):
        """Returns count of titles added per release_year for trend chart."""
        try:
            return pd.read_sql("""
                SELECT release_year, COUNT(*) as count
                FROM content
                WHERE release_year IS NOT NULL AND release_year > 1990
                GROUP BY release_year
                ORDER BY release_year ASC
            """, db.conn)
        except Exception:
            return pd.DataFrame()