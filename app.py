import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd
import traceback
import io

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
st.set_page_config(page_title="RMM Administrative Portal", page_icon="🏫", layout="wide")

# -----------------------------
# 2. DUAL-LAYER SECURITY
# -----------------------------
def check_main_password():
    if "main_auth" not in st.session_state:
        st.markdown("<h2 style='text-align: center;'>School Portal Login</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Portal Password", type="password")
        if st.button("Access Portal"):
            if pwd == "RMM2014":
                st.session_state["main_auth"] = True
                st.rerun()
            else:
                st.error("Invalid Password")
        return False
    return True

def check_office_access():
    if "office_auth" not in st.session_state:
        st.warning("Restricted: Office PIN required for financial operations.")
        pin = st.text_input("Enter Office PIN", type="password", key="office_pin")
        if st.button("Unlock Office Desk"):
            if pin == "OFFICE786":
                st.session_state["office_auth"] = True
                st.rerun()
            else:
                st.error("Incorrect PIN")
        return False
    return True

if not check_main_password():
    st.stop()

# -----------------------------
# 3. DATABASE CONNECTION
# -----------------------------
@st.cache_resource
def get_workbook():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                dict(st.secrets["gcp_service_account"]), scope
            )
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        client = gspread.authorize(creds)
        return client.open_by_key("1fiAOXJUCMk_dlKfUbW6syEEHRREaMAnNaDIe0X0wboo")
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

wb = get_workbook()
if wb is None:
    st.stop()

# -----------------------------
# 4. SMART SHEET FINDER
# -----------------------------
def find_class_sheet(class_num, sheet_type):
    all_sheets = wb.worksheets()
    exact_name = f"{sheet_type}_{class_num}"
    for ws in all_sheets:
        if ws.title.strip() == exact_name:
            return ws
    for ws in all_sheets:
        title = ws.title.strip().lower()
        target = sheet_type.lower()
        if target == 'attendance' and 'attend' in title and str(class_num) in title:
            return ws
        elif target == 'master' and 'master' in title and str(class_num) in title:
            return ws
        elif target == 'fees' and 'fees' in title and str(class_num) in title:
            return ws
    return None

# -----------------------------
# 5. SIDEBAR & NAVIGATION (including new items)
# -----------------------------
st.sidebar.header("Administration Panel")
selected_class = st.sidebar.selectbox("Academic Class", ["7", "8", "9", "10", "11", "12"])
menu = st.sidebar.radio("Navigation", [
    "Student Attendance",
    "Attendance Report",
    "Fee Collection",
    "Daily Cash Report",
    "Student Records",
    "Edit Student Details",
    "Add New Student",
    "At-Risk Students"            # ← Dropout Prediction
])

if "office_auth" in st.session_state:
    if st.sidebar.button("Lock Office Sections"):
        del st.session_state["office_auth"]
        st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# -----------------------------
# 6. LOAD CLASS SHEETS + STUDENT LIST
# -----------------------------
try:
    master_sheet = find_class_sheet(selected_class, 'Master')
    attendance_sheet = find_class_sheet(selected_class, 'Attendance')
    fees_sheet = find_class_sheet(selected_class, 'Fees')

    if not all([master_sheet, attendance_sheet, fees_sheet]):
        missing = []
        if not master_sheet: missing.append('Master')
        if not attendance_sheet: missing.append('Attendance')
        if not fees_sheet: missing.append('Fees')
        st.error(f"❌ Missing sheets for Class {selected_class}: {', '.join(missing)}")
        st.stop()

    raw_data = master_sheet.get_all_values()
    if len(raw_data) < 2:
        st.warning("Master sheet has no data rows. Please add students and headers.")
        student_list = []
        df_master = pd.DataFrame()
    else:
        headers = [h.strip() for h in raw_data[0]]
        df_master = pd.DataFrame(raw_data[1:], columns=headers)
        id_col = next((c for c in df_master.columns if c.lower() == 'student id'), None)
        name_col = next((c for c in df_master.columns if c.lower() == 'name'), None)
        if id_col and name_col:
            student_list = [f"{row[id_col]} - {row[name_col]}" for _, row in df_master.iterrows()]
        else:
            st.error("Master sheet must contain 'Student ID' and 'Name' columns.")
            student_list = []
