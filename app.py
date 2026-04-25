import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cv2
import numpy as np
import pandas as pd
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="RMM Inter College Portal", layout="wide")

# --- 1. SECURITY (ADMIN LOGIN) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>Admin Login</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            st.text_input("Password Daalo", type="password", key="password_input")
            if st.button("Login"):
                if st.session_state["password_input"] == "RMM2014":
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
        st.error(f"Database Connection Error: {e}")
        return None

sheet = get_sheet_connection()

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
choice = st.sidebar.radio("Main Menu", ["Attendance Scanner", "Fees Management", "Search Student Info"])
if st.sidebar.button("Logout"):
    del st.session_state["password_correct"]
    st.rerun()

# --- 5. ATTENDANCE SCANNER ---
if choice == "Attendance Scanner":
    st.subheader("⚡ Smart QR Attendance")
    img_file = st.camera_input("Scan Student QR")
    if img_file:
        file_bytes = np.asarray(bytearray(img_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data:
            s_id = data.split('id=')[-1].strip().upper() if 'id=' in data else data.strip().upper()
            try:
                cell = sheet.find(s_id)
                sheet.update_cell(cell.row, 7, "P") 
                st.success(f"✅ Attendance Marked: {s_id}")
                st.balloons()
            except:
                st.error(f"❌ ID '{s_id}' nahi mili!")

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
            except:
                st.error("❌ ID galat hai!")

# --- 7. SEARCH STUDENT INFO (Fix for Duplicate Columns) ---
elif choice == "Search Student Info":
    st.subheader("🔍 Student Record Search")
    search_id = st.text_input("Enter Student ID:").upper()
    
    if st.button("Search"):
        if search_id:
            try:
                all_values = sheet.get_all_values()
                if all_values:
                    # Header row le rahe hain
                    headers = all_values[0]
                    # Duplicates handle karne ke liye headers ko rename kar rahe hain
                    clean_headers = []
                    counts = {}
                    for h in headers:
                        if not h: h = "Unnamed" # Khali headers ke liye
                        if h in counts:
                            counts[h] += 1
                            clean_headers.append(f"{h}_{counts[h]}")
                        else:
                            counts[h] = 0
                            clean_headers.append(h)

                    df = pd.DataFrame(all_values[1:], columns=clean_headers)
                    
                    # Pehla column search ke liye
                    id_col = df.columns[0]
                    result = df[df[id_col].astype(str).str.upper() == search_id]
                    
                    if not result.empty:
                        st.write("### Student Details Found:")
                        st.dataframe(result, use_container_width=True)
                    else:
                        st.warning(f"❌ Student ID '{search_id}' nahi mili.")
                else:
                    st.error("Sheet khaali hai!")
            except Exception as e:
                st.error(f"Error: {e}")
