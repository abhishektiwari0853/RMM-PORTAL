import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd
import io
import base64

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
st.set_page_config(page_title="RMM Administrative Portal", page_icon="🏫", layout="wide")

# =====================================================================
# SIMPLE RESPONSIVE STYLING – KEEPS BUTTONS VISIBLE ON MOBILE
# =====================================================================
st.markdown("""
<style>
@media (max-width: 640px) {
    .stButton > button {
        font-size: 16px;
        padding: 10px 15px;
        white-space: nowrap;
    }
    .stSelectbox select {
        font-size: 14px;
    }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 2. ROLE-BASED LOGIN (Simple centered form)
# -----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["role"] = None

if not st.session_state["authenticated"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("## School Portal Login")
        role = st.selectbox("Select Role", ["Teacher", "Clerk", "Principal"])
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            valid = False
            if role == "Teacher" and pwd == "TCH2024":
                valid = True
            elif role == "Clerk" and pwd == "CLK2024":
                valid = True
            elif role == "Principal" and pwd == "PRN2024":
                valid = True
            if valid:
                st.session_state["authenticated"] = True
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("Invalid Role or Password")
    st.stop()

# -----------------------------
# 3. DATABASE CONNECTION
# -----------------------------
@st.cache_resource
def get_workbook():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                dict(st.secrets["gcp_service_account"]), scope
            )
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        return client.open_by_key("1fiAOXJUCMk_dlKfUbW6syEEHRREaMAnNaDIe0X0wboo")
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

wb = get_workbook()
if wb is None:
    st.stop()

# -----------------------------
# 4. CACHING FUNCTIONS (TTL = 3600 seconds = 1 hour)
# -----------------------------
@st.cache_data(ttl=3600)
def get_sheet_names():
    return [ws.title.strip() for ws in wb.worksheets()]

def find_sheet(name):
    names = get_sheet_names()
    name_clean = name.strip().lower()
    for n in names:
        if n.lower() == name_clean:
            return wb.worksheet(n)
    for n in names:
        if name_clean in n.lower():
            return wb.worksheet(n)
    return None

def find_class_sheet(class_num, sheet_type):
    return find_sheet(f"{sheet_type}_{class_num}")

@st.cache_data(ttl=3600)
def load_master_data(class_num):
    sheet = find_class_sheet(class_num, 'Master')
    if not sheet:
        return pd.DataFrame(), []
    raw = sheet.get_all_values()
    if len(raw) < 2:
        return pd.DataFrame(), []
    headers = [h.strip() for h in raw[0]]
    df = pd.DataFrame(raw[1:], columns=headers)
    id_col = next((c for c in df.columns if c.lower() == 'student id'), None)
    name_col = next((c for c in df.columns if c.lower() == 'name'), None)
    student_list = []
    if id_col and name_col:
        student_list = [f"{row[id_col]} - {row[name_col]}" for _, row in df.iterrows()]
    return df, student_list

@st.cache_data(ttl=3600)
def load_attendance_data(class_num):
    sheet = find_class_sheet(class_num, 'Attendance')
    if sheet:
        return sheet.get_all_values()
    return []

@st.cache_data(ttl=3600)
def load_fees_data(class_num):
    sheet = find_class_sheet(class_num, 'Fees')
    if sheet:
        return sheet.get_all_values()
    return []

@st.cache_data(ttl=3600)
def load_fee_structure():
    sheet = find_sheet("Fee_Structure")
    if not sheet:
        return {}
    data = sheet.get_all_values()
    fee_map = {}
    if len(data) >= 2:
        for row in data[1:]:
            if len(row) >= 2:
                cls, fee = row[0].strip(), row[1].strip()
                if cls.isdigit() and fee.isdigit():
                    fee_map[cls] = int(fee)
    return fee_map

# -----------------------------
# 5. HEADER WITH LOGOUT, REFRESH AND BACK BUTTON
# -----------------------------
col_logo, col_title, col_logout = st.columns([1, 3, 1])
with col_logo:
    try:
        st.image("School_logo.png", width=80)
    except:
        pass
with col_title:
    st.markdown("<h1 style='text-align: center;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>Administrative Management System</h4>", unsafe_allow_html=True)
with col_logout:
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["role"] = None
        st.cache_data.clear()
        st.rerun()
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    # 🔙 BACK BUTTON – always visible when inside a section
    if st.session_state.get("section") is not None:
        if st.button("🔙 Back"):
            st.session_state["section"] = None
            st.rerun()

st.divider()

# -----------------------------
# 6. SESSION STATE FOR NAVIGATION
# -----------------------------
if "section" not in st.session_state:
    st.session_state["section"] = None
if "selected_class" not in st.session_state:
    st.session_state["selected_class"] = None

# -----------------------------
# 7. THREE BIG BUTTONS FOR MAIN SECTIONS
# -----------------------------
if st.session_state["section"] is None:
    st.markdown("### Select a Module")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎓 Student Section", key="btn_student", width='stretch'):
            st.session_state["section"] = "Student"
            st.rerun()
    with col2:
        if st.button("💰 Fees Management", key="btn_fees", width='stretch'):
            st.session_state["section"] = "Fees"
            st.rerun()
    with col3:
        if st.button("📊 Executive Dashboard", key="btn_dashboard", width='stretch'):
            st.session_state["section"] = "Dashboard"
            st.rerun()
    st.stop()

# -----------------------------
# 8. COMMON CLASS SELECTION (after section is chosen)
# -----------------------------
st.markdown(f"### Current Module: **{st.session_state['section']}**")
selected_class = st.selectbox("Select Academic Class", ["7", "8", "9", "10", "11", "12"], key="class_selector")
st.session_state["selected_class"] = selected_class

# Load data for selected class (cached)
df_master, student_list = load_master_data(selected_class)
id_col = next((c for c in df_master.columns if c.lower() == 'student id'), None) if not df_master.empty else None
name_col = next((c for c in df_master.columns if c.lower() == 'name'), None) if not df_master.empty else None

attendance_data = load_attendance_data(selected_class)
fees_data = load_fees_data(selected_class)
monthly_fee_map = load_fee_structure()
default_monthly_fee = monthly_fee_map.get(selected_class, 500)

master_sheet = find_class_sheet(selected_class, 'Master')
attendance_sheet = find_class_sheet(selected_class, 'Attendance')
fees_sheet = find_class_sheet(selected_class, 'Fees')

marks_sheet = find_sheet("Marks_Entry")
exam_schedule_sheet = find_sheet("Exam_Schedule")

if not all([master_sheet, attendance_sheet, fees_sheet]):
    st.error("Required class sheets missing. Please check tab names.")
    st.stop()

# -----------------------------
# 9. SUB-MENU OPTIONS BASED ON SECTION & ROLE
# -----------------------------
role = st.session_state["role"]
section = st.session_state["section"]

if section == "Student":
    if role == "Teacher":
        sub_options = [
            "Student Attendance","Attendance Report",
            "Marks Entry","Result Card","Admit Card",
            "Student Records","Edit Student Details","Add New Student","At-Risk Students"
        ]
    elif role == "Clerk":
        sub_options = ["Result Card","Admit Card","Add New Student","Student Records"]
    else:  # Principal
        sub_options = [
            "Student Attendance","Attendance Report",
            "Marks Entry","Result Card","Admit Card",
            "Student Records","Edit Student Details","Add New Student","At-Risk Students"
        ]
elif section == "Fees":
    if role == "Teacher":
        st.warning("You do not have access to this section.")
        st.stop()
    elif role == "Clerk":
        sub_options = ["Fee Collection","Daily Cash Report","Defaulter List"]
    else:  # Principal
        sub_options = ["Fee Collection","Daily Cash Report","Defaulter List"]
elif section == "Dashboard":
    if role == "Principal":
        sub_options = ["Executive Dashboard"]
    else:
        st.warning("Only Principal can view the Dashboard.")
        st.stop()

# Show sub-menu only if there are options
if section != "Dashboard":
    menu = st.radio("Choose Action", sub_options, horizontal=True, label_visibility="collapsed")
else:
    menu = "Executive Dashboard"

# =============================
# 10. EXECUTIVE DASHBOARD (Principal only)
# =============================
if menu == "Executive Dashboard":
    st.subheader(f"Executive Dashboard – Class {selected_class}")

    @st.cache_data(ttl=3600)
    def compute_dashboard_metrics(selected_class, df_master, attendance_data, fees_data, monthly_fee_map):
        total_students = len(df_master)
        today_str = datetime.now().strftime("%d-%m-%Y")
        att_headers = attendance_data[0] if attendance_data else []
        today_col = None
        for idx, h in enumerate(att_headers):
            if h == today_str:
                today_col = idx
                break
        present_today = 0
        if today_col and len(attendance_data) > 1:
            for row in attendance_data[1:]:
                if today_col < len(row) and row[today_col].strip().upper() == 'P':
                    present_today += 1
        attendance_pct = (present_today / total_students * 100) if total_students > 0 else 0

        total_today_fees = 0
        if fees_data and len(fees_data) > 1:
            for row in fees_data[1:]:
                if len(row) >= 4:
                    date_part = row[3].split(' ')[0] if row[3] else ""
                    if date_part == today_str and row[1].isdigit():
                        total_today_fees += int(row[1])

        current_month = datetime.now().month
        current_year = datetime.now().year
        month_collection = 0
        if fees_data and len(fees_data) > 1:
            for row in fees_data[1:]:
                if len(row) >= 4:
                    date_str = row[3].split(' ')[0] if row[3] else ""
                    try:
                        d = datetime.strptime(date_str, "%d-%m-%Y")
                        if d.month == current_month and d.year == current_year and row[1].isdigit():
                            month_collection += int(row[1])
                    except:
                        pass

        monthly_fee = monthly_fee_map.get(selected_class, 500)
        expected_monthly = total_students * monthly_fee
        collection_pct = (month_collection / expected_monthly * 100) if expected_monthly > 0 else 0

        if not df_master.empty:
            def calc_outstanding(row):
                total_paid = int(row['Total_Fees']) if 'Total_Fees' in row and str(row['Total_Fees']).isdigit() else 0
                if current_month >= 4:
                    months = current_month - 4 + 1
                else:
                    months = current_month + 9
                expected = months * monthly_fee
                return max(0, expected - total_paid)
            df_master_temp = df_master.copy()
            df_master_temp['Outstanding'] = df_master_temp.apply(calc_outstanding, axis=1)
            top_defaulters = df_master_temp.nlargest(5, 'Outstanding')[['Name', 'Outstanding']]
        else:
            top_defaulters = pd.DataFrame()

        at_risk_count = 0
        if attendance_data and len(attendance_data) > 1:
            for row in attendance_data[1:]:
                max_consec = 0
                streak = 0
                for idx in range(1, len(row)):
                    val = row[idx].strip().upper() if idx < len(row) else ""
                    if val != 'P':
                        streak += 1
                    else:
                        streak = 0
                    max_consec = max(max_consec, streak)
                if max_consec >= 5:
                    at_risk_count += 1

        return total_students, attendance_pct, present_today, total_today_fees, month_collection, collection_pct, top_defaulters, at_risk_count

    if df_master.empty:
        st.warning("No student data.")
    else:
        total_students, att_pct, present, today_fees, month_col, col_pct, top_def, at_risk = compute_dashboard_metrics(
            selected_class, df_master, attendance_data, fees_data, monthly_fee_map
        )

        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Total Students", total_students)
        col_b.metric("Today's Attendance", f"{att_pct:.1f}% ({present}/{total_students})")
        col_c.metric("Today's Fees Collected", f"INR {today_fees}")
        col_d.metric("This Month Collection", f"INR {month_col} ({col_pct:.0f}%)")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Top 5 Defaulters (Outstanding)**")
            if not top_def.empty:
                st.dataframe(top_def.reset_index(drop=True))
            else:
                st.write("No defaulters.")
        with col2:
            st.write("**Dropout Risk**")
            st.metric("At-Risk Students (5+ consec. absences)", at_risk)

# =============================
# 11. STUDENT ATTENDANCE (with search filter)
# =============================
elif menu == "Student Attendance":
    st.subheader(f"Daily Attendance – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        search_term = st.text_input("Search Student by Name or ID", "")
        if search_term:
            filtered_students = [s for s in student_list if search_term.lower() in s.lower()]
        else:
            filtered_students = student_list

        selected_student = st.selectbox("Select Student", ["-- Select --"] + filtered_students)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Mark Present"):
                if selected_student == "-- Select --":
                    st.warning("Please select a student first.")
                else:
                    s_id = selected_student.split(" - ")[0]
                    try:
                        today = datetime.now().strftime("%d-%m-%Y")
                        hdrs = attendance_sheet.row_values(1)
                        col_idx = hdrs.index(today) + 1 if today in hdrs else len(hdrs) + 1
                        if today not in hdrs:
                            attendance_sheet.update_cell(1, col_idx, today)
                        cell = attendance_sheet.find(s_id)
                        attendance_sheet.update_cell(cell.row, col_idx, "P")
                        st.success(f"Present marked for {selected_student}")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Update failed: {e}")

        with col2:
            if st.button("Mark All Present"):
                try:
                    today = datetime.now().strftime("%d-%m-%Y")
                    hdrs = attendance_sheet.row_values(1)
                    col_idx = hdrs.index(today) + 1 if today in hdrs else len(hdrs) + 1
                    if today not in hdrs:
                        attendance_sheet.update_cell(1, col_idx, today)
                    all_ids = [f"{row[id_col]}" for _, row in df_master.iterrows()]
                    cnt = 0
                    for sid in all_ids:
                        try:
                            cell = attendance_sheet.find(sid)
                            attendance_sheet.update_cell(cell.row, col_idx, "P")
                            cnt += 1
                        except:
                            pass
                    st.success(f"All {cnt} students marked Present")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error: {e}")

        with col3:
            if st.button("Mark Absent for Unmarked"):
                try:
                    today = datetime.now().strftime("%d-%m-%Y")
                    hdrs = attendance_sheet.row_values(1)
                    if today not in hdrs:
                        st.warning("Today's column not created yet.")
                    else:
                        col_idx = hdrs.index(today) + 1
                        all_ids = [f"{row[id_col]}" for _, row in df_master.iterrows()]
                        absent_cnt = 0
                        for sid in all_ids:
                            try:
                                cell = attendance_sheet.find(sid)
                                curr_val = attendance_sheet.cell(cell.row, col_idx).value
                                if curr_val is None or curr_val.strip() == "":
                                    attendance_sheet.update_cell(cell.row, col_idx, "A")
                                    absent_cnt += 1
                            except:
                                pass
                        st.success(f"Marked {absent_cnt} students as Absent")
                        st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error: {e}")

# =============================
# 12. ATTENDANCE REPORT
# =============================
elif menu == "Attendance Report":
    st.subheader(f"Monthly Attendance Report – Class {selected_class}")
    months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    sel_month = st.selectbox("Month", months, index=datetime.now().month-1)
    sel_year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.now().year)
    month_num = months.index(sel_month) + 1
    month_str = f"{month_num:02d}"

    with st.spinner("Generating attendance report..."):
        if len(attendance_data) < 2:
            st.warning("No attendance data.")
        else:
            att_headers = attendance_data[0]
            date_cols = []
            col_indices = []
            for idx, h in enumerate(att_headers):
                if idx == 0: continue
                parts = h.split('-')
                if len(parts) == 3 and parts[1] == month_str and parts[2] == str(sel_year):
                    date_cols.append(h)
                    col_indices.append(idx)
            if not date_cols:
                st.warning(f"No records for {sel_month} {sel_year}")
            else:
                total_days = len(date_cols)
                records = []
                for row in attendance_data[1:]:
                    sid = row[0]
                    name = "N/A"
                    if not df_master.empty:
                        mask = df_master[id_col].astype(str) == sid
                        if mask.any():
                            name = df_master.loc[mask, name_col].values[0]
                    present = sum(1 for ci in col_indices if ci < len(row) and row[ci].strip().upper() == 'P')
                    percent = (present / total_days * 100) if total_days else 0
                    records.append({
                        "Student ID": sid,
                        "Name": name,
                        "Working Days": total_days,
                        "Present": present,
                        "Attendance %": round(percent, 1)
                    })
                df_rep = pd.DataFrame(records)
                def highlight_low(val):
                    return 'background-color: #ffcccc' if val < 75 else ''
                st.dataframe(df_rep.style.map(highlight_low, subset=['Attendance %']), use_container_width=True)

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_rep.to_excel(writer, index=False, sheet_name='Attendance')
                st.download_button(
                    label="Download Excel Report",
                    data=buffer.getvalue(),
                    file_name=f"Attendance_Class{selected_class}_{sel_month}_{sel_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# =============================
# 13. FEE COLLECTION (with Receipt Printing)
# =============================
elif menu == "Fee Collection":
    if role not in ["Clerk", "Principal"]:
        st.error("Access Denied")
        st.stop()
    st.subheader(f"Fee Counter – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        search_term = st.text_input("Search Student", "")
        if search_term:
            filtered_students = [s for s in student_list if search_term.lower() in s.lower()]
        else:
            filtered_students = student_list

        selected_student = st.selectbox("Select Student", ["-- Select --"] + filtered_students)
        if selected_student != "-- Select --":
            s_id = selected_student.split(" - ")[0]
            try:
                m_cell = master_sheet.find(s_id)
                m_row = master_sheet.row_values(m_cell.row)
                current_fees = int(m_row[6]) if len(m_row) >= 7 and str(m_row[6]).isdigit() else 0
                st.info(f"**Student:** {m_row[1]} | **Father:** {m_row[3]} | **Total Paid:** INR {current_fees}")

                with st.form("fee_form", clear_on_submit=True):
                    amount = st.number_input("Amount Received", min_value=0)
                    month = st.selectbox("Month", ["April","May","June","July","August","September","October","November","December","January","February","March"])
                    mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque"])
                    submitted = st.form_submit_button("Process Payment")

                    if submitted:
                        if amount <= 0:
                            st.error("Amount must be > 0")
                        else:
                            new_total = current_fees + amount
                            master_sheet.update_cell(m_cell.row, 7, str(new_total))
                            ts = datetime.now().strftime("%d-%m-%Y %H:%M")
                            fees_sheet.insert_row([s_id, amount, month, f"{ts} {mode}"], index=2)
                            st.success(f"Payment of INR {amount} recorded. New Total: INR {new_total}")
                            st.cache_data.clear()

                            # ---- RECEIPT SECTION ----
                            receipt_html = f"""
                            <div style="border:1px solid #ccc; padding:15px; margin-top:20px; border-radius:8px;">
                                <h3 style="text-align:center;">PAYMENT RECEIPT</h3>
                                <p><b>Receipt No:</b> RCP-{int(datetime.timestamp(datetime.now()))}</p>
                                <p><b>Date:</b> {datetime.now().strftime("%d-%m-%Y %H:%M")}</p>
                                <p><b>Student ID:</b> {s_id}</p>
                                <p><b>Student Name:</b> {m_row[1]}</p>
                                <p><b>Amount Paid:</b> INR {amount}</p>
                                <p><b>Payment Mode:</b> {mode}</p>
                                <p><b>Month:</b> {month}</p>
                            </div>
                            """
                            st.markdown(receipt_html, unsafe_allow_html=True)
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("""
                                    <button onclick="window.print()" style="background:#1a3b5d; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer;">
                                        Print Receipt
                                    </button>
                                """, unsafe_allow_html=True)
                            with col2:
                                b64 = base64.b64encode(receipt_html.encode()).decode()
                                href = f'<a href="data:text/html;base64,{b64}" download="Receipt_{s_id}_{datetime.now().strftime("%Y%m%d%H%M")}.html">Download Receipt</a>'
                                st.markdown(href, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error: {e}")

# =============================
# 14. DAILY CASH REPORT
# =============================
elif menu == "Daily Cash Report":
    if role not in ["Clerk", "Principal"]:
        st.error("Access Denied")
        st.stop()
    st.subheader(f"Today's Financial Summary – Class {selected_class}")
    today_date = datetime.now().strftime("%d-%m-%Y")
    if fees_data and len(fees_data) > 1:
        fee_headers = fees_data[0]
        today_rows = []
        for r in fees_data[1:]:
            if len(r) >= 4:
                date_part = r[3].split(' ')[0] if r[3] else ""
                if date_part == today_date:
                    today_rows.append(r)
        if today_rows:
            amt_col = fee_headers.index('Amount') if 'Amount' in fee_headers else 1
            total = sum(int(r[amt_col]) for r in today_rows if r[amt_col].isdigit())
            st.metric("Total Collection Today", f"INR {total}")
            df_show = pd.DataFrame(today_rows, columns=fee_headers)
            st.dataframe(df_show[['Student ID','Amount','Month','Date of payment']])
        else:
            st.info("No transactions recorded today.")
    else:
        st.info("No fee records yet.")

# =============================
# 15. DEFAULTER LIST
# =============================
elif menu == "Defaulter List":
    if role not in ["Clerk", "Principal"]:
        st.error("Access Denied")
        st.stop()
    st.subheader(f"Fee Defaulter List – Class {selected_class}")
    with st.spinner("Calculating outstanding balances..."):
        if df_master.empty:
            st.warning("No students found.")
        else:
            current_date = datetime.now()
            current_month = current_date.month
            if current_month >= 4:
                months_count = current_month - 4 + 1
            else:
                months_count = current_month + 9
            monthly_fee = monthly_fee_map.get(selected_class, 500)
            expected_total = months_count * monthly_fee

            defaulter_list = []
            for _, student in df_master.iterrows():
                sid = str(student[id_col])
                name = student[name_col]
                total_paid = int(student.get('Total_Fees', 0)) if str(student.get('Total_Fees', 0)).isdigit() else 0
                outstanding = max(0, expected_total - total_paid)
                last_date = "N/A"
                if fees_data:
                    for row in fees_data[1:]:
                        if row[0].upper() == sid.upper():
                            date_str = row[3] if len(row) > 3 else ""
                            if date_str:
                                last_date = date_str.split(' ')[0]
                defaulter_list.append({
                    "Student ID": sid, "Name": name, "Total Paid": total_paid,
                    "Expected Total": expected_total, "Outstanding": outstanding,
                    "Last Paid Date": last_date
                })
            df_def = pd.DataFrame(defaulter_list)
            df_def = df_def.sort_values("Outstanding", ascending=False)
            def hl(val):
                if val > 1000: return 'background-color: #ff4d4d'
                elif val > 0: return 'background-color: #ffff99'
                return ''
            st.dataframe(df_def.style.map(hl, subset=['Outstanding']), use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_def.to_excel(writer, index=False, sheet_name='Defaulters')
            st.download_button(
                label="Download Defaulter List (Excel)",
                data=buffer.getvalue(),
                file_name=f"Defaulters_Class{selected_class}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# =============================
# 16. STUDENT RECORDS
# =============================
elif menu == "Student Records":
    st.subheader(f"Student Profile – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        search_term = st.text_input("Search Student", "")
        if search_term:
            filtered_students = [s for s in student_list if search_term.lower() in s.lower()]
        else:
            filtered_students = student_list

        selected_student = st.selectbox("Select Student", ["-- Select --"] + filtered_students)
        if selected_student != "-- Select --":
            s_id = selected_student.split(" - ")[0]
            mask = df_master[id_col].astype(str) == s_id
            if mask.any():
                student_data = df_master[mask].iloc[0]
                name = student_data.get('Name','')
                roll = student_data.get('Roll No','')
                father = student_data.get('Father name', student_data.get('Father Name',''))
                mobile = student_data.get('Mobile','')
                total_fees = student_data.get('Total_Fees','0')
                address = student_data.get('Adress', student_data.get('Address','N/A'))
                st.info(f"**Name:** {name}  |  **Roll No:** {roll}")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Father's Name:** {father}")
                    st.write(f"**Address:** {address}")
                with c2:
                    st.write(f"**Mobile:** {mobile}")
                    st.markdown(f"### Total Fees Paid: INR {total_fees}")
                st.divider()
                st.subheader("Fee Payment History")
                if fees_data and len(fees_data) > 1:
                    fee_headers = fees_data[0]
                    history = [r for r in fees_data[1:] if r[0].upper() == s_id.upper()]
                    if history:
                        st.dataframe(pd.DataFrame(history, columns=fee_headers), use_container_width=True)
                        df_hist = pd.DataFrame(history, columns=fee_headers)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as w:
                            df_hist.to_excel(w, index=False, sheet_name='FeeHistory')
                        st.download_button(
                            label="Download Fee History (Excel)",
                            data=buf.getvalue(),
                            file_name=f"FeeHistory_{s_id}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.write("No payment history found.")
                else:
                    st.write("No payment records available.")
            else:
                st.warning("Student not found.")

# =============================
# 17. EDIT STUDENT DETAILS
# =============================
elif menu == "Edit Student Details":
    st.subheader(f"Edit Student Information – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        search_term = st.text_input("Search Student", "")
        if search_term:
            filtered_students = [s for s in student_list if search_term.lower() in s.lower()]
        else:
            filtered_students = student_list

        selected_student = st.selectbox("Choose Student to Edit", ["-- Select --"] + filtered_students)
        if selected_student != "-- Select --":
            s_id = selected_student.split(" - ")[0]
            try:
                cell = master_sheet.find(s_id)
                row_num = cell.row
                row_data = master_sheet.row_values(row_num)
                headers_edit = [h.strip() for h in master_sheet.row_values(1)]

                def find_col(col_name):
                    col_name = col_name.lower()
                    for i, h in enumerate(headers_edit):
                        if h.lower() == col_name:
                            return i
                    for i, h in enumerate(headers_edit):
                        if col_name in h.lower():
                            return i
                    return None

                col_name = find_col('name')
                col_father = find_col('father')
                col_mobile = find_col('mobile')
                col_address = find_col('adress')
                if col_address is None: col_address = find_col('address')
                col_aadhaar = find_col('aadhar')

                def safe_get(idx):
                    return row_data[idx] if idx < len(row_data) else ""
                current_name = safe_get(col_name)
                current_roll = safe_get(find_col('roll no')) if find_col('roll no') else "N/A"
                current_father = safe_get(col_father)
                current_mobile = safe_get(col_mobile)
                current_address = safe_get(col_address)
                current_aadhaar = safe_get(col_aadhaar) if col_aadhaar else ""

                st.info(f"**Student ID:** {s_id} | **Roll No:** {current_roll}")
                st.write("---")
                with st.form("edit_form"):
                    new_name = st.text_input("Name", value=current_name)
                    new_father = st.text_input("Father's Name", value=current_father)
                    new_mobile = st.text_input("Mobile Number", value=current_mobile)
                    new_address = st.text_input("Address", value=current_address)
                    new_aadhaar = st.text_input("Aadhaar Number", value=current_aadhaar)
                    if st.form_submit_button("Update Details"):
                        updates = []
                        if new_name != current_name and col_name is not None:
                            updates.append((col_name, new_name))
                        if new_father != current_father and col_father is not None:
                            updates.append((col_father, new_father))
                        if new_mobile != current_mobile and col_mobile is not None:
                            updates.append((col_mobile, new_mobile))
                        if new_address != current_address and col_address is not None:
                            updates.append((col_address, new_address))
                        if new_aadhaar != current_aadhaar and col_aadhaar is not None:
                            updates.append((col_aadhaar, new_aadhaar))
                        if not updates:
                            st.info("No changes detected.")
                        else:
                            for col_idx, value in updates:
                                master_sheet.update_cell(row_num, col_idx + 1, value)
                            st.success("Student details updated successfully!")
                            st.cache_data.clear()
            except Exception as e:
                st.error(f"Error: {e}")

# =============================
# 18. ADD NEW STUDENT
# =============================
elif menu == "Add New Student":
    st.subheader(f"Enroll New Student – Class {selected_class}")
    existing_ids = []
    existing_rolls = []
    if not df_master.empty:
        id_col_local = id_col
        roll_col_local = next((c for c in df_master.columns if c.lower() == 'roll no'), None)
        if id_col_local:
            existing_ids = df_master[id_col_local].astype(str).tolist()
        if roll_col_local:
            try:
                existing_rolls = df_master[roll_col_local].astype(int).tolist()
            except:
                pass

    prefix = f"RMEC{selected_class}"
    max_seq = 0
    for sid in existing_ids:
        if sid.startswith(prefix):
            num_part = sid[len(prefix):]
            if num_part.isdigit():
                max_seq = max(max_seq, int(num_part))
    new_id = f"{prefix}{max_seq + 1:03d}"

    new_roll = 1
    if existing_rolls:
        new_roll = max(existing_rolls) + 1

    with st.form("add_student_form", clear_on_submit=True):
        st.info(new_id)
        st.caption("Student ID (auto‑generated)")
        st.info(str(new_roll))
        st.caption("Roll Number (auto‑generated)")
        new_name = st.text_input("Full Name *")
        new_father = st.text_input("Father's Name *")
        new_mobile = st.text_input("Mobile Number")
        new_address = st.text_input("Address")
        new_aadhaar = st.text_input("Aadhaar Number")
        if st.form_submit_button("Enroll Student"):
            if not new_name.strip() or not new_father.strip():
                st.error("Name and Father's Name are required.")
            else:
                new_row = [
                    new_id, new_name.strip(), str(new_roll), new_father.strip(),
                    "", new_mobile.strip() if new_mobile else "", "0",
                    new_address.strip() if new_address else "", "",
                    new_aadhaar.strip() if new_aadhaar else ""
                ]
                try:
                    master_sheet.append_row(new_row, value_input_option='USER_ENTERED')
                    attendance_sheet.append_row([new_id])
                    st.success(f"Student {new_name} enrolled successfully!")
                    st.balloons()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# =============================
# 19. AT-RISK STUDENTS
# =============================
elif menu == "At-Risk Students":
    st.subheader(f"Dropout Risk Alert – Class {selected_class}")
    with st.spinner("Analyzing attendance patterns..."):
        if len(attendance_data) < 2:
            st.warning("No attendance data.")
        else:
            att_headers = attendance_data[0]
            date_map = {}
            for idx, h in enumerate(att_headers):
                if idx == 0: continue
                parts = h.split('-')
                if len(parts) == 3:
                    try:
                        d = datetime.strptime(h, "%d-%m-%Y")
                        date_map[idx] = d
                    except:
                        pass
            sorted_cols = sorted(date_map.items(), key=lambda x: x[1])

            at_risk = []
            for row in attendance_data[1:]:
                sid = row[0]
                name = "N/A"
                if not df_master.empty:
                    mask = df_master[id_col].astype(str) == sid
                    if mask.any():
                        name = df_master.loc[mask, name_col].values[0]
                max_consec = 0
                streak = 0
                for col_idx, _ in sorted_cols:
                    val = row[col_idx].strip().upper() if col_idx < len(row) else ""
                    if val != 'P':
                        streak += 1
                    else:
                        streak = 0
                    max_consec = max(max_consec, streak)
                if max_consec >= 5:
                    at_risk.append((sid, name, max_consec))

            if at_risk:
                df_risk = pd.DataFrame(at_risk, columns=["Student ID", "Name", "Consecutive Absences"])
                st.warning(f"Total students at risk: {len(at_risk)}")
                st.dataframe(df_risk.style.map(lambda x: 'background-color: #ff4d4d' if isinstance(x, int) and x >= 5 else '', subset=['Consecutive Absences']))
            else:
                st.success("No students with 5+ consecutive absences.")

# =============================
# 20. MARKS ENTRY (Multi‑subject support)
# =============================
elif menu == "Marks Entry":
    st.subheader(f"Marks Entry – Class {selected_class}")
    if marks_sheet is None:
        st.error("Marks_Entry sheet not found. Please create it with columns: Class, Student_ID, Exam, Subject, Marks_Obtained, Max_Marks, Grade")
    elif not student_list:
        st.warning("No students.")
    else:
        with st.form("marks_form"):
            sel_student = st.selectbox("Student", ["-- Select --"] + student_list)
            exam = st.text_input("Exam (e.g. Half-Yearly, Annual)")
            st.markdown("**Enter subjects and marks** (one per line, format: `Subject: Obtained/Max`, e.g., `Hindi: 78/100`)")
            subjects_text = st.text_area("Subjects & Marks", placeholder="Hindi: 78/100\nEnglish: 85/100\nMaths: 90/100")

            if st.form_submit_button("Save All Marks"):
                if sel_student == "-- Select --" or not exam.strip() or not subjects_text.strip():
                    st.error("Please fill all required fields (Student, Exam, and at least one subject).")
                else:
                    sid = sel_student.split(" - ")[0]
                    lines = [line.strip() for line in subjects_text.split("\n") if line.strip()]
                    rows_to_add = []
                    for line in lines:
                        if ":" not in line or "/" not in line:
                            st.error(f"Invalid format in line: '{line}'. Use 'Subject: Obtained/Max'")
                            break
                        subject_part, marks_part = line.split(":", 1)
                        subject = subject_part.strip()
                        marks = marks_part.strip()
                        if "/" not in marks:
                            st.error(f"Missing '/' in marks for {subject}. Use Obtained/Max")
                            break
                        obt_str, max_str = marks.split("/", 1)
                        try:
                            obt = int(obt_str.strip())
                            max_m = int(max_str.strip())
                        except:
                            st.error(f"Invalid numbers in '{line}'")
                            break
                        rows_to_add.append([selected_class, sid, exam.strip(), subject, obt, max_m, ""])
                    else:
                        for row in rows_to_add:
                            marks_sheet.append_row(row, value_input_option='USER_ENTERED')
                        st.success(f"{len(rows_to_add)} subjects saved for {exam}!")
                        st.cache_data.clear()

# =============================
# 21. RESULT CARD
# =============================
elif menu == "Result Card":
    st.subheader("Generate Result Card")
    if marks_sheet is None:
        st.error("Marks_Entry sheet not found.")
    elif not student_list:
        st.warning("No students.")
    else:
        sel_student = st.selectbox("Select Student", ["-- Select --"] + student_list)
        try:
            all_marks = pd.DataFrame(marks_sheet.get_all_records())
            class_marks = all_marks[all_marks['Class'] == selected_class]
            exams = class_marks['Exam'].unique().tolist() if not class_marks.empty else []
        except:
            exams = []
        sel_exam = st.selectbox("Select Exam", exams if exams else ["No exams"])

        if st.button("Generate Report Card"):
            if sel_student == "-- Select --" or sel_exam == "No exams":
                st.warning("Please select student and exam.")
            else:
                sid = sel_student.split(" - ")[0]
                student_data = df_master[df_master[id_col] == sid].iloc[0]
                name = student_data[name_col]
                roll = student_data.get('Roll No', '')
                cls = selected_class

                student_marks = class_marks[(class_marks['Student_ID'] == sid) & (class_marks['Exam'] == sel_exam)]
                if student_marks.empty:
                    st.error("No marks found for this student and exam.")
                else:
                    def get_attendance_pct(sid, att_data):
                        today = datetime.now()
                        start = datetime(today.year, 4, 1) if today.month >= 4 else datetime(today.year-1, 4, 1)
                        total_days, present = 0, 0
                        for idx, h in enumerate(att_data[0]):
                            if idx == 0: continue
                            try:
                                d = datetime.strptime(h, "%d-%m-%Y")
                                if start <= d <= today:
                                    total_days += 1
                                    for row in att_data[1:]:
                                        if row[0] == sid and idx < len(row) and row[idx].strip().upper() == 'P':
                                            present += 1
                                            break
                            except: pass
                        return round(present/total_days*100, 1) if total_days else 0

                    att_pct = get_attendance_pct(sid, attendance_data)

                    rows_html = ""
                    total = 0
                    max_total = 0
                    for _, row in student_marks.iterrows():
                        rows_html += f"<tr><td>{row['Subject']}</td><td>{row['Max_Marks']}</td><td>{row['Marks_Obtained']}</td><td>{row.get('Grade','')}</td></tr>"
                        total += int(row['Marks_Obtained'])
                        max_total += int(row['Max_Marks'])
                    percent = round(total/max_total*100, 1) if max_total else 0

                    result_html = f"""
                    <div style="max-width:700px; margin:auto; border:2px solid #1a3b5d; padding:25px; font-family:'Georgia', serif;">
                      <div style="text-align:center;">
                        <h2 style="color:#1a3b5d;">RAM MURTI MISHRA INTER COLLEGE</h2>
                        <p style="font-size:18px;">ACADEMIC REPORT</p>
                      </div>
                      <div style="display:flex; justify-content:space-between; margin:20px 0;">
                        <div><b>Name:</b> {name}<br><b>Roll:</b> {roll}<br><b>Class:</b> {cls}</div>
                        <div><b>Attendance:</b> {att_pct}%<br><b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}</div>
                      </div>
                      <table style="width:100%; border-collapse:collapse;">
                        <tr style="background:#1a3b5d; color:white;"><th>Subject</th><th>Max</th><th>Obtained</th><th>Grade</th></tr>
                        {rows_html}
                      </table>
                      <p style="text-align:right; margin-top:20px;"><b>Total:</b> {total}/{max_total} &nbsp;&nbsp; <b>Percentage:</b> {percent}%</p>
                      <p style="margin-top:50px; text-align:right;"><b>Class Teacher</b></p>
                    </div>
                    """
                    st.markdown(result_html, unsafe_allow_html=True)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown('<button onclick="window.print()">Print Report Card</button>', unsafe_allow_html=True)
                    with col2:
                        b64 = base64.b64encode(result_html.encode()).decode()
                        href = f'<a href="data:text/html;base64,{b64}" download="ReportCard_{sid}.html">Download</a>'
                        st.markdown(href, unsafe_allow_html=True)

# =============================
# 22. ADMIT CARD
# =============================
elif menu == "Admit Card":
    st.subheader("Generate Admit Card")
    if exam_schedule_sheet is None:
        st.error("Exam_Schedule sheet not found. Please create it with columns: Class, Exam, Date, Time, Subject, Room_No")
    elif not student_list:
        st.warning("No students.")
    else:
        sel_student = st.selectbox("Select Student", ["-- Select --"] + student_list)
        try:
            sched_df = pd.DataFrame(exam_schedule_sheet.get_all_records())
            class_sched = sched_df[sched_df['Class'] == selected_class]
            exams = class_sched['Exam'].unique().tolist() if not class_sched.empty else []
        except:
            exams = []
        sel_exam = st.selectbox("Select Exam", exams if exams else ["No exams"])

        if st.button("Generate Admit Card"):
            if sel_student == "-- Select --" or sel_exam == "No exams":
                st.warning("Please select student and exam.")
            else:
                sid = sel_student.split(" - ")[0]
                student_data = df_master[df_master[id_col] == sid].iloc[0]
                name = student_data[name_col]
                roll = student_data.get('Roll No', '')

                exam_details = class_sched[class_sched['Exam'] == sel_exam]
                if exam_details.empty:
                    st.error("No schedule for this exam.")
                else:
                    rows_html = ""
                    for _, row in exam_details.iterrows():
                        rows_html += f"<tr><td>{row['Subject']}</td><td>{row['Date']}</td><td>{row['Time']}</td><td>{row['Room_No']}</td></tr>"

                    admit_html = f"""
                    <div style="max-width:600px; margin:auto; border:2px solid #000; padding:25px; font-family:'Helvetica', sans-serif;">
                      <h2 style="text-align:center;">RAM MURTI MISHRA INTER COLLEGE</h2>
                      <h3 style="text-align:center; border-bottom:1px solid #000; padding-bottom:10px;">ADMIT CARD</h3>
                      <p><b>Name:</b> {name} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <b>Roll No:</b> {roll}</p>
                      <p><b>Exam:</b> {sel_exam}</p>
                      <table style="width:100%; border-collapse:collapse; margin-top:20px;">
                        <tr style="background:#eee;"><th>Subject</th><th>Date</th><th>Time</th><th>Room</th></tr>
                        {rows_html}
                      </table>
                      <p style="margin-top:30px;"><b>Instructions:</b> 1. Carry this card to exam hall. 2. Reach 15 minutes before.</p>
                      <p style="margin-top:50px; text-align:right;"><b>Principal</b></p>
                    </div>
                    """
                    st.markdown(admit_html, unsafe_allow_html=True)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown('<button onclick="window.print()">Print Admit Card</button>', unsafe_allow_html=True)
                    with col2:
                        b64 = base64.b64encode(admit_html.encode()).decode()
                        href = f'<a href="data:text/html;base64,{b64}" download="AdmitCard_{sid}_{sel_exam}.html">Download</a>'
                        st.markdown(href, unsafe_allow_html=True)
