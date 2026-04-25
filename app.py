import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cv2
import numpy as np
import pandas as pd
import os
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, RTCConfiguration

# --- RTC CONFIGURATION (Cloud par camera chalane ke liye zaroori hai) ---
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# --- PAGE CONFIG ---
st.set_page_config(page_title="RMM Inter College Portal", layout="wide")

# --- 1. SECURITY (ADMIN LOGIN) ---
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

# --- 2. DATABASE CONNECTION ---
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

# --- ATTENDANCE LOGIC ---
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

# --- 🆕 FIX: AUTO-SCANNER PROCESSOR ---
class QRProcessor(VideoProcessorBase):
    def __init__(self):
        self.detector = cv2.QRCodeDetector()

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        data, _, _ = self.detector.detectAndDecode(img)
        if data:
            s_id = data.split('id=')[-1].strip().upper() if 'id=' in data else data.strip().upper()
            # Storing in session state
            st.session_state["detected_id"] = s_id
        return frame

# --- UI ---
st.markdown("<h1 style='text-align: center; color: #1a73e8;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.divider()

choice = st.sidebar.radio("Main Menu", ["Attendance", "Fees Management", "Search Student Info"])

if choice == "Attendance":
    st.subheader("📝 Live Attendance (Auto-Scan)")
    tabs = st.tabs(["📷 Auto Scanner", "⌨️ Manual Entry"])
    
    with tabs[0]:
        st.info("Niche 'Start' button dabaiye aur QR code camera ke samne laaiye.")
        # Added rtc_configuration and video_hints for better mobile support
        ctx = webrtc_streamer(
            key="qr-scanner",
            video_processor_factory=QRProcessor,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"video": True, "audio": False},
            video_html_attrs={"style": {"width": "100%", "margin": "0 auto"}, "controls": False, "autoPlay": True},
        )

        # Check if ID was detected
        if "detected_id" in st.session_state:
            res_id = st.session_state["detected_id"]
            st.success(f"🔍 QR Detected: **{res_id}**")
            if st.button(f"Mark Attendance for {res_id}"):
                success, msg = mark_attendance_logic(res_id)
                if success:
                    st.success(f"✅ Marked Present!")
                    st.balloons()
                    del st.session_state["detected_id"]
                else:
                    st.error(f"Error: {msg}")

    with tabs[1]:
        with st.form("manual"):
            m_id = st.text_input("Enter ID").upper()
            if st.form_submit_button("Mark"):
                s, m = mark_attendance_logic(m_id)
                if s: st.success(f"Done for {m}")
                else: st.error(m)

# ... (Search aur Fees management ka code same rahega)
