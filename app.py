import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="RMM Portal v3", layout="wide")

# --- 2. SECURITY ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>Admin Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == "RMM2014":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Galat Password!")
        return False
    return True

if not check_password(): st.stop()

# --- 3. DATABASE CONNECTION ---
@st.cache_resource
def get_sheets_data():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        
        client = gspread.authorize(creds)
        
        # Aapki Sheet ID jo aapne bheji hai
        sheet_id = "1fiAOXJUCMk_dlKfUbW6syEEHRREaMAnNaDIe0X0wboo"
        wb = client.open_by_key(sheet_id)
        
        # Tabs load karein
        master = wb.worksheet("Master_Data")
        attendance = wb.worksheet("Attendance")
        fees = wb.worksheet("Fees_Data")
        
        return master, attendance, fees
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None, None, None

# Variables mein sheets ko pakadna
master_sheet, attendance_sheet, fees_sheet = get_sheets_data()

# Agar data nahi mila toh app yahi rok do
if master_sheet is None:
    st.warning("⚠️ Google Sheet connect nahi ho payi. Check karein ki apne Service Account Email ko Sheet mein 'Editor' banaya hai.")
    st.stop()

# --- 4. UI ---
st.title("🏫 RAM MURTI MISHRA INTER COLLEGE")
choice = st.sidebar.radio("Main Menu", ["Haziri (Attendance)", "Fees Jama Karein", "Student Khojein"])

# --- FEATURE 1: ATTENDANCE ---
if choice == "Haziri (Attendance)":
    st.subheader("📝 Daily Attendance (Manual Entry)")
    s_id = st.text_input("Student ID Daalein (e.g. RMM001)").upper()
    
    if st.button("Mark Present"):
        if s_id:
            try:
                today = datetime.now().strftime("%d-%m-%Y")
                headers = attendance_sheet.row_values(1)
                
                # Check/Create Date Column
                if today not in headers:
                    col_idx = len(headers) + 1
                    attendance_sheet.update_cell(1, col_idx, today)
                else:
                    col_idx = headers.index(today) + 1
                
                cell = attendance_sheet.find(s_id)
                if cell:
                    attendance_sheet.update_cell(cell.row, col_idx, "P")
                    st.success(f"✅ {s_id} ki Haziri lag gayi!")
                else:
                    st.error("❌ Ye ID Master List mein nahi mili!")
            except Exception as e: st.error(f"Error: {e}")

# --- FEATURE 2: FEES (WITH AUTO-TOTAL) ---
elif choice == "Fees Jama Karein":
    st.subheader("💰 Fees Collection System")
    with st.form("fees_form"):
        f_id = st.text_input("Student ID").upper()
        amt = st.number_input("Amount (Rupees)", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        
        if st.form_submit_button("Fees Update Karein"):
            try:
                master_cell = master_sheet.find(f_id)
                if master_cell:
                    current_data = master_sheet.row_values(master_cell.row)
                    # TOTAL_FEES_PAID Column G (index 7)
                    old_total = int(current_data[6]) if len(current_data) >= 7 and str(current_data[6]).isdigit() else 0
                    new_total = old_total + amt
                    
                    # Update Master Total
                    master_sheet.update_cell(master_cell.row, 7, str(new_total))
                    # Log in Fees_Data
                    fees_sheet.append_row([f_id, amt, month, datetime.now().strftime("%d-%m-%Y %H:%M")])
                    
                    st.success(f"✅ ₹{amt} Jama ho gaye! Naya Total: ₹{new_total}")
                else:
                    st.error("❌ Student ID nahi mili.")
            except Exception as e: st.error(f"Error: {e}")

# --- FEATURE 3: SEARCH ---
elif choice == "Student Khojein":
    st.subheader("🔍 Student Record & Fees History")
    search_id = st.text_input("Student ID Daalein").upper()
    
    if st.button("Search Details"):
        try:
            all_students = master_sheet.get_all_values()
            student_row = next((r for r in all_students if r[0].upper() == search_id), None)
            
            if student_row:
                st.info(f"### Student: {student_row[1]}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Roll No:** {student_row[2]}")
                    st.write(f"**Father's Name:** {student_row[3]}")
                    st.write(f"**Class:** {student_row[5] if len(student_row)>5 else 'N/A'}")
                with col2:
                    st.write(f"**Mobile:** {student_row[4] if len(student_row)>4 else 'N/A'}")
                    st.markdown(f"### 💰 Total Fees Paid: ₹{student_row[6] if len(student_row)>6 else '0'}")
                
                st.divider()
                st.write("#### Recent Fees Transactions")
                all_fees = fees_sheet.get_all_values()
                history = [r for r in all_fees if r[0].upper() == search_id]
                if history:
                    st.table(history)
                else:
                    st.write("Abhi tak koi fees jama nahi hui.")
            else:
                st.warning("ID galat hai ya data available nahi hai.")
        except Exception as e: st.error(f"Error: {e}")
