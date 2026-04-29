import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import traceback
import re

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
# 4. SMART SHEET FINDER
# -----------------------------
def find_class_sheet(class_num, sheet_type):
    all_sheets = wb.worksheets()
    exact_name = f"{sheet_type}_{class_num}"
    for ws in all_sheets:
        if ws.title.strip() == exact_name:
            return ws
    for ws in all_sheets:
        title = ws.title.strip().lower()
        target = sheet_type.lower()
        if target == 'attendance' and 'attend' in title and str(class_num) in title:
            return ws
        elif target == 'master' and 'master' in title and str(class_num) in title:
            return ws
        elif target == 'fees' and 'fees' in title and str(class_num) in title:
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
    "Student Records",
    "Edit Student Details",
    "Add New Student"           # ← Naya feature
])

if "office_auth" in st.session_state:
    if st.sidebar.button("Lock Office Sections"):
        del st.session_state["office_auth"]
        st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# -----------------------------
# 6. LOAD CLASS SHEETS + STUDENT LIST
# -----------------------------
try:
    master_sheet = find_class_sheet(selected_class, 'Master')
    attendance_sheet = find_class_sheet(selected_class, 'Attendance')
    fees_sheet = find_class_sheet(selected_class, 'Fees')

    if not all([master_sheet, attendance_sheet, fees_sheet]):
        missing = []
        if not master_sheet: missing.append('Master')
        if not attendance_sheet: missing.append('Attendance')
        if not fees_sheet: missing.append('Fees')
        st.error(f"❌ Missing sheets for Class {selected_class}: {', '.join(missing)}")
        st.stop()

    raw_data = master_sheet.get_all_values()
    if len(raw_data) < 2:
        st.warning("Master sheet has no data rows. Please add students and headers.")
        student_list = []
        df_master = pd.DataFrame()
    else:
        headers = [h.strip() for h in raw_data[0]]
        df_master = pd.DataFrame(raw_data[1:], columns=headers)
        id_col = next((c for c in df_master.columns if c.lower() == 'student id'), None)
        name_col = next((c for c in df_master.columns if c.lower() == 'name'), None)
        if id_col and name_col:
            student_list = [f"{row[id_col]} - {row[name_col]}" for _, row in df_master.iterrows()]
        else:
            st.error("Master sheet must contain 'Student ID' and 'Name' columns.")
            student_list = []
except Exception as e:
    st.error(f"❌ Error loading sheets for Class {selected_class}:\n{e}\n{traceback.format_exc()}")
    st.stop()

# -----------------------------
# 7. BRANDING
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
# 8. ATTENDANCE
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
                    headers_att = attendance_sheet.row_values(1)
                    col_idx = headers_att.index(today) + 1 if today in headers_att else len(headers_att) + 1
                    if today not in headers_att:
                        attendance_sheet.update_cell(1, col_idx, today)
                    cell = attendance_sheet.find(s_id)
                    attendance_sheet.update_cell(cell.row, col_idx, "P")
                    st.success(f"Present marked for {selected_student} on {today}")
                except Exception as e:
                    st.error(f"Update failed: {e}")

# =============================
# 9. FEE COLLECTION
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
# 10. DAILY CASH REPORT
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
# 11. STUDENT RECORDS
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

# =============================
# 12. EDIT STUDENT DETAILS
# =============================
elif menu == "Edit Student Details":
    st.subheader(f"Edit Student Information – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Choose Student to Edit", ["-- Select --"] + student_list)
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
            except Exception as e:
                st.error(f"Error: {e}")

# =============================
# 13. ADD NEW STUDENT (AUTO ID & ROLL)
# =============================
elif menu == "Add New Student":
    st.subheader(f"Enroll New Student – Class {selected_class}")

    # Extract all IDs for this class to generate next ID
    existing_ids = []
    existing_rolls = []
    if not df_master.empty:
        # Get column names case-insensitive
        id_col_name = next((c for c in df_master.columns if c.lower() == 'student id'), None)
        roll_col_name = next((c for c in df_master.columns if c.lower() == 'roll no'), None)
        if id_col_name:
            existing_ids = df_master[id_col_name].astype(str).tolist()
        if roll_col_name:
            try:
                existing_rolls = df_master[roll_col_name].astype(int).tolist()
            except:
                existing_rolls = []

    # Auto-generate Student ID: RMEC + class + next number
    prefix = f"RMEC{selected_class}"
    max_seq = 0
    for sid in existing_ids:
        if sid.startswith(prefix):
            num_part = sid[len(prefix):]
            if num_part.isdigit():
                max_seq = max(max_seq, int(num_part))
    new_id = f"{prefix}{max_seq + 1:03d}"   # e.g., RMEC7001 if max was 0

    # Auto-generate Roll No: max existing + 1
    new_roll = 1
    if existing_rolls:
        new_roll = max(existing_rolls) + 1

    with st.form("add_student_form", clear_on_submit=True):
        st.markdown("**Student ID (auto‑generated)**")
        st.info(new_id)
        st.markdown("**Roll Number (auto‑generated)**")
        st.info(str(new_roll))
        new_name = st.text_input("Full Name *")
        new_father = st.text_input("Father's Name *")
        new_mobile = st.text_input("Mobile Number")
        new_address = st.text_input("Address")
        new_aadhaar = st.text_input("Aadhaar Number")
        st.markdown("*marked fields are mandatory")

        if st.form_submit_button("Enroll Student"):
            if not new_name.strip() or not new_father.strip():
                st.error("❌ Student Name and Father's Name are required.")
            else:
                # Prepare new row according to Master sheet column order
                # We know the column mapping: A-J: ID, Name, Roll No, Father Name, Node, Mobile, Total_Fees, Address, Node, Aadhar
                new_row = [
                    new_id,
                    new_name.strip(),
                    str(new_roll),
                    new_father.strip(),
                    "",                    # Node (blank)
                    new_mobile.strip() if new_mobile else "",
                    "0",                   # Total_Fees initially 0
                    new_address.strip() if new_address else "",
                    "",                    # second Node (blank)
                    new_aadhaar.strip() if new_aadhaar else ""
                ]
                try:
                    master_sheet.append_row(new_row, value_input_option='USER_ENTERED')
                    # Also add the new student to the Attendance sheet (just ID in first column)
                    attendance_sheet.append_row([new_id])

                    st.success(f"✅ Student {new_name} ({new_id}) enrolled successfully!")
                    st.balloons()
                    # Clear cache to refresh data next time
                    st.cache_resource.clear()
                    # Auto-refresh after 2 seconds
                    st.write("Refreshing data...")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to add student: {e}")
