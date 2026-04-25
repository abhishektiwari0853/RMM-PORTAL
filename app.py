import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cv2
import numpy as np
import os
import json

# --- PAGE CONFIG ---
st.set_page_config(page_title="RMM Inter College Portal", layout="wide")

# --- GOOGLE SHEETS SETUP (Cloud Friendly) ---
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # LOCAL vs CLOUD check
    if "gcp_service_account" in st.secrets:
        # Jab app Streamlit Cloud par chalegi
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Jab app tere laptop (Local) par chalegi
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        
    client = gspread.authorize(creds)
    sheet = client.open_by_key("14tEcfJ6j9hVZ76_69rkAoTZC0MpxdtlXemYcl8oacmI").sheet1
except Exception as e:
    st.error("Database connection fail ho gaya. Secrets check karein!")

# --- HEADER WITH LOGO ---
logo_path = "School_logo.png"
col1, col2, col3 = st.columns([2.5, 1, 2.5])
with col2:
    if os.path.exists(logo_path):
        st.image(logo_path, width=130)
    else:
        st.write("🏫")

st.markdown("<h1 style='text-align: center; color: #1a73e8; margin-top: -10px;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 18px; margin-top: -20px;'>ESTABLISHED: 2014</p>", unsafe_allow_html=True)
st.divider()

# --- SIDEBAR ---
choice = st.sidebar.radio("Navigation", ["Attendance Scanner", "Fees Management"])

# --- 1. ATTENDANCE SCANNER ---
if choice == "Attendance Scanner":
    st.subheader("⚡ QR Attendance System")
    img_file = st.camera_input("Student ID card kheencho")
    
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        
        if data:
            s_id = data.split('id=')[-1].strip().upper()
            try:
                cell = sheet.find(s_id)
                sheet.update_cell(cell.row, 7, "P") # Column G
                st.success(f"✅ Attendance Marked: {s_id}")
                st.balloons()
            except:
                st.error("❌ ID nahi mili!")

# --- 2. FEES MANAGEMENT ---
elif choice == "Fees Management":
    st.subheader("💰 Fees Deposit System")
    with st.form("fees_form"):
        f_id = st.text_input("Enter Student ID").upper()
        amt = st.number_input("Fees Amount", min_value=0)
        month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
        submit = st.form_submit_button("Update Sheet")
        
        if submit:
            try:
                cell = sheet.find(f_id)
                sheet.update_cell(cell.row, 8, f"{amt} ({month})") # Column H
                st.success("✅ Fees Updated Successfully!")
            except:
                st.error("❌ ID galat hai ya Sheet accessible nahi hai.")
