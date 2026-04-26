import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="RMM Administrative Portal", layout="wide")

# --- 2. AUTHENTICATION SYSTEM ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>Administrator Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Access Password", type="password")
        if st.button("Authenticate"):
            if pwd == "RMM2014":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Invalid credentials. Access denied.")
        return False
    return True

if not check_password(): st.stop()

# --- 3. DATABASE INTEGRATION ---
@st.cache_resource
def get_sheets_data():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        
        client = gspread.authorize(creds)
        sheet_id = "1fiAOXJUCMk_dlKfUbW6syEEHRREaMAnNaDIe0X0wboo"
        wb = client.open_by_key(sheet_id)
        
        master = wb.worksheet("Master_Data")
        attendance = wb.worksheet("Attendance")
        fees = wb.worksheet("Fees_Data")
        
        return master, attendance, fees
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return None, None, None

master_sheet, attendance_sheet, fees_sheet = get_sheets_data()

if master_sheet is None:
    st.stop()

# --- 4. HEADER AND BRANDING ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("School_logo.png", width=180)
    except:
        st.caption("Information: Branding asset 'School_logo.png' not detected.")

st.markdown("<h1 style='text-align: center;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: gray;'>Administrative Management System</h4>", unsafe_allow_html=True)
st.divider()

# --- NAVIGATION MENU ---
choice = st.sidebar.radio("Navigation Menu", ["Student Attendance", "Fee Collection", "Student Records"])

# --- MODULE 1: STUDENT ATTENDANCE ---
if choice == "Student Attendance":
    st.subheader("Daily Attendance Registry")
    s_id = st.text_input("Enter Student ID").upper()
    if st.button("Register Presence"):
        if s_id:
            try:
                today = datetime.now().strftime("%d-%m-%Y")
                headers = attendance_sheet.row_values(1)
                if today not in headers:
                    col_idx = len(headers) + 1
                    attendance_sheet.update_cell(1, col_idx, today)
                else:
                    col_idx = headers.index(today) + 1
                
                cell = attendance_sheet.find(s_id)
                if cell:
                    attendance_sheet.update_cell(cell.row, col_idx, "P")
                    st.success(f"Status Updated: Student {s_id} marked Present for {today}.")
                else:
                    st.error("Error: Student ID not found in Master Registry.")
            except Exception as e: st.error(f"Operational Error: {e}")

# --- MODULE 2: FEE COLLECTION ---
elif choice == "Fee Collection":
    st.subheader("Fee Transaction Management")
    with st.form("fee_form"):
        f_id = st.text_input("Enter Student ID").upper()
        amt = st.number_input("Transaction Amount", min_value=0)
        month = st.selectbox("Billing Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        
        if st.form_submit_button("Process Transaction"):
            if f_id and amt > 0:
                try:
                    master_cell = master_sheet.find(f_id)
                    if master_cell:
                        row_data = master_sheet.row_values(master_cell.row)
                        
                        # Total Fees Calculation (Column G / Index 6)
                        current_fees = 0
                        if len(row_data) >= 7:
                            val = str(row_data[6]).strip()
                            current_fees = int(val) if val.isdigit() else 0
                        
                        new_total = current_fees + amt
                        
                        # Synchronize Master Data
                        master_sheet.update_cell(master_cell.row, 7, str(new_total))
                        
                        # Update Transaction History
                        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")
                        fees_sheet.insert_row([f_id, amt, month, timestamp], index=2)
                        
                        st.success(f"Transaction Successful. Updated Total Balance: INR {new_total}")
                    else:
                        st.error("Error: Student ID not found.")
                except Exception as e: st.error(f"Processing Error: {e}")

# --- MODULE 3: STUDENT RECORDS ---
elif choice == "Student Records":
    st.subheader("Student Database Search")
    search_id = st.text_input("Search by Student ID").upper()
    
    if st.button("Retrieve Information"):
        try:
            records = master_sheet.get_all_values()
            student_row = next((r for r in records if r[0].upper() == search_id), None)
            
            if student_row:
                # Mapping: A:ID, B:Name, C:Roll, D:Father, E:NA, F:Mobile, G:Fees, H:Address
                name = student_row[1] if len(student_row) > 1 else "N/A"
                roll = student_row[2] if len(student_row) > 2 else "N/A"
                father = student_row[3] if len(student_row) > 3 else "N/A"
                mobile = student_row[5] if len(student_row) > 5 else "N/A" 
                total_fees = student_row[6] if len(student_row) > 6 else "0" 
                address = student_row[7] if len(student_row) > 7 else "N/A"
                
                st.info(f"Student Profile: {name}")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Roll Number:** {roll}")
                    st.write(f"**Guardian Name:** {father}")
                    st.write(f"**Residential Address:** {address}")
                with c2:
                    st.write(f"**Contact Number:** {mobile}")
                    st.markdown(f"### Total Fees Received: INR {total_fees}")
                
                st.divider()
                st.subheader("Transaction History")
                all_fees = fees_sheet.get_all_values()
                hist = [r for r in all_fees if r[0].upper() == search_id]
                if hist:
                    st.table(hist)
                else:
                    st.write("No recorded transactions found for this ID.")
            else:
                st.warning("Query Result: No record matching the provided ID.")
        except Exception as e: st.error(f"Search Error: {e}")