except Exception as e:
    st.error(f"❌ Error loading sheets for Class {selected_class}:\n{e}\n{traceback.format_exc()}")
    st.stop()

# -----------------------------
# 7. BRANDING
# -----------------------------
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    try:
        st.image("School_logo.png", width=180)
    except:
        st.caption("School Logo not found")
st.markdown("<h1 style='text-align: center;'>RAM MURTI MISHRA INTER COLLEGE</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: gray;'>Administrative Management System</h4>", unsafe_allow_html=True)
st.divider()

# =============================
# 8. MODULE – STUDENT ATTENDANCE (with Mark All & Auto Absent)
# =============================
if menu == "Student Attendance":
    st.subheader(f"Daily Attendance – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Mark Present"):
                if selected_student == "-- Select --":
                    st.warning("Please select a student first.")
                else:
                    s_id = selected_student.split(" - ")[0]
                    try:
                        today = datetime.now().strftime("%d-%m-%Y")
                        hdrs = attendance_sheet.row_values(1)
                        col_idx = hdrs.index(today) + 1 if today in hdrs else len(hdrs) + 1
                        if today not in hdrs:
                            attendance_sheet.update_cell(1, col_idx, today)
                        cell = attendance_sheet.find(s_id)
                        attendance_sheet.update_cell(cell.row, col_idx, "P")
                        st.success(f"Present marked for {selected_student}")
                    except Exception as e:
                        st.error(f"Update failed: {e}")

        with col2:
            if st.button("✅ Mark All Present"):
                try:
                    today = datetime.now().strftime("%d-%m-%Y")
                    hdrs = attendance_sheet.row_values(1)
                    col_idx = hdrs.index(today) + 1 if today in hdrs else len(hdrs) + 1
                    if today not in hdrs:
                        attendance_sheet.update_cell(1, col_idx, today)
                    all_ids = [f"{row[id_col]}" for _, row in df_master.iterrows()]
                    cnt = 0
                    for sid in all_ids:
                        try:
                            cell = attendance_sheet.find(sid)
                            attendance_sheet.update_cell(cell.row, col_idx, "P")
                            cnt += 1
                        except:
                            pass
                    st.success(f"All {cnt} students marked Present")
                except Exception as e:
                    st.error(f"Error: {e}")

        with col3:
            if st.button("⚠️ Mark Absent for Unmarked"):
                try:
                    today = datetime.now().strftime("%d-%m-%Y")
                    hdrs = attendance_sheet.row_values(1)
                    if today not in hdrs:
                        st.warning("Today's column not created yet. Mark at least one student first.")
                    else:
                        col_idx = hdrs.index(today) + 1
                        all_ids = [f"{row[id_col]}" for _, row in df_master.iterrows()]
                        absent_cnt = 0
                        for sid in all_ids:
                            try:
                                cell = attendance_sheet.find(sid)
                                curr_val = attendance_sheet.cell(cell.row, col_idx).value
                                if curr_val is None or curr_val.strip() == "":
                                    attendance_sheet.update_cell(cell.row, col_idx, "A")
                                    absent_cnt += 1
                            except:
                                pass
                        st.success(f"Marked {absent_cnt} students as Absent")
                except Exception as e:
                    st.error(f"Error: {e}")

