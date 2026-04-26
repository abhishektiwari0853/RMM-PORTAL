import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime
import cv2
import numpy as np
from pyzbar.pyzbar import decode

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
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        return gspread.authorize(creds).open_by_key("14tEcfJ6j9hVZ76_69rkAoTZC0MpxdtlXemYcl8oacmI").sheet1
    except Exception as e:
        st.error(f"Sheet Connection Error: {e}")
        return None

sheet = get_sheet_connection()

# --- 4. ATTENDANCE LOGIC ---
def mark_attendance_logic(student_id):
    try:
        today_date = datetime.now().strftime("%d-%m-%Y")
        headers = sheet.row_values(1)
        
        if today_date not in headers:
            col_idx = len(headers) + 1
            sheet.update_cell(1, col_idx, today_date)
        else:
            col_idx = headers.index(today_date) + 1
        
        cell = sheet.find(student_id.upper())
        if cell:
            sheet.update_cell(cell.row, col_idx, "P")
            return True, today_date
        return False, "ID Database mein nahi mili!"
    except Exception as e:
        return False, str(e)

# --- 5. UI ---
st.markdown("<h1 style='text-align: center; color: #1a73e8;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.divider()

choice = st.sidebar.radio("Main Menu", ["Attendance", "Fees Management", "Search Student Info"])
if st.sidebar.button("Logout"):
    del st.session_state["password_correct"]
    st.rerun()

if choice == "Attendance":
    st.subheader("📝 Attendance System")
    tabs = st.tabs(["📷 QR Scanner", "⌨️ Manual Entry"])
    
    with tabs[0]:
        img_file = st.camera_input("Student ka QR Scan Karein")
        if img_file:
            # QR Process karein
            file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
            opencv_img = cv2.imdecode(file_bytes, 1)
            decoded_objects = decode(opencv_img)
            
            if decoded_objects:
                qr_data = decoded_objects[0].data.decode("utf-8")
                res_id = qr_data.split('id=')[-1].strip().upper() if 'id=' in qr_data else qr_data.strip().upper()
                st.success(f"🎯 Detected ID: **{res_id}**")
                
                if st.button(f"Mark Present for {res_id}"):
                    with st.spinner("Sheet update ho rahi hai..."):
                        success, msg = mark_attendance_logic(res_id)
                        if success:
                            st.success(f"✅ {res_id} ki attendance lag gayi!")
                            st.balloons()
                        else:
                            st.error(f"❌ Error: {msg}")
            else:
                st.warning("QR Code saaf nahi dikh raha, fir se koshish karein.")

    with tabs[1]:
        with st.form("manual"):
            m_id = st.text_input("Student ID Enter Karein").upper()
            if st.form_submit_button("Attendance Lagao"):
                s, m = mark_attendance_logic(m_id)
                if s: st.success(f"✅ {m_id} Present Mark!")
                else: st.error(m)

elif choice == "Fees Management":
    st.subheader("💰 Fees Deposit")
    with st.form("fees"):
        f_id = st.text_input("Student ID").upper()
        amt = st.number_input("Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        if st.form_submit_button("Update Fees"):
            try:
                cell = sheet.find(f_id)
                sheet.update_cell(cell.row, 8, f"{amt} ({month})")
                st.success("✅ Fees Update Ho Gayi!")
            except:
                st.error("❌ Student ID nahi mili!")

elif choice == "Search Student Info":
    st.subheader("🔍 Search Record")
    search_id = st.text_input("Enter ID:").upper()
    if st.button("Search"):
        try:
            data = sheet.get_all_values()
            df = pd.DataFrame(data[1:], columns=data[0])
            res = df[df.iloc[:, 0].str.upper() == search_id]
            if not res.empty:
                st.dataframe(res, use_container_width=True)
            else:
                st.warning("❌ Record nahi mila.")
        except Exception as e:
            st.error(f"Error: {e}")
