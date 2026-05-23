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
# NO CUSTOM CSS – USING STREAMLIT'S DEFAULT LIGHT THEME
# =====================================================================

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
# 4. CACHING FUNCTIONS (10 min TTL)
# -----------------------------
@st.cache_data(ttl=600)
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

@st.cache_data(ttl=600)
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

@st.cache_data(ttl=600)
def load_attendance_data(class_num):
    sheet = find_class_sheet(class_num, 'Attendance')
    if sheet:
        return sheet.get_all_values()
    return []

@st.cache_data(ttl=600)
def load_fees_data(class_num):
    sheet = find_class_sheet(class_num, 'Fees')
    if sheet:
        return sheet.get_all_values()
    return []

@st.cache_data(ttl=600)
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
# 5. SIDEBAR (using st.radio – stable)
# -----------------------------
with st.sidebar:
    st.header("Administration Panel")
    st.markdown(f"**Logged in as:** {st.session_state['role']}")

    selected_class = st.selectbox("Academic Class", ["7", "8", "9", "10", "11", "12"])

    role = st.session_state["role"]
    if role == "Teacher":
        menu_options = [
            "Student Attendance",
            "Attendance Report",
            "Marks Entry",
            "Result Card",
            "Admit Card",
            "Student Records",
            "Edit Student Details",
            "Add New Student",
            "At-Risk Students"
        ]
    elif role == "Clerk":
        menu_options = [
            "Fee Collection",
            "Daily Cash Report",
            "Defaulter List",
            "Result Card",
            "Admit Card",
            "Add New Student",
            "Student Records"
        ]
    elif role == "Principal":
        menu_options = [
            "Executive Dashboard",
            "Student Attendance",
            "Attendance Report",
            "Fee Collection",
            "Daily Cash Report",
            "Defaulter List",
            "Marks Entry",
            "Result Card",
            "Admit Card",
            "Student Records",
            "Edit Student Details",
            "Add New Student",
            "At-Risk Students"
        ]
    else:
        st.error("Invalid role")
        st.stop()

    menu = st.radio("Navigation", menu_options, label_visibility="collapsed")

    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["role"] = None
        st.cache_data.clear()
        st.rerun()

    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# -----------------------------
# 6. LOAD CLASS DATA
# -----------------------------
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

# ── New sheets for Marks & Exam Schedule ──
marks_sheet = find_sheet("Marks_Entry")
exam_schedule_sheet = find_sheet("Exam_Schedule")

if not all([master_sheet, attendance_sheet, fees_sheet]):
    st.error("Required class sheets missing. Please check tab names.")
    st.stop()

# -----------------------------
# 7. BRANDING
# -----------------------------
st.markdown("<h1 style='text-align: center;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center;'>Administrative Management System</h4>", unsafe_allow_html=True)
st.divider()

# =============================
# 8. EXECUTIVE DASHBOARD (Principal)
# =============================
if menu == "Executive Dashboard" and role == "Principal":
    st.subheader(f"Executive Dashboard – Class {selected_class}")
    with st.spinner("Loading executive insights..."):
        if df_master.empty:
            st.warning("No student data.")
        else:
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

            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Total Students", total_students)
            col_b.metric("Today's Attendance", f"{attendance_pct:.1f}% ({present_today}/{total_students})")
            col_c.metric("Today's Fees Collected", f"INR {total_today_fees}")
            col_d.metric("This Month Collection", f"INR {month_collection} ({collection_pct:.0f}%)")

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Top 5 Defaulters (Outstanding)**")
                if not top_defaulters.empty:
                    st.dataframe(top_defaulters.reset_index(drop=True))
                else:
                    st.write("No defaulters.")
            with col2:
                st.write("**Dropout Risk**")
                st.metric("At-Risk Students (5+ consec. absences)", at_risk_count)

# =============================
# 9. STUDENT ATTENDANCE
# =============================
elif menu == "Student Attendance":
    st.subheader(f"Daily Attendance – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)

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
# 10. ATTENDANCE REPORT
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
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_rep.to_excel(writer, index=False, sheet_name='Attendance')
                st.download_button(
                    label="Download Excel Report",
                    data=buffer.getvalue(),
                    file_name=f"Attendance_Class{selected_class}_{sel_month}_{sel_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# =============================
# 11. FEE COLLECTION (with Receipt Printing)
# =============================
elif menu == "Fee Collection":
    if role not in ["Clerk", "Principal"]:
        st.error("Access Denied")
        st.stop()
    st.subheader(f"Fee Counter – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)
        if selected_student != "-- Select --":
            s_id = selected_student.split(" - ")[0]
            try:
                m_cell = master_sheet.find(s_id)
                m_row = master_sheet.row_values(m_cell.row)
                current_fees = int(m_row[6]) if len(m_row) >= 7 and str(m_row[6]).isdigit() else 0
                st.info(f"**Student:** {m_row[1]} | **Father:** {m_row[3]} | **Total Paid:** INR {current_fees}")

                with st.form("fee_form", clear_on_submit=True):
              
