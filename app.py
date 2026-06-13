import streamlit as st
import gspread
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd
import io
import json
import base64

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
st.set_page_config(page_title="Cambridge Portal", page_icon="🏫", layout="wide")

# =====================================================================
# CLEAN DARK THEME – BLACK BACKGROUND, NO GLASS
# =====================================================================
st.markdown("""
<style>
/* Global */
body {
    background-color: #000000;
    color: #ffffff;
}
.main {
    background-color: #000000;
}

/* Cards */
div[data-testid="stVerticalBlock"] > div {
    background: #111111;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
}

/* Buttons */
.stButton > button {
    background-color: #1a3b5d;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
}
.stButton > button:hover {
    background-color: #2c5282;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #0a0a0a;
    border-right: 1px solid #333333;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    color: #ffffff;
}
section[data-testid="stSidebar"] .stSelectbox label {
    color: #ffffff !important;
}

/* Inputs */
.stTextInput input, .stNumberInput input, .stSelectbox select {
    background-color: #1a1a1a !important;
    border: 1px solid #444444 !important;
    border-radius: 6px !important;
    color: white !important;
}

/* Tables */
.stTable tbody tr:nth-child(even) {
    background-color: #1a1a1a;
}
.stTable tbody tr:hover {
    background-color: #2a2a2a;
}

/* Metric Cards */
[data-testid="metric-container"] {
    background: #111111;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 16px;
}
[data-testid="metric-container"] label {
    color: #aaaaaa !important;
}
[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    color: #fbbf24 !important;
}

/* Receipt Card */
.receipt-card {
    background: #111111;
    border: 1px solid #444444;
    border-radius: 8px;
    padding: 20px;
    margin: 20px 0;
}
.receipt-card h3 { color: #fbbf24; text-align: center; }
.receipt-card p { color: #e0e0e0; }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 2. LOGIN
# -----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["role"] = None

if not st.session_state["authenticated"]:
    # Simple centered login form
    _, center, _ = st.columns([1,2,1])
    with center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## Cambridge International School")
        role = st.selectbox("Select Role", ["Teacher", "Clerk", "Principal"])
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            valid = False
            if role == "Teacher" and pwd == "TCH2024": valid = True
            elif role == "Clerk" and pwd == "CLK2024": valid = True
            elif role == "Principal" and pwd == "PRN2024": valid = True
            if valid:
                st.session_state["authenticated"] = True
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# -----------------------------
# 3. DATABASE CONNECTION
# -----------------------------
SHEET_ID = "1n6SvSamatNUX8AEZpFXE5IvERZ8a4eDWgQkW6uj-WDc"

@st.cache_resource
def get_workbook():
    try:
        if "gcp_creds" not in st.secrets:
            st.error("❌ Streamlit Secrets missing 'gcp_creds'.")
            return None
        creds_dict = json.loads(st.secrets["gcp_creds"])
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID)
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")
        return None

wb = get_workbook()
if wb is None: st.stop()

# -----------------------------
# 4. CACHING FUNCTIONS (TTL 1800)
# -----------------------------
@st.cache_data(ttl=1800)
def get_sheet_names():
    return [ws.title.strip() for ws in wb.worksheets()]

def find_sheet(name):
    names = get_sheet_names()
    name_clean = name.strip().lower()
    for n in names:
        if n.lower() == name_clean: return wb.worksheet(n)
    for n in names:
        if name_clean in n.lower(): return wb.worksheet(n)
    return None

def get_available_classes():
    sheets = get_sheet_names()
    classes = []
    for s in sheets:
        if s.upper().startswith("MASTER_"):
            class_name = s.split("_", 1)[1].strip()
            if class_name: classes.append(class_name)
    return sorted(classes) if classes else ["LKG"]

@st.cache_data(ttl=1800)
def load_master_data(class_name):
    sheet = find_sheet(f"MASTER_{class_name}")
    if not sheet: return pd.DataFrame(), []
    raw = sheet.get_all_values()
    if len(raw) < 2: return pd.DataFrame(), []
    headers = [h.strip() for h in raw[0]]
    df = pd.DataFrame(raw[1:], columns=headers)
    id_col = next((c for c in df.columns if c.upper() in ['ID', 'STUDENT ID']), None)
    name_col = next((c for c in df.columns if c.upper() in ['NAME', 'STUDENT NAME']), None)
    student_list = []
    if id_col and name_col:
        student_list = [f"{row[id_col]} - {row[name_col]}" for _, row in df.iterrows()]
    return df, student_list

@st.cache_data(ttl=1800)
def load_attendance_data(class_name):
    sheet = find_sheet(f"ATTENDANCE_{class_name}")
    return sheet.get_all_values() if sheet else []

@st.cache_data(ttl=1800)
def load_fees_data(class_name):
    sheet = find_sheet(f"FEES_{class_name}")
    return sheet.get_all_values() if sheet else []

@st.cache_data(ttl=1800)
def load_fee_structure():
    sheet = find_sheet("FEES_STRUCTURE")
    if not sheet: return {}
    data = sheet.get_all_values()
    fee_map = {}
    if len(data) >= 2:
        for row in data[1:]:
            if len(row) >= 2:
                cls, fee = row[0].strip(), row[1].strip()
                if cls and fee.isdigit(): fee_map[cls] = int(fee)
    return fee_map

# -----------------------------
# 5. SIDEBAR
# -----------------------------
with st.sidebar:
    st.header("Administration")
    st.markdown(f"**{st.session_state['role']}**")
    available_classes = get_available_classes()
    selected_class = st.selectbox("Class", available_classes)

    role = st.session_state["role"]
    if role == "Teacher":
        menu_options = ["Student Attendance","Attendance Report","Student Records","Edit Student Details","Add New Student"]
    elif role == "Clerk":
        menu_options = ["Fee Collection","Daily Cash Report","Add New Student","Student Records","Edit Student Details"]
    else:
        menu_options = ["Executive Dashboard","Student Attendance","Attendance Report","Fee Collection","Daily Cash Report","Student Records","Edit Student Details","Add New Student"]

    menu = st.radio("Navigation", menu_options, label_visibility="collapsed")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# -----------------------------
# 6. LOAD DATA
# -----------------------------
df_master, student_list = load_master_data(selected_class)
id_col = next((c for c in df_master.columns if c.upper() in ['ID','STUDENT ID']), None) if not df_master.empty else None
name_col = next((c for c in df_master.columns if c.upper() in ['NAME','STUDENT NAME']), None) if not df_master.empty else None

attendance_data = load_attendance_data(selected_class)
fees_data = load_fees_data(selected_class)
monthly_fee_map = load_fee_structure()
default_fee = monthly_fee_map.get(selected_class, 500)

master_sheet = find_sheet(f"MASTER_{selected_class}")
attendance_sheet = find_sheet(f"ATTENDANCE_{selected_class}")
fees_sheet = find_sheet(f"FEES_{selected_class}")
if not all([master_sheet, attendance_sheet, fees_sheet]):
    st.error("Required sheets missing.")
    st.stop()

def ensure_column(sheet, col_name):
    headers = sheet.row_values(1)
    if col_name not in headers:
        sheet.update_cell(1, len(headers)+1, col_name)
        st.cache_data.clear()

ensure_column(master_sheet, "ANNUAL_FEE")
ensure_column(master_sheet, "ADMISSION_FEE")

def compute_paid_total(sid, all_fees):
    total = 0
    if all_fees and len(all_fees)>1:
        for row in all_fees[1:]:
            if row[0].strip().upper() == sid.upper() and row[1].isdigit():
                total += int(row[1])
    return total

# -----------------------------
# 7. BRANDING
# -----------------------------
st.markdown("<h2 style='text-align:center; color:#fbbf24;'>CAMBRIDGE INTERNATIONAL SCHOOL</h2>", unsafe_allow_html=True)
st.divider()

# =============================
# 8. EXECUTIVE DASHBOARD
# =============================
if menu == "Executive Dashboard" and role == "Principal":
    st.subheader(f"Dashboard – {selected_class}")
    if df_master.empty:
        st.warning("No student data.")
    else:
        total_students = len(df_master)
        today_str = datetime.now().strftime("%d-%m-%Y")
        att_headers = attendance_data[0] if attendance_data else []
        today_col_1based = att_headers.index(today_str)+1 if today_str in att_headers else None
        present = 0
        if today_col_1based and len(attendance_data)>1:
            today_idx = today_col_1based - 1
            for row in attendance_data[1:]:
                if today_idx < len(row) and row[today_idx].strip().upper() == 'P':
                    present += 1
        att_pct = (present/total_students*100) if total_students else 0

        today_fees = 0
        if fees_data and len(fees_data)>1:
            for r in fees_data[1:]:
                if len(r)>=4 and r[3].split(' ')[0] == today_str and r[1].isdigit():
                    today_fees += int(r[1])

        current_month = datetime.now().month
        current_year = datetime.now().year
        month_col = 0
        if fees_data and len(fees_data)>1:
            for r in fees_data[1:]:
                if len(r)>=4:
                    ds = r[3].split(' ')[0]
                    try:
                        d = datetime.strptime(ds, "%d-%m-%Y")
                        if d.month == current_month and d.year == current_year and r[1].isdigit():
                            month_col += int(r[1])
                    except: pass

        monthly_fee = monthly_fee_map.get(selected_class, 500)
        expected_monthly = total_students * monthly_fee
        col_pct = (month_col/expected_monthly*100) if expected_monthly else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Students", total_students)
        col2.metric("Today Att.", f"{att_pct:.0f}% ({present}/{total_students})")
        col3.metric("Today Fees", f"₹{today_fees}")
        col4.metric("Month Fees", f"₹{month_col} ({col_pct:.0f}%)")

        if not df_master.empty:
            outstanding_list = []
            for _, student in df_master.iterrows():
                sid = str(student[id_col])
                name = student[name_col] if name_col else ""
                if current_month >= 4: months = current_month - 4 + 1
                else: months = current_month + 9
                expected = months * monthly_fee
                ann = int(student.get('ANNUAL_FEE', 0)) if str(student.get('ANNUAL_FEE',0)).isdigit() else 0
                adm = int(student.get('ADMISSION_FEE', 0)) if str(student.get('ADMISSION_FEE',0)).isdigit() else 0
                expected += ann + adm
                paid = compute_paid_total(sid, fees_data)
                outstanding = max(0, expected - paid)
                outstanding_list.append((name, outstanding))
            df_out = pd.DataFrame(outstanding_list, columns=["Name", "Outstanding"])
            top5 = df_out.nlargest(5, "Outstanding")
        else:
            top5 = pd.DataFrame()
        st.write("**Top 5 Outstanding**")
        if not top5.empty: st.dataframe(top5)
        else: st.write("None")

# =============================
# 9. STUDENT ATTENDANCE (BATCH UPDATES)
# =============================
elif menu == "Student Attendance":
    st.subheader(f"Daily Attendance – {selected_class}")
    if not student_list: st.warning("No students.")
    else:
        sel = st.selectbox("Select Student", ["-- Select --"] + student_list)
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Mark Present"):
                if sel != "-- Select --":
                    sid = sel.split(" - ")[0]
                    try:
                        today = datetime.now().strftime("%d-%m-%Y")
                        hdrs = attendance_sheet.row_values(1)
                        ci = hdrs.index(today)+1 if today in hdrs else len(hdrs)+1
                        if today not in hdrs: attendance_sheet.update_cell(1, ci, today)
                        cell = attendance_sheet.find(sid)
                        attendance_sheet.update_cell(cell.row, ci, "P")
                        st.success(f"Marked {sel}")
                        st.cache_data.clear()
                    except Exception as e: st.error(f"Error: {e}")
        with c2:
            if st.button("Mark All Present"):
                try:
                    today = datetime.now().strftime("%d-%m-%Y")
                    hdrs = attendance_sheet.row_values(1)
                    ci = hdrs.index(today)+1 if today in hdrs else len(hdrs)+1
                    if today not in hdrs: attendance_sheet.update_cell(1, ci, today)
                    ids = [f"{row[id_col]}" for _, row in df_master.iterrows()]
                    cells_to_update = []
                    for sid in ids:
                        try:
                            cell = attendance_sheet.find(sid)
                            cells_to_update.append({
                                'range': rowcol_to_a1(cell.row, ci),
                                'values': [['P']]
                            })
                        except: pass
                    if cells_to_update:
                        attendance_sheet.batch_update(cells_to_update)
                    st.success(f"All {len(cells_to_update)} marked Present")
                    st.cache_data.clear()
                except Exception as e: st.error(f"Error: {e}")
        with c3:
            if st.button("Mark Absent for Unmarked"):
                try:
                    today = datetime.now().strftime("%d-%m-%Y")
                    hdrs = attendance_sheet.row_values(1)
                    if today not in hdrs:
                        st.warning("Column not created.")
                    else:
                        ci = hdrs.index(today)+1
                        ids = [f"{row[id_col]}" for _, row in df_master.iterrows()]
                        cells_to_update = []
                        for sid in ids:
                            try:
                                cell = attendance_sheet.find(sid)
                                val = attendance_sheet.cell(cell.row, ci).value
                                if not val or val.strip()=="":
                                    cells_to_update.append({
                                        'range': rowcol_to_a1(cell.row, ci),
                                        'values': [['A']]
                                    })
                            except: pass
                        if cells_to_update:
                            attendance_sheet.batch_update(cells_to_update)
                        st.success(f"Marked {len(cells_to_update)} students as Absent")
                        st.cache_data.clear()
                except Exception as e: st.error(f"Error: {e}")

# =============================
# 10. ATTENDANCE REPORT
# =============================
elif menu == "Attendance Report":
    st.subheader(f"Monthly Attendance Report – {selected_class}")
    months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    sel_month = st.selectbox("Month", months, index=datetime.now().month-1)
    sel_year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.now().year)
    month_num = months.index(sel_month) + 1
    month_str = f"{month_num:02d}"

    with st.spinner("Generating attendance report..."):
        if len(attendance_data) < 2:
            st.warning("No attendance data.")
        else:
            att_headers = attendance_data[0]
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
                for row in attendance_data[1:]:
                    sid = row[0]
                    name = "N/A"
                    if not df_master.empty:
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
                st.dataframe(df_rep.style.map(highlight_low, subset=['Attendance %']), use_container_width=True)

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_rep.to_excel(writer, index=False, sheet_name='Attendance')
                st.download_button(
                    label="Download Excel Report",
                    data=buffer.getvalue(),
                    file_name=f"Attendance_{selected_class}_{sel_month}_{sel_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# =============================
# 11. FEE COLLECTION (with Receipt)
# =============================
elif menu == "Fee Collection":
    if role not in ["Clerk","Principal"]:
        st.error("Access Denied"); st.stop()
    st.subheader(f"Fee Counter – {selected_class}")
    if not student_list: st.warning("No students.")
    else:
        sel = st.selectbox("Select Student", ["-- Select --"]+student_list)
        if sel != "-- Select --":
            sid = sel.split(" - ")[0]
            mask = df_master[id_col].astype(str) == sid
            student_name = ""
            if mask.any():
                student_name = df_master[mask].iloc[0].get(name_col, "")
            paid_total = compute_paid_total(sid, fees_data)
            st.info(f"**Student:** {student_name} | **Total Paid (all):** ₹{paid_total}")
            with st.form("fee_form", clear_on_submit=True):
                fee_type = st.selectbox("Fee Type", ["Monthly Fee", "Annual Fee", "Admission Fee"])
                amt = st.number_input("Amount", min_value=0)
                mo = st.selectbox("Month", ["April","May","June","July","August","September","October","November","December","January","February","March"])
                mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque"])
                submitted = st.form_submit_button("Process Payment")
                if submitted:
                    if amt <= 0:
                        st.error("Amount must be > 0")
                    else:
                        ts = datetime.now().strftime("%d-%m-%Y %H:%M")
                        fh = fees_sheet.row_values(1)
                        if "Fee Type" not in fh:
                            fees_sheet.update_cell(1, len(fh)+1, "Fee Type")
                            fh.append("Fee Type")
                        fees_sheet.insert_row([sid, amt, mo, f"{ts} {mode}", fee_type], index=2)
                        st.success(f"Payment of ₹{amt} recorded ({fee_type})")
                        st.cache_data.clear()
                        receipt_html = f"""
<div style="border:1px solid #444; padding:15px; margin-top:20px; border-radius:8px; background:#111;">
    <h3 style="text-align:center; color:#fbbf24;">PAYMENT RECEIPT</h3>
    <p style="color:#e0e0e0;"><b>Receipt No:</b> RCP-{int(datetime.timestamp(datetime.now()))}</p>
    <p style="color:#e0e0e0;"><b>Date:</b> {datetime.now().strftime("%d-%m-%Y %H:%M")}</p>
    <p style="color:#e0e0e0;"><b>Student ID:</b> {sid}</p>
    <p style="color:#e0e0e0;"><b>Student Name:</b> {student_name}</p>
    <p style="color:#e0e0e0;"><b>Fee Type:</b> {fee_type}</p>
    <p style="color:#e0e0e0;"><b>Amount Paid:</b> ₹{amt}</p>
    <p style="color:#e0e0e0;"><b>Payment Mode:</b> {mode}</p>
    <p style="color:#e0e0e0;"><b>Month:</b> {mo}</p>
</div>
"""
                        st.markdown(receipt_html, unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("""
                                <button onclick="window.print()" style="background:#1a3b5d; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer;">
                                    Print Receipt
                                </button>
                            """, unsafe_allow_html=True)
                        with col2:
                            b64 = base64.b64encode(receipt_html.encode()).decode()
                            href = f'<a href="data:text/html;base64,{b64}" download="Receipt_{sid}_{datetime.now().strftime("%Y%m%d%H%M")}.html">Download Receipt</a>'
                            st.markdown(href, unsafe_allow_html=True)

# =============================
# 12. DAILY CASH REPORT
# =============================
elif menu == "Daily Cash Report":
    if role not in ["Clerk","Principal"]:
        st.error("Access Denied"); st.stop()
    st.subheader(f"Today's Financial Summary – {selected_class}")
    today_str = datetime.now().strftime("%d-%m-%Y")
    if fees_data and len(fees_data)>1:
        fh = fees_data[0]
        today_rows = [r for r in fees_data[1:] if len(r)>=4 and r[3].split(' ')[0]==today_str]
        if today_rows:
            amt_col = fh.index('Amount') if 'Amount' in fh else 1
            total = sum(int(r[amt_col]) for r in today_rows if r[amt_col].isdigit())
            st.metric("Total Today", f"₹{total}")
            display_cols = ['Student ID','Amount','Month','Date of payment']
            if 'Fee Type' in fh: display_cols.append('Fee Type')
            df_today = pd.DataFrame(today_rows, columns=fh)
            available_cols = [c for c in display_cols if c in df_today.columns]
            st.dataframe(df_today[available_cols])
        else: st.info("No transactions today.")
    else: st.info("No fee records.")

# =============================
# 13. STUDENT RECORDS
# =============================
elif menu == "Student Records":
    st.subheader(f"Student Profile – {selected_class}")
    if not student_list: st.warning("No students.")
    else:
        sel = st.selectbox("Select Student", ["-- Select --"]+student_list)
        if sel != "-- Select --":
            sid = sel.split(" - ")[0]
            mask = df_master[id_col].astype(str)==sid
            if mask.any():
                sd = df_master[mask].iloc[0]
                name = sd.get(name_col,'')
                roll = sd.get('ROLL NO','')
                father = sd.get('FATHER','') or sd.get('FATHER NAME','')
                mobile = sd.get('MOBILE','')
                addr = sd.get('ADDRESS','N/A')
                ann = sd.get('ANNUAL_FEE','0')
                adm = sd.get('ADMISSION_FEE','0')
                paid = compute_paid_total(sid, fees_data)
                st.info(f"**{name}** | Roll: {roll}")
                c1,c2 = st.columns(2)
                c1.write(f"Father: {father}")
                c1.write(f"Mobile: {mobile}")
                c1.write(f"Annual Fees Due: ₹{ann}")
                c1.write(f"Admission Fees Due: ₹{adm}")
                c2.write(f"Total Paid: ₹{paid}")
                c2.write(f"Address: {addr}")
                st.divider()
                st.subheader("Fee History")
                if fees_data and len(fees_data)>1:
                    fh = fees_data[0]
                    hist = [r for r in fees_data[1:] if r[0].upper()==sid.upper()]
                    if hist:
                        df_hist = pd.DataFrame(hist, columns=fh)
                        st.dataframe(df_hist, use_container_width=True)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                            df_hist.to_excel(w, index=False)
                        st.download_button("Download History", buf.getvalue(), f"FeeHistory_{sid}.xlsx")
                    else: st.write("No history.")
                else: st.write("No records.")
            else: st.warning("Not found.")

# =============================
# 14. EDIT STUDENT DETAILS
# =============================
elif menu == "Edit Student Details":
    st.subheader(f"Edit Student – {selected_class}")
    if not student_list: st.warning("No students.")
    else:
        sel = st.selectbox("Choose Student", ["-- Select --"]+student_list)
        if sel != "-- Select --":
            sid = sel.split(" - ")[0]
            try:
                cell = master_sheet.find(sid)
                rn = cell.row
                rd = master_sheet.row_values(rn)
                hd = [h.strip() for h in master_sheet.row_values(1)]
                def fc(n):
                    for i,h in enumerate(hd):
                        if h.upper() == n.upper(): return i
                    return None
                def gv(col): return rd[col] if col is not None and col < len(rd) else ""
                cname = fc('NAME')
                cfather = fc('FATHER') or fc('FATHER NAME')
                cmobile = fc('MOBILE')
                caddress = fc('ADDRESS')
                caadhar = fc('AADHAR') or fc('AADHAAR')
                cannual = fc('ANNUAL_FEE')
                cadm = fc('ADMISSION_FEE')
                if caddress is None:
                    master_sheet.update_cell(1, len(hd)+1, 'ADDRESS')
                    st.cache_data.clear()
                    hd.append('ADDRESS')
                    caddress = len(hd)-1
                if cannual is None:
                    master_sheet.update_cell(1, len(hd)+1, 'ANNUAL_FEE')
                    st.cache_data.clear()
                    hd.append('ANNUAL_FEE')
                    cannual = len(hd)-1
                if cadm is None:
                    master_sheet.update_cell(1, len(hd)+1, 'ADMISSION_FEE')
                    st.cache_data.clear()
                    hd.append('ADMISSION_FEE')
                    cadm = len(hd)-1

                current_name = gv(cname)
                current_father = gv(cfather)
                current_mobile = gv(cmobile)
                current_address = gv(caddress)
                current_aadhaar = gv(caadhar) if caadhar else ""
                current_annual = gv(cannual) if cannual else "0"
                current_adm = gv(cadm) if cadm else "0"

                st.info(f"**ID:** {sid}")
                with st.form("edit_form"):
                    nn = st.text_input("Name", value=current_name)
                    nf = st.text_input("Father", value=current_father)
                    nm = st.text_input("Mobile", value=current_mobile)
                    na = st.text_input("Address", value=current_address)
                    nd = st.text_input("Aadhaar", value=current_aadhaar)
                    nannual = st.number_input("Annual Fees Due", value=int(current_annual) if current_annual.isdigit() else 0)
                    nadm = st.number_input("Admission Fees Due", value=int(current_adm) if current_adm.isdigit() else 0)
                    if st.form_submit_button("Update"):
                        if cname: master_sheet.update_cell(rn, cname+1, nn)
                        if cfather: master_sheet.update_cell(rn, cfather+1, nf)
                        if cmobile: master_sheet.update_cell(rn, cmobile+1, nm)
                        master_sheet.update_cell(rn, caddress+1, na)
                        if caadhar: master_sheet.update_cell(rn, caadhar+1, nd)
                        master_sheet.update_cell(rn, cannual+1, str(nannual))
                        master_sheet.update_cell(rn, cadm+1, str(nadm))
                        st.success("Updated!")
                        st.cache_data.clear()
            except Exception as e: st.error(f"Error: {e}")

# =============================
# 15. ADD NEW STUDENT
# =============================
elif menu == "Add New Student":
    st.subheader(f"Enroll New Student – {selected_class}")
    existing_ids = []; existing_rolls = []
    if not df_master.empty and id_col:
        existing_ids = df_master[id_col].astype(str).tolist()
        if 'ROLL NO' in df_master.columns:
            try: existing_rolls = df_master['ROLL NO'].astype(int).tolist()
            except: pass
    prefix = "CME"
    max_s = 0
    for sid in existing_ids:
        if sid.startswith(prefix):
            num = sid[len(prefix):]
            if num.isdigit(): max_s = max(max_s, int(num))
    new_id = f"{prefix}{max_s+1:02d}"
    new_roll = 1 if not existing_rolls else max(existing_rolls)+1

    with st.form("add_student_form", clear_on_submit=True):
        st.info(new_id); st.caption("Auto ID")
        st.info(str(new_roll)); st.caption("Auto Roll")
        nn = st.text_input("Full Name *")
        nf = st.text_input("Father's Name *")
        nm = st.text_input("Mobile")
        na = st.text_input("Address")
        nd = st.text_input("Aadhaar")
        nannual = st.number_input("Annual Fees Due", value=0)
        nadm = st.number_input("Admission Fees Due", value=0)
        if st.form_submit_button("Enroll"):
            if not nn.strip() or not nf.strip():
                st.error("Name and Father required.")
            else:
                headers = master_sheet.row_values(1)
                row_data = {}
                row_data['ID'] = new_id
                row_data['NAME'] = nn.strip()
                row_data['ROLL NO'] = str(new_roll)
                row_data['FATHER'] = nf.strip()
                row_data['NODE'] = ""
                row_data['MOBILE'] = nm.strip() if nm else ""
                row_data['ANNUAL_FEE'] = str(nannual)
                row_data['ADMISSION_FEE'] = str(nadm)
                row_data['ADDRESS'] = na.strip() if na else ""
                row_data['AADHAR'] = nd.strip() if nd else ""
                for col in ['ID','NAME','ROLL NO','FATHER','NODE','MOBILE','ANNUAL_FEE','ADMISSION_FEE','ADDRESS','AADHAR']:
                    if col not in headers:
                        master_sheet.update_cell(1, len(headers)+1, col)
                        headers.append(col)
                final_row = [row_data.get(h, "") for h in headers]
                master_sheet.append_row(final_row, value_input_option='USER_ENTERED')
                attendance_sheet.append_row([new_id])
                st.success(f"Enrolled {nn}")
                st.balloons()
                st.cache_data.clear()
                st.rerun()
