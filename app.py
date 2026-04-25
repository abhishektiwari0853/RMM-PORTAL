import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cv2
import numpy as np
import pandas as pd
from pyzbar.pyzbar import decode
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, RTCConfiguration

# --- 1. RTC CONFIG ---
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

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
        return False, "ID Nahi Mili"
    except Exception as e:
        return False, str(e)

# --- 5. FAST PYZBAR PROCESSOR ---
class QRProcessor(VideoProcessorBase):
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        
        # PyZbar se turant detection
        barcodes = decode(img)
        
        for barcode in barcodes:
            data = barcode.data.decode('utf-8')
            if data:
                # ID extract karne ka logic
                s_id = data.split('id=')[-1].strip().upper() if 'id=' in data else data.strip().upper()
                st.session_state["detected_id"] = s_id
                
                # Green border for feedback
                (x, y, w, h) = barcode.rect
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        return frame

# --- 6. UI ---
st.markdown("<h1 style='text-align: center; color: #1a73e8;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.divider()

choice = st.sidebar.radio("Main Menu", ["Attendance", "Fees Management", "Search Student Info"])
if st.sidebar.button("Logout"):
    del st.session_state["password_correct"]
    st.rerun()

# --- FEATURE 1: ATTENDANCE ---
if choice == "Attendance":
    st.subheader("📝 Live Attendance (Fast Scan)")
    tabs = st.tabs(["📷 Auto Scanner", "⌨️ Manual Entry"])
    
    with tabs[0]:
        st.info("Scanner On Karein. PyZbar turant detect karega.")
        webrtc_streamer(
            key="pyzbar-scanner",
            video_processor_factory=QRProcessor,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

        if "detected_id" in st.session_state:
            res_id = st.session_state["detected_id"]
            st.success(f"🎯 Detected: **{res_id}**")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(f"Mark Present for {res_id}"):
                    success, msg = mark_attendance_logic(res_id)
                    if success:
                        st.success(f"✅ Attendance Marked!")
                        st.balloons()
                        del st.session_state["detected_id"]
                        st.rerun()
            with col_b:
                if st.button("Clear / Scan Again"):
                    del st.session_state["detected_id"]
                    st.rerun()

    with tabs[1]:
        with st.form("manual"):
            m_id = st.text_input("Enter Student ID").upper()
            if st.form_submit_button("Submit"):
                s, m = mark_attendance_logic(m_id)
                if s: st.success(f"✅ Attendance marked for {m}")
                else: st.error(m)

# --- FEATURE 2: FEES MANAGEMENT ---
elif choice == "Fees Management":
    st.subheader("💰 Fees Deposit")
    with st.form("fees"):
        f_id = st.text_input("Student ID").upper()
        amt = st.number_input("Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        if st.form_submit_button("Update"):
            try:
                cell = sheet.find(f_id)
                # Column 8 for fees
                sheet.update_cell(cell.row, 8, f"{amt} ({month})")
                st.success(f"✅ Fees Updated for {f_id}!")
            except:
                st.error("❌ Student ID nahi mili!")

# --- FEATURE 3: SEARCH STUDENT INFO ---
elif choice == "Search Student Info":
    st.subheader("🔍 Search Student Record")
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
