import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import cv2
import numpy as np
from pyzbar.pyzbar import decode

# --- 1. CONFIG ---
st.set_page_config(page_title="RMM Portal", layout="wide")

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

# --- 3. DATABASE ---
@st.cache_resource
def get_sheet_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        return gspread.authorize(creds).open_by_key("14tEcfJ6j9hVZ76_69rkAoTZC0MpxdtlXemYcl8oacmI").sheet1
    except: return None

sheet = get_sheet_connection()

# --- 4. LOGIC ---
def mark_attendance_logic(student_id):
    try:
        today = datetime.now().strftime("%d-%m-%Y")
        headers = sheet.row_values(1)
        if today not in headers:
            col_idx = len(headers) + 1
            sheet.update_cell(1, col_idx, today)
        else:
            col_idx = headers.index(today) + 1
        
        cell = sheet.find(student_id.upper())
        if cell:
            sheet.update_cell(cell.row, col_idx, "P")
            return True, today
        return False, "ID Not Found"
    except Exception as e: return False, str(e)

# --- 5. UI ---
st.title("RAM MURTI MISHRA INTER COLLEGE")
choice = st.sidebar.radio("Menu", ["Attendance", "Fees Management", "Search Student"])

if choice == "Attendance":
    st.subheader("📝 Attendance")
    t1, t2 = st.tabs(["📷 QR Scanner", "⌨️ Manual Entry"])
    with t1:
        img = st.camera_input("Scan QR")
        if img:
            file_bytes = np.asarray(bytearray(img.read()), dtype=np.uint8)
            decoded = decode(cv2.imdecode(file_bytes, 1))
            if decoded:
                res_id = decoded[0].data.decode("utf-8").split('id=')[-1].strip().upper()
                st.success(f"Detected: {res_id}")
                if st.button(f"Mark Present {res_id}"):
                    s, m = mark_attendance_logic(res_id)
                    if s: st.success("✅ Done!"); st.balloons()
                    else: st.error(m)
    with t2:
        m_id = st.text_input("Enter ID").upper()
        if st.button("Submit Attendance"):
            s, m = mark_attendance_logic(m_id)
            if s: st.success("✅ Done!")
            else: st.error(m)

elif choice == "Fees Management":
    st.subheader("💰 Fees Update")
    with st.form("fees"):
        f_id = st.text_input("ID").upper()
        amt = st.number_input("Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        if st.form_submit_button("Update"):
            try:
                cell = sheet.find(f_id)
                sheet.update_cell(cell.row, 8, f"{amt} ({month})")
                st.success("✅ Fees Updated!")
            except: st.error("ID Not Found")

elif choice == "Search Student":
    st.subheader("🔍 Student Information")
    s_id = st.text_input("Enter Student ID").upper()
    if st.button("Search Details"):
        try:
            all_data = sheet.get_all_values()
            headers = all_data[0]
            student_row = None
            for row in all_data[1:]:
                if row[0].upper() == s_id:
                    student_row = row
                    break
            
            if student_row:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Name:** {student_row[1]}")
                    st.write(f"**Father's Name:** {student_row[3]}")
                with col2:
                    st.write(f"**Mobile:** {student_row[5]}")
                    st.write(f"**Fees Status:** {student_row[7] if len(student_row)>7 else 'N/A'}")
                
                # Full Record in Table
                st.divider()
                st.write("### Full Record")
                st.table([headers, student_row])
            else:
                st.warning("❌ Is ID ka koi student nahi mila.")
        except Exception as e:
            st.error(f"Error: {e}")
