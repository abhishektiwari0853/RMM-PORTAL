import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import os

# --- LOGIN SYSTEM ---
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("Admin Password Daalo", type="password", on_change=password_entered, key="password_input")
        return False
    return st.session_state["password_correct"]

def password_entered():
    if st.session_state["password_input"] == "RMM2014": # Password badal sakte ho
        st.session_state["password_correct"] = True
        del st.session_state["password_input"]
    else:
        st.error("Wrong Password!")

if not check_password():
    st.stop()

# --- DATABASE CONNECTION ---
# (Yahan wahi purana gspread wala logic rahega jo secrets se connect hota hai)
# ... [Purana Connection Code] ...

# --- APP NAVIGATION ---
choice = st.sidebar.radio("Main Menu", ["Attendance Scanner", "Fees Management", "Search Student Info"])

# --- NEW FEATURE: SEARCH STUDENT INFO ---
if choice == "Search Student Info":
    st.subheader("🔍 Student Record Search")
    search_id = st.text_input("Student ID Enter Karo:").upper()
    
    if search_id:
        try:
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            student_row = df[df['ID'] == search_id] # Column name 'ID' hona chahiye
            
            if not student_row.empty:
                st.write("### Student Details:")
                st.table(student_row) # Pura data dikha dega
            else:
                st.error("Is ID ka koi student nahi mila!")
        except Exception as e:
            st.error("Data fetch karne mein galti hui.")