# =============================
# 9. MODULE – ATTENDANCE REPORT (with Excel Download)
# =============================
elif menu == "Attendance Report":
    st.subheader(f"Monthly Attendance Report – Class {selected_class}")
    months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    sel_month = st.selectbox("Month", months, index=datetime.now().month-1)
    sel_year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.now().year)
    month_num = months.index(sel_month) + 1
    month_str = f"{month_num:02d}"

    try:
        att_vals = attendance_sheet.get_all_values()
        if len(att_vals) < 2:
            st.warning("No attendance data.")
        else:
            att_headers = att_vals[0]
            date_cols = []
            col_indices = []
            for idx, h in enumerate(att_headers):
                if idx == 0: continue
                parts = h.split('-')
                if len(parts) == 3 and parts[1] == month_str and parts[2] == str(sel_year):
                    date_cols.append(h)
                    col_indices.append(idx)
            if not date_cols:
                st.warning(f"No records for {sel_month} {sel_year}")
            else:
                total_days = len(date_cols)
                records = []
                for row in att_vals[1:]:
                    sid = row[0]
                    name = "N/A"
                    mask = df_master[id_col].astype(str) == sid
                    if mask.any():
                        name = df_master.loc[mask, name_col].values[0]
                    present = sum(1 for ci in col_indices if ci < len(row) and row[ci].strip().upper() == 'P')
                    percent = (present / total_days * 100) if total_days else 0
                    records.append({
                        "Student ID": sid,
                        "Name": name,
                        "Working Days": total_days,
                        "Present": present,
                        "Attendance %": round(percent, 1)
                    })
                df_rep = pd.DataFrame(records)

                def highlight_low(val):
                    return 'background-color: #ffcccc' if val < 75 else ''
                st.dataframe(df_rep.style.applymap(highlight_low, subset=['Attendance %']), use_container_width=True)

                # Excel Download
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_rep.to_excel(writer, index=False, sheet_name='Attendance')
                st.download_button(
                    label="📥 Download Excel Report",
                    data=buffer.getvalue(),
                    file_name=f"Attendance_Class{selected_class}_{sel_month}_{sel_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    except Exception as e:
        st.error(f"Error: {e}")

# =============================
# 10. MODULE – FEE COLLECTION
# =============================
elif menu == "Fee Collection":
    if check_office_access():
        st.subheader(f"Fee Counter – Class {selected_class}")
        if not student_list:
            st.warning("No students found.")
        else:
            selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)
            if selected_student != "-- Select --":
                s_id = selected_student.split(" - ")[0]
                try:
                    m_cell = master_sheet.find(s_id)
                    m_row = master_sheet.row_values(m_cell.row)
                    current_fees = int(m_row[6]) if len(m_row) >= 7 and str(m_row[6]).isdigit() else 0
                    st.info(f"**Student:** {m_row[1]} | **Father:** {m_row[3]} | **Total Paid:** ₹{current_fees}")

                    with st.form("fee_form", clear_on_submit=True):
                        amount = st.number_input("Amount Received", min_value=0)
                        month = st.selectbox("Month", ["April","May","June","July","August","September","October","November","December","January","February","March"])
                        mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque"])
                        if st.form_submit_button("Process Payment"):
                            new_total = current_fees + amount
                            master_sheet.update_cell(m_cell.row, 7, str(new_total))
                            ts = datetime.now().strftime("%d-%m-%Y %H:%M")
                            fees_sheet.insert_row([s_id, amount, month, f"{ts} {mode}"], index=2)
                            st.success(f"Payment of ₹{amount} recorded. New Total: ₹{new_total}")
                except Exception as e:
                    st.error(f"Error: {e}")

# =============================
# 11. MODULE – DAILY CASH REPORT
# =============================
elif menu == "Daily Cash Report":
    if check_office_access():
        st.subheader(f"Today's Financial Summary – Class {selected_class}")
        today_date = datetime.now().strftime("%d-%m-%Y")
        try:
            data = fees_sheet.get_all_records()
            if data:
                df_fees = pd.DataFrame(data)
                if 'Date of payment' in df_fees.columns:
                    df_fees['Date'] = df_fees['Date of payment'].apply(lambda x: str(x).split(' ')[0] if x else "")
                    today_df = df_fees[df_fees['Date'] == today_date]
                    if today_df.empty:
                        st.info("No transactions recorded today.")
                    else:
                        tot = today_df['Amount'].sum()
                        st.metric("Total Collection Today", f"₹{tot}")
                        st.dataframe(today_df[['Student ID','Amount','Month','Date of payment']])
                else:
                    st.error("Fees sheet missing 'Date of payment' column.")
            else:
                st.info("No fee records yet.")
        except Exception as e:
            st.error(f"Error: {e}")

