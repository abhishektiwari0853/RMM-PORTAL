import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cv2
import numpy as np
import pandas as pd
import os
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase

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
            # Fixed the unterminated string error here
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        return client.open_by_key("14tEcfJ6j9hVZ76_69rkAoTZC0MpxdtlXemYcl8oacmI").sheet1
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return None

sheet = get_sheet_connection()

# --- DATE-WISE ATTENDANCE LOGIC ---
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
        return False, "ID Not Found"
    except Exception as e:
        return False, str(e)

# --- AUTO-SCANNER PROCESSOR ---
class QRProcessor(VideoProcessorBase):
    def __init__(self):
        self.detector = cv2.QRCodeDetector()

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        data, _, _ = self.detector.detectAndDecode(img)
        if data:
            s_id = data.split('id=')[-1].strip().upper() if 'id=' in data else data.strip().upper()
            st.session_state["scanned_id"] = s_id
        return frame

# --- 3. HEADER & LOGO ---
logo_path = "School_logo.png"
col1, col2, col3 = st.columns([2.5, 1, 2.5])
with col2:
    if os.path.exists(logo_path):
        st.image(logo_path, width=130)
    else:
        st.write("🏫")

st.markdown("<h1 style='text-align: center; color: #1a73e8; margin-top: -10px;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.divider()

# --- 4. NAVIGATION ---
choice = st.sidebar.radio("Main Menu", ["Attendance", "Fees Management", "Search Student Info"])
if st.sidebar.button("Logout"):
    del st.session_state["password_correct"]
    st.rerun()

# --- 5. ATTENDANCE ---
if choice == "Attendance":
    st.subheader("📝 Live Attendance (Auto-Scan)")
    tabs = st.tabs(["📷 Auto Scanner", "⌨️ Manual Entry"])
    
    with tabs[0]:
        st.info("Camera ke samne QR laaiye.")
        webrtc_streamer(key="qr-scanner", video_processor_factory=QRProcessor)
        
        if "scanned_id" in st.session_state:
            scanned_id = st.session_state["scanned_id"]
            st.success(f"🔍 QR Detected: **{scanned_id}**")
            if st.button(f"Mark Attendance for {scanned_id}"):
                success, msg = mark_attendance_logic(scanned_id)
                if success:
                    st.success(f"✅ Marked Present for {msg}")
                    st.balloons()
                    del st.session_state["scanned_id"] 
                else:
                    st.error(f"Error: {msg}")

    with tabs[1]:
        with st.form("manual_form", clear_on_submit=True):
            m_id = st.text_input("Enter Student ID").upper()
            if st.form_submit_button("Mark Present"):
                success, msg = mark_attendance_logic(m_id)
                if success: st.success(f"✅ Marked Present for {msg}")
                else: st.error(f"Error: {msg}")

# --- 6. FEES MANAGEMENT ---
elif choice == "Fees Management":
    st.subheader("💰 Fees Deposit")
    with st.form("fees_form"):
        f_id = st.text_input("Student ID").upper()
        amt = st.number_input("Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        if st.form_submit_button("Update"):
            try:
                cell = sheet.find(f_id)
                sheet.update_cell(cell.row, 8, f"{amt} ({month})")
                st.success("✅ Fees Updated!")
            except: st.error("❌ Student ID galat hai!")

# --- 7. SEARCH STUDENT INFO ---
elif choice == "Search Student Info":
    st.subheader("🔍 Student Record Search")
    search_id = st.text_input("Enter Student ID:").upper()
    if st.button("Search"):
        try:
            all_values = sheet.get_all_values()
            headers = all_values[0]
            clean_headers = []
            counts = {}
            for h in headers:
                if not h: h = "Unnamed"
                if h in counts:
                    counts[h] += 1
                    clean_headers.append(f"{h}_{counts[h]}")
                else:
                    counts[h] = 0
                    clean_headers.append(h)
            
            df = pd.DataFrame(all_values[1:], columns=clean_headers)
            result = df[df.iloc[:, 0].astype(str).str.upper() == search_id]
            if not result.empty: 
                st.write("### Student Record Found:")
                st.dataframe(result, use_container_width=True)
            else: 
                st.warning("❌ Record nahi mila.")
        except Exception as e: 
            st.error(f"Error: {e}")
