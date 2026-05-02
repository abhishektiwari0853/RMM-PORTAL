import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pandas as pd
import traceback
import io
from streamlit_option_menu import option_menu

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
st.set_page_config(page_title="RMM Administrative Portal", page_icon="🏫", layout="wide")

# =====================================================================
# CLEAN MINIMAL CSS – Professional White & Navy Theme
# =====================================================================
st.markdown("""
<style>
/* ========== Global ========== */
body {
    background-color: #f5f7fa;
}
.main {
    background-color: transparent;
}
/* ========== Sidebar ========== */
section[data-testid="stSidebar"] {
    background-color: #1a2744;
    border-right: 2px solid #2c3e6b;
}
section[data-testid="stSidebar"] * {
    color: #dce3f0 !important;
}
/* ========== Cards ========== */
div[data-testid="stVerticalBlock"] > div {
    background: white;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    margin-bottom: 16px;
}
/* ========== Buttons ========== */
.stButton > button {
    background-color: #1a3b5d;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
    transition: all 0.2s;
}
.stButton > button:hover {
    background-color: #2c5a8c;
    box-shadow: 0 4px 12px rgba(26,59,93,0.2);
}
/* ========== Inputs ========== */
.stTextInput input, .stNumberInput input, .stSelectbox select {
    border-radius: 6px;
    border: 1px solid #dce1e8;
    padding: 8px 12px;
}
/* ========== Tables ========== */
.stTable tbody tr:hover {
    background-color: #f1f5f9;
}
/* ========== Metric Cards ========== */
[data-testid="metric-container"] {
    background: white;
    border: 1px solid #e9eef2;
    border-radius: 10px;
    padding: 16px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}
[data-testid="metric-container"] label {
    color: #64748b;
    font-size: 13px;
}
[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    color: #1a3b5d;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 2. ROLE-BASED LOGIN (Clean Centered)
# -----------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["role"] = None

if not st.session_state["authenticated"]:
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        try:
            st.image("School_logo.png", width=140)
        except:
            pass
        st.markdown("<h2 style='text-align: center; color: #1a3b5d;'>School Portal Login</h2>", unsafe_allow_html=True)
        role = st.selectbox("Select Role", ["Teacher", "Clerk", "Principal"])
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            valid = False
            if role == "Teacher" and pwd == "TCH2024":
                valid = True
            elif role == "Clerk" and pwd == "CLK2024":
                valid = True
            elif role == "Principal" and pwd == "PRN2024":
                valid = True
            if valid:
                st.session_state["authenticated"] = True
                st.session_state["role"] = role
                st.rerun()
            else:
                st.error("Invalid Role or Password")
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
# 4. CACHING FUNCTIONS
# -----------------------------
@st.cache_data(ttl=600)
def get_sheet_names():
    return [ws.title.strip() for ws in wb.worksheets()]

def find_sheet(name):
    names = get_sheet_names()
    name_clean = name.strip().lower()
    for n in names:
        if n.lower() == name_clean:
            return wb.worksheet(n)
    for n in names:
        if name_clean in n.lower():
            return wb.worksheet(n)
    return None

def find_class_sheet(class_num, sheet_type):
    return find_sheet(f"{sheet_type}_{class_num}")

@st.cache_data(ttl=600)
def load_master_data(class_num):
    sheet = find_class_sheet(class_num, 'Master')
    if not sheet:
        return pd.DataFrame(), []
    raw = sheet.get_all_values()
    if len(raw) < 2:
        return pd.DataFrame(), []
    headers = [h.strip() for h in raw[0]]
    df = pd.DataFrame(raw[1:], columns=headers)
    id_col = next((c for c in df.columns if c.lower() == 'student id'), None)
    name_col = next((c for c in df.columns if c.lower() == 'name'), None)
    student_list = []
    if id_col and name_col:
        student_list = [f"{row[id_col]} - {row[name_col]}" for _, row in df.iterrows()]
    return df, student_list

@st.cache_data(ttl=600)
def load_attendance_data(class_num):
    sheet = find_class_sheet(class_num, 'Attendance')
    if sheet:
        return sheet.get_all_values()
    return []

@st.cache_data(ttl=600)
def load_fees_data(class_num):
    sheet = find_class_sheet(class_num, 'Fees')
    if sheet:
        return sheet.get_all_values()
    return []

@st.cache_data(ttl=600)
def load_fee_structure():
    sheet = find_sheet("Fee_Structure")
    if not sheet:
        return {}
    data = sheet.get_all_values()
    fee_map = {}
    if len(data) >= 2:
        for row in data[1:]:
            if len(row) >= 2:
                cls, fee = row[0].strip(), row[1].strip()
                if cls.isdigit() and fee.isdigit():
                    fee_map[cls] = int(fee)
    return fee_map

# -----------------------------
# 5. SIDEBAR + NAVIGATION
# -----------------------------
st.sidebar.header("Administration")
st.sidebar.markdown(f"**{st.session_state['role']}**")
selected_class = st.sidebar.selectbox("Class", ["7","8","9","10","11","12"])

role = st.session_state["role"]
menu_options = {
    "Teacher": ["Student Attendance","Attendance Report","Student Records","Edit Student Details","Add New Student","At-Risk Students"],
    "Clerk": ["Fee Collection","Daily Cash Report","Defaulter List","Add New Student","Student Records"],
    "Principal": ["Executive Dashboard","Student Attendance","Attendance Report","Fee Collection","Daily Cash Report","Defaulter List","Student Records","Edit Student Details","Add New Student","At-Risk Students"]
}[role]

icons = {
    "Executive Dashboard": "speedometer2","Student Attendance": "calendar-check","Attendance Report": "bar-chart-line",
    "Fee Collection": "cash-stack","Daily Cash Report": "graph-up-arrow","Defaulter List": "exclamation-triangle",
    "Student Records": "people","Edit Student Details": "pencil-square","Add New Student": "person-plus",
    "At-Risk Students": "exclamation-circle"
}
menu = option_menu(None, menu_options, [icons.get(o,"circle") for o in menu_options],
    menu_icon="cast", default_index=0,
    styles={
        "container": {"background-color": "#1a2744"},
        "icon": {"color": "#f0c45a"},
        "nav-link": {"--hover-color": "#233058"},
        "nav-link-selected": {"background-color": "#2c3e6b"},
    }
)

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# -----------------------------
# 6. LOAD DATA
# -----------------------------
df_master, student_list = load_master_data(selected_class)
id_col = next((c for c in df_master.columns if c.lower() == 'student id'), None) if not df_master.empty else None
name_col = next((c for c in df_master.columns if c.lower() == 'name'), None) if not df_master.empty else None

attendance_data = load_attendance_data(selected_class)
fees_data = load_fees_data(selected_class)
monthly_fee_map = load_fee_structure()
default_monthly_fee = monthly_fee_map.get(selected_class, 500)

master_sheet = find_class_sheet(selected_class, 'Master')
attendance_sheet = find_class_sheet(selected_class, 'Attendance')
fees_sheet = find_class_sheet(selected_class, 'Fees')
if not all([master_sheet, attendance_sheet, fees_sheet]):
    st.error("Sheets missing.")
    st.stop()

# -----------------------------
# 7. BRANDING
# -----------------------------
st.markdown("<h2 style='text-align: center; color: #1a3b5d;'>RAM MURTI MISHRA INTER COLLEGE</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b;'>Management System</p>", unsafe_allow_html=True)
st.divider()

# =============================
# 8. EXECUTIVE DASHBOARD
# =============================
if menu == "Executive Dashboard":
    st.subheader(f"Dashboard – Class {selected_class}")
    if df_master.empty:
        st.warning("No data.")
    else:
        total = len(df_master)
        today = datetime.now().strftime("%d-%m-%Y")
        att_h = attendance_data[0] if attendance_data else []
        col_idx = att_h.index(today)+1 if today in att_h else None
        present = 0
        if col_idx and len(attendance_data)>1:
            for row in attendance_data[1:]:
                if col_idx < len(row) and row[col_idx].strip().upper() == 'P':
                    present += 1
        att_pct = (present/total*100) if total else 0

        today_fees = 0
        if fees_data and len(fees_data)>1:
            for r in fees_data[1:]:
                if len(r)>=4 and r[3].split(' ')[0] == today and r[1].isdigit():
                    today_fees += int(r[1])

        current_month = datetime.now().month
        current_year = datetime.now().year
        month_col = 0
        if fees_data and len(fees_data)>1:
            for r in fees_data[1:]:
                if len(r)>=4:
                    try:
                        d = datetime.strptime(r[3].split(' ')[0], "%d-%m-%Y")
                        if d.month == current_month and d.year == current_year and r[1].isdigit():
                            month_col += int(r[1])
                    except: pass

        monthly_fee = monthly_fee_map.get(selected_class, 500)
        expected_monthly = total * monthly_fee
        col_pct = (month_col/expected_monthly*100) if expected_monthly else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Students", total)
        col2.metric("Today Att.", f"{att_pct:.0f}% ({present}/{total})")
        col3.metric("Today Fees", f"₹{today_fees}")
        col4.metric("Month Fees", f"₹{month_col} ({col_pct:.0f}%)")

        if not df_master.empty:
            def calc(row):
                paid = int(row['Total_Fees']) if 'Total_Fees' in row and str(row['Total_Fees']).isdigit() else 0
                if current_month>=4: months = current_month-4+1
                else: months = current_month+9
                expected = months * monthly_fee
                return max(0, expected - paid)
            temp = df_master.copy()
            temp['Outstanding'] = temp.apply(calc, axis=1)
            top5 = temp.nlargest(5, 'Outstanding')[['Name','Outstanding']]
        else: top5 = pd.DataFrame()
        st.write("**Top 5 Outstanding**")
        if not top5.empty: st.dataframe(top5)
        else: st.write("None")

# =============================
# 9. STUDENT ATTENDANCE
# =============================
elif menu == "Student Attendance":
    st.subheader(f"Daily Attendance – Class {selected_class}")
    if not student_list:
        st.warning("No students.")
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
                    cnt = 0
                    for sid in ids:
                        try:
                            cell = attendance_sheet.find(sid)
                            attendance_sheet.update_cell(cell.row, ci, "P")
                            cnt += 1
                        except: pass
                    st.success(f"All {cnt} marked")
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
                        ac = 0
                        for sid in ids:
                            try:
                                cell = attendance_sheet.find(sid)
                                val = attendance_sheet.cell(cell.row, ci).value
                                if not val or val.strip()=="":
                                    attendance_sheet.update_cell(cell.row, ci, "A")
                                    ac += 1
                            except: pass
                        st.success(f"Marked {ac} absent")
                        st.cache_data.clear()
                except Exception as e: st.error(f"Error: {e}")

# =============================
# 10. ATTENDANCE REPORT
# =============================
elif menu == "Attendance Report":
    st.subheader(f"Monthly Attendance Report – Class {selected_class}")
    months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    sel_month = st.selectbox("Month", months, index=datetime.now().month-1)
    sel_year = st.number_input("Year", 2020,2030, datetime.now().year)
    mn = months.index(sel_month)+1
    ms = f"{mn:02d}"
    if len(attendance_data)<2:
        st.warning("No data.")
    else:
        att_headers = attendance_data[0]
        dcols = []
        cidx = []
        for i,h in enumerate(att_headers):
            if i==0: continue
            p = h.split('-')
            if len(p)==3 and p[1]==ms and p[2]==str(sel_year):
                dcols.append(h)
                cidx.append(i)
        if not dcols:
            st.warning(f"No records for {sel_month} {sel_year}")
        else:
            total_days = len(dcols)
            recs = []
            for row in attendance_data[1:]:
                sid = row[0]
                name = "N/A"
                mask = df_master[id_col].astype(str)==sid if not df_master.empty else None
                if mask is not None and mask.any():
                    name = df_master.loc[mask, name_col].values[0]
                present = sum(1 for ci in cidx if ci<len(row) and row[ci].strip().upper()=='P')
                pct = (present/total_days*100) if total_days else 0
                recs.append({"Student ID":sid,"Name":name,"Working Days":total_days,"Present":present,"Attendance %":round(pct,1)})
            df_rep = pd.DataFrame(recs)
            def hl(val):
                return 'background-color: #ffcccc' if val<75 else ''
            st.dataframe(df_rep.style.map(hl, subset=['Attendance %']), use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                df_rep.to_excel(w, index=False, sheet_name='Attendance')
            st.download_button("Download Excel", buf.getvalue(), f"Attendance_{selected_class}_{sel_month}_{sel_year}.xlsx")

# =============================
# 11. FEE COLLECTION
# =============================
elif menu == "Fee Collection":
    if role not in ["Clerk","Principal"]:
        st.error("Access Denied"); st.stop()
    st.subheader(f"Fee Counter – Class {selected_class}")
    if not student_list:
        st.warning("No students.")
    else:
        sel = st.selectbox("Select Student", ["-- Select --"]+student_list)
        if sel != "-- Select --":
            sid = sel.split(" - ")[0]
            try:
                mc = master_sheet.find(sid)
                mr = master_sheet.row_values(mc.row)
                cur = int(mr[6]) if len(mr)>=7 and str(mr[6]).isdigit() else 0
                st.info(f"**Student:** {mr[1]} | **Father:** {mr[3]} | **Paid:** ₹{cur}")
                with st.form("fee_form", clear_on_submit=True):
                    amt = st.number_input("Amount", min_value=0)
                    mo = st.selectbox("Month", ["April","May","June","July","August","September","October","November","December","January","February","March"])
                    mode = st.selectbox("Mode", ["Cash","Online","Cheque"])
                    if st.form_submit_button("Process Payment"):
                        new = cur + amt
                        master_sheet.update_cell(mc.row, 7, str(new))
                        ts = datetime.now().strftime("%d-%m-%Y %H:%M")
                        fees_sheet.insert_row([sid, amt, mo, f"{ts} {mode}"], index=2)
                        st.success(f"Paid ₹{amt}, New Total ₹{new}")
                        st.cache_data.clear()
            except Exception as e: st.error(f"Error: {e}")

# =============================
# 12. DAILY CASH REPORT
# =============================
elif menu == "Daily Cash Report":
    if role not in ["Clerk","Principal"]:
        st.error("Access Denied"); st.stop()
    st.subheader(f"Today's Financial Summary – Class {selected_class}")
    today_str = datetime.now().strftime("%d-%m-%Y")
    if fees_data and len(fees_data)>1:
        fh = fees_data[0]
        today_rows = [r for r in fees_data[1:] if len(r)>=4 and r[3].split(' ')[0]==today_str]
        if today_rows:
            amt_col = fh.index('Amount') if 'Amount' in fh else 1
            total = sum(int(r[amt_col]) for r in today_rows if r[amt_col].isdigit())
            st.metric("Total Today", f"₹{total}")
            st.dataframe(pd.DataFrame(today_rows, columns=fh)[['Student ID','Amount','Month','Date of payment']])
        else: st.info("No transactions today.")
    else: st.info("No fee records.")

# =============================
# 13. DEFAULTER LIST
# =============================
elif menu == "Defaulter List":
    if role not in ["Clerk","Principal"]:
        st.error("Access Denied"); st.stop()
    st.subheader(f"Fee Defaulter List – Class {selected_class}")
    if df_master.empty:
        st.warning("No students.")
    else:
        cur_month = datetime.now().month
        if cur_month>=4: mcount = cur_month-4+1
        else: mcount = cur_month+9
        monthly_fee = monthly_fee_map.get(selected_class, 500)
        expected_total = mcount * monthly_fee
        defs = []
        for _, s in df_master.iterrows():
            sid = str(s[id_col])
            name = s[name_col]
            paid = int(s.get('Total_Fees',0)) if str(s.get('Total_Fees',0)).isdigit() else 0
            out = max(0, expected_total - paid)
            last = "N/A"
            if fees_data:
                for r in fees_data[1:]:
                    if r[0].upper()==sid.upper():
                        ds = r[3] if len(r)>3 else ""
                        if ds: last = ds.split(' ')[0]
            defs.append({"Student ID":sid,"Name":name,"Total Paid":paid,"Expected":expected_total,"Outstanding":out,"Last Paid":last})
        df_def = pd.DataFrame(defs).sort_values("Outstanding", ascending=False)
        def hl(val):
            if val>1000: return 'background-color:#ffcccc'
            elif val>0: return 'background-color:#fff9c4'
            return ''
        st.dataframe(df_def.style.map(hl, subset=['Outstanding']), use_container_width=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
            df_def.to_excel(w, index=False)
        st.download_button("Download Excel", buf.getvalue(), f"Defaulters_{selected_class}.xlsx")

# =============================
# 14. STUDENT RECORDS
# =============================
elif menu == "Student Records":
    st.subheader(f"Student Profile – Class {selected_class}")
    if not student_list:
        st.warning("No students.")
    else:
        sel = st.selectbox("Select Student", ["-- Select --"]+student_list)
        if sel != "-- Select --":
            sid = sel.split(" - ")[0]
            mask = df_master[id_col].astype(str)==sid
            if mask.any():
                sd = df_master[mask].iloc[0]
                name = sd.get('Name','')
                roll = sd.get('Roll No','')
                father = sd.get('Father name', sd.get('Father Name',''))
                mobile = sd.get('Mobile','')
                total = sd.get('Total_Fees','0')
                addr = sd.get('Adress', sd.get('Address','N/A'))
                st.info(f"**{name}** | Roll: {roll}")
                c1,c2 = st.columns(2)
                c1.write(f"Father: {father}")
                c1.write(f"Address: {addr}")
                c2.write(f"Mobile: {mobile}")
                c2.write(f"Fees Paid: ₹{total}")
                st.divider()
                st.subheader("Fee History")
                if fees_data and len(fees_data)>1:
                    fh = fees_data[0]
                    hist = [r for r in fees_data[1:] if r[0].upper()==sid.upper()]
                    if hist:
                        st.table([fh]+hist)
                        df_h = pd.DataFrame(hist, columns=fh)
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
                            df_h.to_excel(w, index=False)
                        st.download_button("Download History", buf.getvalue(), f"FeeHistory_{sid}.xlsx")
                    else: st.write("No history.")
                else: st.write("No records.")
            else: st.warning("Not found.")

# =============================
# 15. EDIT STUDENT DETAILS
# =============================
elif menu == "Edit Student Details":
    st.subheader(f"Edit Student – Class {selected_class}")
    if not student_list:
        st.warning("No students.")
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
                    n=n.lower()
                    for i,h in enumerate(hd):
                        if h.lower()==n: return i
                    for i,h in enumerate(hd):
                        if n in h.lower(): return i
                    return None
                cn = fc('name'); cf = fc('father'); cm = fc('mobile'); ca = fc('adress') or fc('address'); cad = fc('aadhar')
                def sg(i):
                    return rd[i] if i<len(rd) else ""
                cname = sg(cn); fname = sg(cf); mob = sg(cm); addr = sg(ca); aad = sg(cad) if cad else ""
                croll = sg(fc('roll no')) if fc('roll no') else "N/A"
                st.info(f"**ID:** {sid} | Roll: {croll}")
                with st.form("edit_form"):
                    nn = st.text_input("Name", value=cname)
                    nf = st.text_input("Father", value=fname)
                    nm = st.text_input("Mobile", value=mob)
                    na = st.text_input("Address", value=addr)
                    nd = st.text_input("Aadhaar", value=aad)
                    if st.form_submit_button("Update"):
                        up = []
                        if nn!=cname and cn is not None: up.append((cn,nn))
                        if nf!=fname and cf is not None: up.append((cf,nf))
                        if nm!=mob and cm is not None: up.append((cm,nm))
                        if na!=addr and ca is not None: up.append((ca,na))
                        if nd!=aad and cad is not None: up.append((cad,nd))
                        if not up: st.info("No changes.")
                        else:
                            for ci,v in up: master_sheet.update_cell(rn, ci+1, v)
                            st.success("Updated!")
                            st.cache_data.clear()
            except Exception as e: st.error(f"Error: {e}")

# =============================
# 16. ADD NEW STUDENT
# =============================
elif menu == "Add New Student":
    st.subheader(f"Enroll New Student – Class {selected_class}")
    existing_ids = []
    existing_rolls = []
    if not df_master.empty:
        il = next((c for c in df_master.columns if c.lower()=='student id'), None)
        rl = next((c for c in df_master.columns if c.lower()=='roll no'), None)
        if il: existing_ids = df_master[il].astype(str).tolist()
        if rl:
            try: existing_rolls = df_master[rl].astype(int).tolist()
            except: pass
    prefix = f"RMEC{selected_class}"
    max_s = 0
    for sid in existing_ids:
        if sid.startswith(prefix):
            num = sid[len(prefix):]
            if num.isdigit(): max_s = max(max_s, int(num))
    new_id = f"{prefix}{max_s+1:03d}"
    new_roll = 1 if not existing_rolls else max(existing_rolls)+1

    with st.form("add_student_form", clear_on_submit=True):
        st.info(new_id); st.caption("Auto ID")
        st.info(str(new_roll)); st.caption("Auto Roll")
        nn = st.text_input("Full Name *")
        nf = st.text_input("Father's Name *")
        nm = st.text_input("Mobile")
        na = st.text_input("Address")
        nd = st.text_input("Aadhaar")
        if st.form_submit_button("Enroll"):
            if not nn.strip() or not nf.strip():
                st.error("Name and Father required.")
            else:
                new_row = [new_id, nn.strip(), str(new_roll), nf.strip(), "", nm.strip() if nm else "", "0", na.strip() if na else "", "", nd.strip() if nd else ""]
                try:
                    master_sheet.append_row(new_row, value_input_option='USER_ENTERED')
                    attendance_sheet.append_row([new_id])
                    st.success(f"Enrolled {nn}")
                    st.balloons()
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# =============================
# 17. AT-RISK STUDENTS
# =============================
elif menu == "At-Risk Students":
    st.subheader(f"Dropout Risk – Class {selected_class}")
    if len(attendance_data)<2:
        st.warning("No data.")
    else:
        ah = attendance_data[0]
        dm = {}
        for i,h in enumerate(ah):
            if i==0: continue
            p = h.split('-')
            if len(p)==3:
                try: dm[i] = datetime.strptime(h, "%d-%m-%Y")
                except: pass
        sorted_cols = sorted(dm.items(), key=lambda x: x[1])
        risk = []
        for row in attendance_data[1:]:
            sid = row[0]
            name = "N/A"
            if not df_master.empty:
                mask = df_master[id_col].astype(str)==sid
                if mask.any(): name = df_master.loc[mask, name_col].values[0]
            maxc = 0; cur = 0
            for ci,_ in sorted_cols:
                val = row[ci].strip().upper() if ci<len(row) else ""
                if val!='P': cur+=1
                else: cur=0
                maxc = max(maxc, cur)
            if maxc>=5: risk.append((sid, name, maxc))
        if risk:
            df_r = pd.DataFrame(risk, columns=["Student ID","Name","Consecutive Absences"])
            st.warning(f"Total at risk: {len(risk)}")
            st.dataframe(df_r.style.map(lambda x: 'background-color:#ffcccc' if isinstance(x,int) and x>=5 else '', subset=['Consecutive Absences']))
        else: st.success("No student with 5+ consecutive absences.")