# =============================
# 12. MODULE – STUDENT RECORDS (with Fee History Excel Download)
# =============================
elif menu == "Student Records":
    st.subheader(f"Student Profile – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Select Student", ["-- Select --"] + student_list)
        if selected_student != "-- Select --":
            s_id = selected_student.split(" - ")[0]
            try:
                student_data = df_master[df_master['Student ID'].astype(str) == s_id].iloc[0]
                name = student_data.get('Name','')
                roll = student_data.get('Roll No','')
                father = student_data.get('Father name', student_data.get('Father Name',''))
                mobile = student_data.get('Mobile','')
                total_fees = student_data.get('Total_Fees','0')
                address = student_data.get('Adress', student_data.get('Address','N/A'))
                st.info(f"**Name:** {name}  |  **Roll No:** {roll}")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Father's Name:** {father}")
                    st.write(f"**Address:** {address}")
                with c2:
                    st.write(f"**Mobile:** {mobile}")
                    st.markdown(f"### Total Fees Paid: ₹{total_fees}")
                st.divider()
                st.subheader("Fee Payment History")
                all_fee_records = fees_sheet.get_all_values()
                if len(all_fee_records) > 1:
                    fee_headers = all_fee_records[0]
                    history = [r for r in all_fee_records[1:] if r[0].upper() == s_id.upper()]
                    if history:
                        tdata = [fee_headers] + history
                        st.table(tdata)
                        # Excel download for fee history
                        pdf_df = pd.DataFrame(history, columns=fee_headers)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                            pdf_df.to_excel(w, index=False, sheet_name='FeeHistory')
                        st.download_button(
                            label="📥 Download Fee History (Excel)",
                            data=buf.getvalue(),
                            file_name=f"FeeHistory_{s_id}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.write("No payment history found.")
                else:
                    st.write("No payment records available.")
            except Exception as e:
                st.warning(f"Error: {e}")

# =============================
# 13. MODULE – EDIT STUDENT DETAILS
# =============================
elif menu == "Edit Student Details":
    st.subheader(f"Edit Student Information – Class {selected_class}")
    if not student_list:
        st.warning("No students found.")
    else:
        selected_student = st.selectbox("Choose Student to Edit", ["-- Select --"] + student_list)
        if selected_student != "-- Select --":
            s_id = selected_student.split(" - ")[0]
            try:
                cell = master_sheet.find(s_id)
                row_num = cell.row
                row_data = master_sheet.row_values(row_num)
                headers_edit = [h.strip() for h in master_sheet.row_values(1)]

                def find_col(col_name):
                    col_name = col_name.lower()
                    for i, h in enumerate(headers_edit):
                        if h.lower() == col_name:
                            return i
                    for i, h in enumerate(headers_edit):
                        if col_name in h.lower():
                            return i
                    return None

                col_name = find_col('name')
                col_father = find_col('father')
                col_mobile = find_col('mobile')
                col_address = find_col('adress')
                if col_address is None: col_address = find_col('address')
                col_aadhaar = find_col('aadhar')

                def safe_get(idx):
                    return row_data[idx] if idx < len(row_data) else ""
                current_name = safe_get(col_name)
                current_roll = safe_get(find_col('roll no')) if find_col('roll no') else "N/A"
                current_father = safe_get(col_father)
                current_mobile = safe_get(col_mobile)
                current_address = safe_get(col_address)
                current_aadhaar = safe_get(col_aadhaar) if col_aadhaar else ""

                st.info(f"**Student ID:** {s_id} | **Roll No:** {current_roll}")
                st.write("---")
                with st.form("edit_form"):
                    new_name = st.text_input("Name", value=current_name)
                    new_father = st.text_input("Father's Name", value=current_father)
                    new_mobile = st.text_input("Mobile Number", value=current_mobile)
                    new_address = st.text_input("Address", value=current_address)
                    new_aadhaar = st.text_input("Aadhaar Number", value=current_aadhaar)
                    if st.form_submit_button("Update Details"):
                        updates = []
                        if new_name != current_name and col_name is not None:
                            updates.append((col_name, new_name))
                        if new_father != current_father and col_father is not None:
                            updates.append((col_father, new_father))
                        if new_mobile != current_mobile and col_mobile is not None:
                            updates.append((col_mobile, new_mobile))
                        if new_address != current_address and col_address is not None:
                            updates.append((col_address, new_address))
                        if new_aadhaar != current_aadhaar and col_aadhaar is not None:
                            updates.append((col_aadhaar, new_aadhaar))
                        if not updates:
                            st.info("No changes detected.")
                        else:
                            for col_idx, value in updates:
                                master_sheet.update_cell(row_num, col_idx + 1, value)
                            st.success("Student details updated successfully!")
            except Exception as e:
                st.error(f"Error: {e}")

# =============================
# 14. MODULE – ADD NEW STUDENT
# =============================
elif menu == "Add New Student":
    st.subheader(f"Enroll New Student – Class {selected_class}")
    existing_ids = []
    existing_rolls = []
    if not df_master.empty:
        id_col_name = next((c for c in df_master.columns if c.lower() == 'student id'), None)
        roll_col_name = next((c for c in df_master.columns if c.lower() == 'roll no'), None)
        if id_col_name:
            existing_ids = df_master[id_col_name].astype(str).tolist()
        if roll_col_name:
            try:
                existing_rolls = df_master[roll_col_name].astype(int).tolist()
            except:
                existing_rolls = []

    prefix = f"RMEC{selected_class}"
    max_seq = 0
    for sid in existing_ids:
        if sid.startswith(prefix):
            num_part = sid[len(prefix):]
            if num_part.isdigit():
                max_seq = max(max_seq, int(num_part))
    new_id = f"{prefix}{max_seq + 1:03d}"

    new_roll = 1
    if existing_rolls:
        new_roll = max(existing_rolls) + 1

    with st.form("add_student_form", clear_on_submit=True):
        st.info(new_id)
        st.caption("Student ID (auto‑generated)")
        st.info(str(new_roll))
        st.caption("Roll Number (auto‑generated)")
        new_name = st.text_input("Full Name *")
        new_father = st.text_input("Father's Name *")
        new_mobile = st.text_input("Mobile Number")
        new_address = st.text_input("Address")
        new_aadhaar = st.text_input("Aadhaar Number")
        if st.form_submit_button("Enroll Student"):
            if not new_name.strip() or not new_father.strip():
                st.error("❌ Name and Father's Name are required.")
            else:
                new_row = [
                    new_id, new_name.strip(), str(new_roll), new_father.strip(),
                    "", new_mobile.strip() if new_mobile else "", "0",
                    new_address.strip() if new_address else "", "",
                    new_aadhaar.strip() if new_aadhaar else ""
                ]
                try:
                    master_sheet.append_row(new_row, value_input_option='USER_ENTERED')
                    attendance_sheet.append_row([new_id])
                    st.success(f"✅ {new_name} enrolled!")
                    st.balloons()
                    st.cache_resource.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# =============================
# 15. MODULE – AT‑RISK STUDENTS (Dropout Prediction)
# =============================
elif menu == "At-Risk Students":
    st.subheader(f"🚨 Dropout Risk Alert – Class {selected_class}")
    st.caption("Students with 5+ consecutive absences (non‑'P' marks)")

    try:
        att_vals = attendance_sheet.get_all_values()
        if len(att_vals) < 2:
            st.warning("No attendance data.")
        else:
            att_headers = att_vals[0]
            # Sort date columns in chronological order
            date_map = {}
            for idx, h in enumerate(att_headers):
                if idx == 0: continue
                parts = h.split('-')
                if len(parts) == 3:
                    try:
                        d = datetime.strptime(h, "%d-%m-%Y")
                        date_map[idx] = d
                    except:
                        pass
            sorted_cols = sorted(date_map.items(), key=lambda x: x[1])  # (col_idx, date)

            at_risk = []
            for row_idx, row in enumerate(att_vals[1:], start=2):   # row numbers in sheet
                sid = row[0]
                name = "N/A"
                mask = df_master[id_col].astype(str) == sid
                if mask.any():
                    name = df_master.loc[mask, name_col].values[0]
                # Determine absent sequence
                max_consec = 0
                current_streak = 0
                for col_idx, _ in sorted_cols:
                    val = row[col_idx].strip().upper() if col_idx < len(row) else ""
                    if val != 'P':   # absent or unmarked
                        current_streak += 1
                    else:
                        current_streak = 0
                    max_consec = max(max_consec, current_streak)
                if max_consec >= 5:
                    at_risk.append((sid, name, max_consec))

            if at_risk:
                df_risk = pd.DataFrame(at_risk, columns=["Student ID", "Name", "Consecutive Absences"])
                st.warning(f"Total students at risk: {len(at_risk)}")
                st.dataframe(df_risk.style.applymap(lambda x: 'background-color: #ff4d4d' if isinstance(x, int) and x >= 5 else '', subset=['Consecutive Absences']))
            else:
                st.success("No students with 5+ consecutive absences. Keep it up!")
    except Exception as e:
        st.error(f"Error: {e}")
