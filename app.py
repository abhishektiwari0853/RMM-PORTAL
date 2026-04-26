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
        sheet_id = "1fiAOXJUCMk_dlKfUbW6syEEHRREaMAnNaDIe0X0wboo"
        wb = client.open_by_key(sheet_id)
        
        master = wb.worksheet("Master_Data")
        attendance = wb.worksheet("Attendance")
        fees = wb.worksheet("Fees_Data")
        
        return master, attendance, fees
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None, None, None

master_sheet, attendance_sheet, fees_sheet = get_sheets_data()

if master_sheet is None:
    st.stop()

# --- 4. UI ---
st.title("🏫 RAM MURTI MISHRA INTER COLLEGE")
choice = st.sidebar.radio("Main Menu", ["Haziri (Attendance)", "Fees Jama Karein", "Student Khojein"])

# --- ATTENDANCE ---
if choice == "Haziri (Attendance)":
    st.subheader("📝 Daily Attendance")
    s_id = st.text_input("Student ID").upper()
    if st.button("Mark Present"):
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
                    st.success(f"✅ {s_id} marked Present!")
                else:
                    st.error("❌ ID nahi mili!")
            except Exception as e: st.error(f"Error: {e}")

# --- FEES (FORCED DOUBLE UPDATE) ---
elif choice == "Fees Jama Karein":
    st.subheader("💰 Fees Collection")
    with st.form("fees_form"):
        f_id = st.text_input("Student ID").upper()
        amt = st.number_input("Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        
        if st.form_submit_button("Fees Update Karein"):
            if f_id and amt > 0:
                try:
                    # STEP 1: Master Data Update
                    master_cell = master_sheet.find(f_id)
                    if master_cell:
                        row_data = master_sheet.row_values(master_cell.row)
                        current_fees = 0
                        if len(row_data) >= 7:
                            val = str(row_data[6]).strip()
                            current_fees = int(val) if val.isdigit() else 0
                        
                        new_total = current_fees + amt
                        master_sheet.update_cell(master_cell.row, 7, str(new_total))
                        
                        # STEP 2: Fees_Data Update (Try Insert)
                        try:
                            timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")
                            # Insert row at the end
                            fees_sheet.insert_row([f_id, amt, month, timestamp], index=2) 
                            st.success(f"✅ Master aur History dono update ho gaye! Naya Total: ₹{new_total}")
                        except Exception as fee_e:
                            st.warning(f"Master update ho gaya par History fail hui: {fee_e}")
                    else:
                        st.error("❌ ID Master List mein nahi mili!")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# --- SEARCH ---
elif choice == "Student Khojein":
    st.subheader("🔍 Student Record")
    search_id = st.text_input("Student ID").upper()
    
    if st.button("Search Details"):
        try:
            records = master_sheet.get_all_values()
            student_row = next((r for r in records if r[0].upper() == search_id), None)
            
            if student_row:
                name = student_row[1] if len(student_row) > 1 else "N/A"
                roll = student_row[2] if len(student_row) > 2 else "N/A"
                father = student_row[3] if len(student_row) > 3 else "N/A"
                mobile = student_row[5] if len(student_row) > 5 else "N/A" 
                total_fees = student_row[6] if len(student_row) > 6 else "0" 
                address = student_row[7] if len(student_row) > 7 else "N/A"
                
                st.info(f"### Student: {name}")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Roll No:** {roll}")
                    st.write(f"**Father:** {father}")
                    st.write(f"**Address:** {address}")
                with c2:
                    st.write(f"**Mobile:** {mobile}")
                    st.markdown(f"### 💰 Total Fees Paid: ₹{total_fees}")
                
                st.divider()
                st.write("#### History (Fees_Data Tab)")
                all_fees = fees_sheet.get_all_values()
                hist = [r for r in all_fees if r[0].upper() == search_id]
                if hist:
                    st.table(hist)
                else:
                    st.write("History tab mein koi record nahi mila.")
            else:
                st.warning("ID not found.")
        except Exception as e: st.error(e)
