import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import traceback

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
st.set_page_config(page_title="RMM Administrative Portal", page_icon="🏫", layout="wide")

# -----------------------------
# 2. DUAL-LAYER SECURITY
# -----------------------------
def check_main_password():
    if "main_auth" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>School Portal Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Portal Password", type="password")
        if st.button("Access Portal"):
            if pwd == "RMM2014":
                st.session_state["main_auth"] = True
                st.rerun()
            else:
                st.error("Invalid Password")
        return False
    return True

def check_office_access():
    if "office_auth" not in st.session_state:
        st.warning("Restricted: Office PIN required for financial operations.")
        pin = st.text_input("Enter Office PIN", type="password", key="office_pin")
        if st.button("Unlock Office Desk"):
            if pin == "OFFICE786":
                st.session_state["office_auth"] = True
                st.rerun()
            else:
                st.error("Incorrect PIN")
        return False
    return True

if not check_main_password():
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
# 4. SMART SHEET FINDER (Robust against typos)
# -----------------------------
def find_class_sheet(class_num, sheet_type):
    """
    sheet_type: 'Master', 'Attendance', 'Fees'
    Returns the worksheet object, or None.
    Searches by exact match first, then falls back to partial matching.
    """
    all_sheets = wb.worksheets()
    exact_name = f"{sheet_type}_{class_num}"
    
    # Try exact match first (strip spaces)
    for ws in all_sheets:
        if ws.title.strip() == exact_name:
            return ws
    
    # Fallback: partial match – e.g., 'Attendence_8' should match
    for ws in all_sheets:
        title_lower = ws.title.strip().lower()
        if sheet_type.lower() == 'attendance':
            if 'attend' in title_lower and str(class_num) in title_lower:
                return ws
        elif sheet_type.lower() == 'master':
            if 'master' in title_lower and str(class_num) in title_lower:
                return ws
        elif sheet_type.lower() == 'fees':
            if 'fees' in title_lower and str(class_num) in title_lower:
                return ws
    return None

# -----------------------------
# 5. SIDEBAR & NAVIGATION
# -----------------------------
st.sidebar.header("Administration Panel")
selected_class = st.sidebar.selectbox("Academic Class", ["7", "8", "9", "10", "11", "12"])
menu = st.sidebar.radio("Navigation", [
    "Student Attendance",
    "Fee Collection",
    "Daily Cash Report",
    "Student Records"
])

if "office_auth" in st.session_state:
    if st.sidebar.button("Lock Office Sections"):
        del st.session_state["office_auth"]
        st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# -----------------------------
# 6. LOAD CLASS SHEETS (SMART MATCHING)
# -----------------------------
try:
    master_sheet = find_class_sheet(selected_class, 'Master')
    attendance_sheet = find_class_sheet(selected_class, 'Attendance')
    fees_sheet = find_class_sheet(selected_class, 'Fees')

    missing = []
    if not master_sheet: missing.append('Master')
    if not attendance_sheet: missing.append('Attendance')
    if not fees_sheet: missing.append('Fees')
    if missing:
        st.error(f"❌ Could not find {', '.join(missing)} sheets for Class {selected_class}. "
                 f"Please check tab names. Available tabs: {[ws.title for ws in wb.worksheets()]}")
        st.stop()

    # Now read data safely (duplicate headers allowed)
    raw_data = master_sheet.get_all_values()
    if len(raw_data) < 2:
        st.warning("Master sheet has no data rows. Please add students and headers.")
        student_list = []
    else:
        headers = raw_data[0]
        df_master = pd.DataFrame(raw_data[1:], columns=headers)

        # Case‑insensitive column search for 'Student ID' and 'Name'
        id_col = next((c for c in df_master.columns if c.strip().lower() == 'student id'), None)
        name_col = next((c for c in df_master.columns if c.strip().lower() == 'name'), None)
        if id_col and name_col:
            student_list = [f"{row[id_col]} - {row[name_col]}" for _, row in df_master.iterrows()]
        else:
            st.error("Master sheet must contain 'Student ID' and 'Name' columns.")
            student_list = []
