import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cv2
import numpy as np
import pandas as pd
import os
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, RTCConfiguration

# --- 1. RTC CONFIG (Standard STUN Server) ---
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

# --- 3. DB CONNECTION ---
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
        st.error(f"Database Error: {e}")
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

# --- 5. FAST QR PROCESSOR ---
class QRProcessor(VideoProcessorBase):
    def __init__(self):
        # Using a more robust detector
        self.detector = cv2.QRCodeDetector()

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        
        # QR Detection logic
        data, bbox, _ = self.detector.detectAndDecode(img)
        
        if data:
            # Clean ID from the QR
            s_id = data.split('id=')[-1].strip().upper() if 'id=' in data else data.strip().upper()
            st.session_state["detected_id"] = s_id
            
            # Draw green box on frame for feedback
            if bbox is not None:
                for i in range(len(bbox)):
                    cv2.line(img, tuple(bbox[i][0].astype(int)), tuple(bbox[(i+1)%len(bbox)][0].astype(int)), (0, 255, 0), 3)
        
        return frame

# --- 6. UI ---
st.markdown("<h1 style='text-align: center; color: #1a73e8;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.divider()

choice = st.sidebar.radio("Main Menu", ["Attendance", "Fees Management", "Search Student Info"])
if st.sidebar.button("Logout"):
    del st.session_state["password_correct"]
    st.rerun()

if choice == "Attendance":
    st.subheader("📝 Live Attendance (Auto-Scan)")
    tabs = st.tabs(["📷 Auto Scanner", "⌨️ Manual Entry"])
    
    with tabs[0]:
        st.info("Scanner On Karein. QR ko camera ke samne 2 second hold karein.")
        
        webrtc_streamer(
            key="qr-scanner",
            video_processor_factory=QRProcessor,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True, # Improved performance
        )

        # Persistence fix
        if "detected_id" in st.session_state:
            res_id = st.session_state["detected_id"]
            st.success(f"🎯 Detected: **{res_id}**")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(f"Mark Present for {res_id}"):
                    success, msg = mark_attendance_logic(res_id)
                    if success:
                        st.success(f"✅ Marked!")
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
                if s: st.success(f"Attendance marked for {m}")
                else: st.error(m)

elif choice == "Fees Management":
    st.subheader("💰 Fees Deposit")
    with st.form("fees"):
        f_id = st.text_input("Student ID").upper()
        amt = st.number_input("Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        if st.form_submit_button("Update"):
            try:
                cell = sheet.find(f_id)
                sheet.update_cell(cell.row, 8, f"{amt} ({month})")
                st.success("✅ Fees Updated!")
            except: st.error("❌ Student nahi mila!")

elif choice == "Search Student Info":
    st.subheader("🔍 Search Record")
    s_id = st.text_input("Enter ID:").upper()
    if st.button("Search"):
        try:
            data = sheet.get_all_values()
            df = pd.DataFrame(data[1:], columns=data[0])
            res = df[df.iloc[:, 0].str.upper() == s_id]
            if not res.empty:
                st.dataframe(res)
            else:
                st.warning("Nahi mila.")
        except Exception as e: st.error(e)
