import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

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
    """Office PIN required for financial sections."""
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
        # Aapki Sheet ID
        return client.open_by_key("1fiAOXJUCMk_dlKfUbW6syEEHRREaMAnNaDIe0X0wboo")
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return None

wb = get_workbook()
if wb is None:
    st.stop()

# -----------------------------
# 4. SIDEBAR & NAVIGATION
# -----------------------------
st.sidebar.header("Administration Panel")
selected_class = st.sidebar.selectbox("Academic Class", ["7", "8", "9", "10", "11", "12"])
menu = st.sidebar.radio("Navigation", [
    "Student Attendance",
    "Fee Collection",
    "Daily Cash Report",
    "Student Records"
])

# Office lock button (visible only when unlocked)
if "office_auth" in st.session_state:
    if st.sidebar.button("Lock Office Sections"):
        del st.session_state["office_auth"]
        st.rerun()

# Full logout
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# -----------------------------
# 5. LOAD CLASS SHEETS
# -----------------------------
try:
    master_sheet = wb.worksheet(f"Master_{selected_class}")
    attendance_sheet = wb.worksheet(f"Attendance_{selected_class}")
    fees_sheet = wb.worksheet(f"Fees_{selected_class}")

    # Build student list for dropdown (ID - Name)
    all_records = master_sheet.get_all_records()
    df_master = pd.DataFrame(all_records)
    # Ensure column names exactly match your Master sheet headers
    student_list = [
        f"{row['Student ID']} - {row['Name']}"
        for _, row in df_master.iterrows()
    ]
except Exception as e:
    st.error(f"Classes sheets not found. Please ensure tabs exist: "
             f"`Master_{selected_class}`, `Attendance_{selected_class}`, `Fees_{selected_class}`")
    st.stop()

# -----------------------------
# 6. BRANDING (Top Centre Logo)
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
# 7. MODULE 1 – ATTENDANCE
# =============================
if menu == "Student Attendance":
    st.subheader(f"Daily Attendance – Class {selected_class}")
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
# 8. MODULE 2 – FEE COLLECTION
# =============================
elif menu == "Fee Collection":
    if check_office_access():
        st.subheader(f"Fee Counter – Class {selected_class}")
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
                        # Update master (Column G = index 7)
                        master_sheet.update_cell(m_cell.row, 7, str(new_total))

                        # Log into Fees sheet (combine timestamp + mode as per your sheet)
                        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")
                        combined_date = f"{timestamp} {payment_mode}"   # e.g., "27-04-2026 03:30 Cash"
                        fees_sheet.insert_row(
                            [s_id, amount, month, combined_date],
                            index=2
                        )
                        st.success(f"Payment of ₹{amount} recorded. New Total: ₹{new_total}")
            except Exception as e:
                st.error(f"Student ID not found or sheet error: {e}")

# =============================
# 9. MODULE 3 – DAILY CASH REPORT
# =============================
elif menu == "Daily Cash Report":
    if check_office_access():
        st.subheader(f"Today's Financial Summary – Class {selected_class}")
        today_date = datetime.now().strftime("%d-%m-%Y")
        try:
            # fees_sheet.get_all_records() returns dict with keys from first row headers
            data = fees_sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                # We have columns: Student ID, Amount, Month, Date of payment
                # Extract just the date part (before first space)
                df['Date'] = df['Date of payment'].apply(
                    lambda x: str(x).split(' ')[0] if x else ""
                )
                today_df = df[df['Date'] == today_date]

                if today_df.empty:
                    st.info("No transactions recorded today.")
                else:
                    total_amount = today_df['Amount'].sum()
                    st.metric("Total Collection Today", f"₹{total_amount}")
                    st.dataframe(today_df[['Student ID','Amount','Month','Date of payment']])
            else:
                st.info("No fee records yet.")
        except Exception as e:
            st.error(f"Error reading fee records: {e}")

# =============================
# 10. MODULE 4 – STUDENT RECORDS
# =============================
elif menu == "Student Records":
    st.subheader(f"Student Profile – Class {selected_class}")
    selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)

    if selected_student != "-- Select --":
        s_id = selected_student.split(" - ")[0]
        try:
            student_data = df_master[df_master['Student ID'].astype(str) == s_id].iloc[0]
            name = student_data.get('Name','')
            roll = student_data.get('Roll No','')
            father = student_data.get('Father Name','')
            mobile = student_data.get('Mobile','')
            total_fees = student_data.get('Total_Fees','0')
            address = student_data.get('Address','N/A')

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
            # Skip header row if present
            history = [r for r in all_fee_records[1:] if r[0].upper() == s_id.upper()]
            if history:
                # Display headers + history
                st.table([all_fee_records[0]] + history)
            else:
                st.write("No payment history found.")
        except Exception as e:
            st.warning(f"Student data not found or sheet misconfigured: {e}")
