import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="RMM School Portal", page_icon="🏫", layout="wide")

# --- 2. DUAL-LAYER SECURITY ---
def check_main_password():
    if "main_auth" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>School Portal Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Portal Password", type="password")
        if st.button("Access Portal"):
            if pwd == "RMM2014":
                st.session_state["main_auth"] = True
                st.rerun()
            else:
                st.error("Invalid Portal Password")
        return False
    return True

def check_office_access():
    if "office_auth" not in st.session_state:
        st.warning("🔒 Restricted: Office PIN Required to access financial data.")
        pin = st.text_input("Enter Office PIN", type="password", key="off_pin")
        if st.button("Unlock Office Sections"):
            if pin == "OFFICE786":
                st.session_state["office_auth"] = True
                st.rerun()
            else:
                st.error("Incorrect PIN")
        return False
    return True

if not check_main_password(): st.stop()

# --- 3. DATABASE CONNECTION ---
@st.cache_resource
def get_workbook():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        return client.open_by_key("1fiAOXJUCMk_dlKfUbW6syEEHRREaMAnNaDIe0X0wboo")
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return None

wb = get_workbook()
if wb is None: st.stop()

# --- 4. SIDEBAR & NAVIGATION ---
st.sidebar.header("RMM Admin Panel")
selected_class = st.sidebar.selectbox("Select Class", ["7", "8", "9", "10", "11", "12"])
menu = st.sidebar.radio("Navigation", ["Student Attendance", "Fee Collection", "Daily Cash Report", "Student Records"])

# Security Buttons
if "office_auth" in st.session_state:
    if st.sidebar.button("🔒 Lock Office Sections"):
        del st.session_state["office_auth"]
        st.rerun()

if st.sidebar.button("Logout System"):
    st.session_state.clear()
    st.rerun()

st.markdown(f"<h1 style='text-align: center;'>RMM INTER COLLEGE - CLASS {selected_class}</h1>", unsafe_allow_html=True)
st.divider()

# DYNAMIC SHEET LOADING
try:
    master_sheet = wb.worksheet(f"Master_{selected_class}")
    attendance_sheet = wb.worksheet(f"Attendance_{selected_class}")
    fees_sheet = wb.worksheet(f"Fees_{selected_class}")
except:
    st.error(f"Error: Sheets for Class {selected_class} not found. Please check Google Sheets.")
    st.stop()

# --- MODULE 1: ATTENDANCE (Teacher Access) ---
if menu == "Student Attendance":
    st.subheader("Daily Attendance Registry")
    s_id = st.text_input("Enter Student ID").upper()
    if st.button("Mark Present"):
        if s_id:
            try:
                today = datetime.now().strftime("%d-%m-%Y")
                headers = attendance_sheet.row_values(1)
                col_idx = headers.index(today) + 1 if today in headers else len(headers) + 1
                if today not in headers: attendance_sheet.update_cell(1, col_idx, today)
                
                cell = attendance_sheet.find(s_id)
                if cell:
                    attendance_sheet.update_cell(cell.row, col_idx, "P")
                    st.success(f"Student {s_id} marked Present for {today}")
                else: st.error("ID not found in this class.")
            except Exception as e: st.error(f"Error: {e}")

# --- MODULE 2: FEE COLLECTION (Office PIN Required) ---
elif menu == "Fee Collection":
    if check_office_access():
        st.subheader("Fee Counter")
        f_id = st.text_input("Enter Student ID").upper()
        if f_id:
            try:
                m_cell = master_sheet.find(f_id)
                m_row = master_sheet.row_values(m_cell.row)
                st.info(f"Student: {m_row[1]} | Father: {m_row[3]}")
                
                with st.form("fee_form", clear_on_submit=True):
                    amt = st.number_input("Amount Received", min_value=0)
                    month = st.selectbox("Month", ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"])
                    mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque"])
                    if st.form_submit_button("Submit & Update Record"):
                        # Update Master (Column G / Index 6)
                        current_total = int(m_row[6]) if len(m_row) > 6 and str(m_row[6]).isdigit() else 0
                        master_sheet.update_cell(m_cell.row, 7, str(current_total + amt))
                        # Log History
                        ts = datetime.now().strftime("%d-%m-%Y %H:%M")
                        fees_sheet.insert_row([f_id, amt, month, ts, mode], index=2)
                        st.success(f"Payment successful. New Total: ₹{current_total + amt}")
            except: st.error("Student ID not found.")

# --- MODULE 3: DAILY CASH REPORT (Office PIN Required) ---
elif menu == "Daily Cash Report":
    if check_office_access():
        st.subheader("Daily Financial Summary")
        today_date = datetime.now().strftime("%d-%m-%Y")
        try:
            data = fees_sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                df['Date'] = df['Timestamp'].apply(lambda x: x.split(' ')[0])
                today_df = df[df['Date'] == today_date]
                if not today_df.empty:
                    st.metric("Total Collection Today", f"₹{today_df['Amount'].sum()}")
                    st.dataframe(today_df)
                else: st.info("No transactions today.")
        except: st.write("No history available.")

# --- MODULE 4: STUDENT RECORDS (Search) ---
elif menu == "Student Records":
    st.subheader("Search Student Profile")
    search_id = st.text_input("Enter ID").upper()
    if st.button("Search"):
        try:
            all_m = master_sheet.get_all_values()
            s_data = next((r for r in all_m if r[0].upper() == search_id), None)
            if s_data:
                st.info(f"Name: {s_data[1]} | Roll: {s_data[2]}")
                st.write(f"**Father:** {s_data[3]} | **Contact:** {s_data[5]}")
                st.markdown(f"### Total Fees Paid: ₹{s_data[6]}")
                st.divider()
                st.write("Recent Transactions:")
                f_hist = fees_sheet.get_all_values()
                u_hist = [r for r in f_hist if r[0].upper() == search_id]
                if u_hist: st.table(u_hist)
            else: st.warning("Not found.")
        except Exception as e: st.error(f"Search Error: {e}")
