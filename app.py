import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
from streamlit_camera_qr import camera_qr

# --- 1. CONFIG ---
st.set_page_config(page_title="RMM Inter College Portal", layout="wide")

# --- 2. SECURITY ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>Admin Login</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            pwd = st.text_input("Password Daalo", type="password")
            if st.button("Login"):
                if pwd == "RMM2014":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ Galat Password!")
        return False
    return True

if not check_password():
    st.stop()

# --- 3. DATABASE CONNECTION ---
@st.cache_resource
def get_sheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        return client.open_by_key("14tEcfJ6j9hVZ76_69rkAoTZC0MpxdtlXemYcl8oacmI").sheet1
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return None

sheet = get_sheet_connection()

# --- 4. ATTENDANCE LOGIC ---
def mark_attendance_logic(student_id):
    try:
        today_date = datetime.now().strftime("%d-%m-%Y")
        headers = sheet.row_values(1)
        
        if today_date not in headers:
            new_col_index = len(headers) + 1
            sheet.update_cell(1, new_col_index, today_date)
            col_to_update = new_col_index
        else:
            col_to_update = headers.index(today_date) + 1
        
        cell = sheet.find(student_id)
        if cell:
            sheet.update_cell(cell.row, col_to_update, "P")
            return True, today_date
        return False, "ID Database mein nahi mili!"
    except Exception as e:
        return False, str(e)

# --- 5. UI DESIGN ---
st.markdown("<h1 style='text-align: center; color: #1a73e8;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.divider()

choice = st.sidebar.radio("Main Menu", ["Attendance", "Fees Management", "Search Student Info"])
if st.sidebar.button("Logout"):
    del st.session_state["password_correct"]
    st.rerun()

# --- FEATURE 1: ATTENDANCE ---
if choice == "Attendance":
    st.subheader("📝 Attendance System")
    tabs = st.tabs(["📷 QR Scanner", "⌨️ Manual Entry"])
    
    with tabs[0]:
        st.info("Scanner use karein. QR ko camera ke samne laayein.")
        qr_data = camera_qr(key='attendance_scanner')

        if qr_data:
            res_id = qr_data.split('id=')[-1].strip().upper() if 'id=' in qr_data else qr_data.strip().upper()
            st.success(f"🎯 Detected ID: **{res_id}**")
            
            if st.button(f"Confirm Attendance for {res_id}"):
                with st.spinner("Sheet Update ho rahi hai..."):
                    success, msg = mark_attendance_logic(res_id)
                    if success:
                        st.success(f"✅ {res_id} ki attendance lag gayi!")
                        st.balloons()
                    else:
                        st.error(f"❌ Error: {msg}")

    with tabs[1]:
        with st.form("manual_entry"):
            m_id = st.text_input("Student ID Enter Karein").upper()
            submit = st.form_submit_button("Attendance Lagao")
            if submit:
                s, m = mark_attendance_logic(m_id)
                if s: st.success(f"✅ {m_id} Present Mark Ho Gaya!")
                else: st.error(m)

# --- FEATURE 2: FEES MANAGEMENT ---
elif choice == "Fees Management":
    st.subheader("💰 Fees Deposit Section")
    with st.form("fees_form"):
        f_id = st.text_input("Student ID").upper()
        amt = st.number_input("Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        
        if st.form_submit_button("Update Fees"):
            try:
                cell = sheet.find(f_id)
                sheet.update_cell(cell.row, 8, f"{amt} ({month})")
                st.success(f"✅ {f_id} ki Fees Update ho gayi!")
            except:
                st.error("❌ Student ID nahi mili!")

# --- FEATURE 3: SEARCH STUDENT INFO ---
elif choice == "Search Student Info":
    st.subheader("🔍 Student Record Khojein")
    search_id = st.text_input("Enter Student ID:").upper()
    if st.button("Search"):
        try:
            data = sheet.get_all_values()
            df = pd.DataFrame(data[1:], columns=data[0])
            res = df[df.iloc[:, 0].str.upper() == search_id]
            if not res.empty:
                st.dataframe(res, use_container_width=True)
            else:
                st.warning("❌ Koi record nahi mila.")
        except Exception as e:
            st.error(f"Error: {e}")
