import streamlit as st
import gspread
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd
import traceback
import io
import json
import base64

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
st.set_page_config(page_title="Cambridge Portal", page_icon="🏫", layout="wide")

# =====================================================================
# NAVY BLUE GLASSMORPHISM THEME (Optimised – no heavy animations)
# =====================================================================
st.markdown("""
<style>
/* ---------- Glass Cards ---------- */
div[data-testid="stVerticalBlock"] > div {
    background: rgba(30, 41, 59, 0.65);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
}

/* ---------- Buttons ---------- */
.stButton > button {
    border-radius: 10px;
    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
    border: none;
    color: white;
    font-weight: 600;
    padding: 8px 20px;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2d5a87 0%, #1e3a5f 100%);
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

/* ---------- Input Fields ---------- */
.stTextInput input, .stNumberInput input, .stSelectbox select {
    background-color: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    color: white !important;
}

/* ---------- Metric Cards ---------- */
[data-testid="metric-container"] {
    background: linear-gradient(145deg, #1e293b, #0f172a);
    border-radius: 14px;
    border: 1px solid #334155;
    padding: 16px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
}
[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    color: #fbbf24 !important;
}

/* ---------- Receipt Card ---------- */
.receipt-card {
    background: #1e2a3a;
    border: 1px dashed #f0c45a;
    border-radius: 12px;
    padding: 20px;
    margin: 20px 0;
}
.receipt-card h3 { color: #f0c45a; text-align: center; }
.receipt-card p { color: #e0e7f2; }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 2. LOGIN
# -----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["role"] = None

if not st.session_state["authenticated"]:
    st.markdown("""
    <style>
    .login-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 20px;
        padding: 40px;
        max-width: 400px;
        margin: 80px auto;
        box-shadow: 0 16px 40px rgba(0,0,0,0.4);
        text-align: center;
    }
    .login-card h2 { color: #fbbf24; margin-bottom: 30px; }
    </style>
    <div class="login-card">
    """, unsafe_allow_html=True)

    try:
        st.image("School_logo.png", width=180)
    except:
        pass
    st.markdown("<h2>Cambridge International School</h2>", unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)
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
# 4. CACHING FUNCTIONS (TTL = 1 hour)
# -----------------------------
@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=3600)
def load_all_class_data(class_name):
    master_sheet = find_sheet(f"MASTER_{class_name}")
    attendance_sheet = find_sheet(f"ATTENDANCE_{class_name}")
    fees_sheet = find_sheet(f"FEES_{class_name}")
    fee_struct = find_sheet("FEES_STRUCTURE")

    master_data = master_sheet.get_all_values() if master_sheet else []
    attendance_data = attendance_sheet.get_all_values() if attendance_sheet else []
    fees_data = fees_sheet.get_all_values() if fees_sheet else []
    fee_struct_data = fee_struct.get_all_values() if fee_struct else []
    return master_data, attendance_data, fees_data, fee_struct_data

@st.cache_data(ttl=3600)
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
master_raw, att_raw, fees_raw, fee_struct_raw = load_all_class_data(selected_class)

# Parse Master
df_master = pd.DataFrame()
student_list = []
if len(master_raw) > 1:
    headers = [h.strip() for h in master_raw[0]]
    df_master = pd.DataFrame(master_raw[1:], columns=headers)
    id_col = next((c for c in df_master.columns if c.upper() in ['ID', 'STUDENT ID']), None)
    name_col = next((c for c in df_master.columns if c.upper() in ['NAME', 'STUDENT NAME']), None)
    if id_col and name_col:
        student_list = [f"{row[id_col]} - {row[name_col]}" for _, row in df_master.iterrows()]

# Parse Attendance
attendance_data = att_raw

# Parse Fees
fees_data = fees_raw

# Fee structure
monthly_fee_map = load_fee_structure()
default_fee = monthly_fee_map.get(selected_class, 500)

# Sheet objects for updates
master_sheet = find_sheet(f"MASTER_{selected_class}")
attendance_sheet = find_sheet(f"ATTENDANCE_{selected_class}")
fees_sheet = find_sheet(f"FEES_{selected_class}")
if not all([master_sheet, attendance_sheet, fees_sheet]):
    st.error("Required sheets missing.")
    st.stop()

# Ensure columns exist
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
try:
    st.image("School_logo.png", width=180)
except:
    pass
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
        today_col_1b = att_headers.index(today_str)+1 if today_str in att_headers else None
        present = 0
        if today_col_1b and len(attendance_data)>1:
            today_idx = today_col_1b - 1
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

        # Top 5 Outstanding
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
# 9. STUDENT ATTENDANCE (Search + Batch Update)
# =============================
elif menu == "Student Attendance":
    st.subheader(f"Daily Attendance – {selected_class}")
    if not student_list: st.warning("No students.")
    else:
        search_term = st.text_input("Search Student by Name or ID", "")
        if search_term:
            filtered = [s for s in student_list if search_term.lower() in s.lower()]
        else:
            filtered = student_list

        sel = st.selectbox("Select Student", ["-- Select --"] + filtered)

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
        st.