except Exception as e:
    st.error(f"❌ Error loading sheets for Class {selected_class}:\n\n{e}\n\n{traceback.format_exc()}")
    st.stop()

# -----------------------------
# 7. BRANDING (Top Centre Logo)
# -----------------------------
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("School_logo.png", width=180)
    except:
        st.caption("School Logo not found")

st.markdown("<h1 style='text-align: center;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: gray;'>Administrative Management System</h4>", unsafe_allow_html=True)
st.divider()

# =============================
# 8. MODULE 1 – ATTENDANCE
# =============================
if menu == "Student Attendance":
    st.subheader(f"Daily Attendance – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)
        if st.button("Mark Present"):
            if selected_student == "-- Select --":
                st.warning("Please select a student first.")
            else:
                s_id = selected_student.split(" - ")[0]
                try:
                    today = datetime.now().strftime("%d-%m-%Y")
                    headers = attendance_sheet.row_values(1)
                    col_idx = headers.index(today) + 1 if today in headers else len(headers) + 1
                    if today not in headers:
                        attendance_sheet.update_cell(1, col_idx, today)
                    cell = attendance_sheet.find(s_id)
                    attendance_sheet.update_cell(cell.row, col_idx, "P")
                    st.success(f"Present marked for {selected_student} on {today}")
                except Exception as e:
                    st.error(f"Update failed: {e}")

# =============================
# 9. MODULE 2 – FEE COLLECTION
# =============================
elif menu == "Fee Collection":
    if check_office_access():
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
                    st.info(f"**Student:** {m_row[1]} | **Father:** {m_row[3]} | **Total Paid:** ₹{current_fees}")
                    with st.form("fee_form", clear_on_submit=True):
                        amount = st.number_input("Amount Received", min_value=0)
                        month = st.selectbox("Month", [
                            "April","May","June","July","August","September",
                            "October","November","December","January","February","March"
                        ])
                        payment_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque"])
                        if st.form_submit_button("Process Payment"):
                            new_total = current_fees + amount
                            master_sheet.update_cell(m_cell.row, 7, str(new_total))
                            timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")
                            combined_date = f"{timestamp} {payment_mode}"
                            fees_sheet.insert_row([s_id, amount, month, combined_date], index=2)
                            st.success(f"Payment of ₹{amount} recorded. New Total: ₹{new_total}")
                except Exception as e:
                    st.error(f"Error: {e}")

# =============================
# 10. MODULE 3 – DAILY CASH REPORT
# =============================
elif menu == "Daily Cash Report":
    if check_office_access():
        st.subheader(f"Today's Financial Summary – Class {selected_class}")
        today_date = datetime.now().strftime("%d-%m-%Y")
        try:
            data = fees_sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                if 'Date of payment' in df.columns:
                    df['Date'] = df['Date of payment'].apply(lambda x: str(x).split(' ')[0] if x else "")
                    today_df = df[df['Date'] == today_date]
                    if today_df.empty:
                        st.info("No transactions recorded today.")
                    else:
                        total_amount = today_df['Amount'].sum()
                        st.metric("Total Collection Today", f"₹{total_amount}")
                        st.dataframe(today_df[['Student ID','Amount','Month','Date of payment']])
                else:
                    st.error("Fees sheet missing 'Date of payment' column.")
            else:
                st.info("No fee records yet.")
        except Exception as e:
            st.error(f"Error: {e}")

# =============================
# 11. MODULE 4 – STUDENT RECORDS
# =============================
elif menu == "Student Records":
    st.subheader(f"Student Profile – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)
        if selected_student != "-- Select --":
            s_id = selected_student.split(" - ")[0]
            try:
                student_data = df_master[df_master['Student ID'].astype(str) == s_id].iloc[0]
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
                    st.markdown(f"### Total Fees Paid: ₹{total_fees}")
                st.divider()
                st.subheader("Fee Payment History")
                all_fee_records = fees_sheet.get_all_values()
                history = [r for r in all_fee_records[1:] if r[0].upper() == s_id.upper()]
                if history:
                    st.table([all_fee_records[0]] + history)
                else:
                    st.write("No payment history found.")
            except Exception as e:
                st.warning(f"Error: {e}")
