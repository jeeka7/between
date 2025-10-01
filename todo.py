import streamlit as st
import requests
import json
from datetime import date
import uuid  # For unique keys in dynamic elements
import os

# Page config for minimalism
st.set_page_config(page_title="Between", page_icon="📝", layout="wide")
st.markdown("""
    <style>
    .main {background-color: #f9fafb;}
    .stTextInput > div > div > input {border-radius: 8px; border: 1px solid #d1d5db;}
    .stSelectbox > div > div > select {border-radius: 8px; border: 1px solid #d1d5db;}
    .stCheckbox > div {margin-right: 10px;}
    .stButton > button {border-radius: 6px; background-color: #3b82f6; color: white;}
    </style>
""", unsafe_allow_html=True)

# HTTP client functions
@st.cache_data(ttl=300)  # Cache queries for 5 min
def query(sql, params=None):
    """Execute SELECT and return list of tuples (rows)."""
    return _execute(sql, params, is_query=True)

def execute(sql, params=None):
    """Execute INSERT/UPDATE/DELETE/CREATE, returns True if successful."""
    return _execute(sql, params, is_query=False) is not None

def _execute(sql, params=None, is_query=False):
    http_url = st.secrets["turso"]["http_url"]
    auth_token = st.secrets["turso"]["token"]
    url = f"{http_url}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    stmt = {"sql": sql}
    if params:
        stmt["args"] = [{"type": "null" if p is None else ("integer" if isinstance(p, int) else "text"), "value": str(p) if p is not None else None} for p in params]
    payload = {
        "requests": [
            {"type": "execute", "stmt": stmt},
            {"type": "close"}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            st.error(f"DB Error: {response.status_code} - {response.text}")
            return None
        data = response.json()
        if not data.get("results"):
            return [] if is_query else True
        result = data["results"][0]
        if is_query and result.get("type") == "rows":
            columns = result.get("columns", [])
            rows = result.get("rows", [])
            return [tuple(row) for row in rows]  # List of tuples, indexed by column order
        return True
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

# Init tables (run once after login)
def init_tables():
    execute("""
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT CHECK(type IN ('Financial', 'Simple')) NOT NULL,
            creation_date DATE NOT NULL,
            deadline_date DATE,
            pinned INTEGER DEFAULT 0
        )
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            task_text TEXT NOT NULL,
            important INTEGER DEFAULT 0,
            urgent INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY (list_id) REFERENCES lists (id) ON DELETE CASCADE
        )
    """)

# Session state for login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Admin login (minimal form)
if not st.session_state.logged_in:
    st.title("📝 Between")
    st.markdown("**To-Do Lists Manager**")
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            password = st.text_input("Admin Password", type="password")
        with col2:
            if st.button("Login", use_container_width=True):
                if password == st.secrets["password"]:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
    st.stop()

# Main app (after login)
st.title("📝 Between")
init_tables()  # Ensure tables exist

# Sidebar: Lists overview
st.sidebar.title("📋 Lists")
st.sidebar.markdown("---")

# Fetch lists (pinned first, then by creation date)
lists_data = query("SELECT * FROM lists ORDER BY pinned DESC, creation_date ASC")
list_dict = {row[1]: row[0] for row in lists_data} if lists_data else {}

if lists_data:
    # Select list
    selected_name = st.sidebar.selectbox("Select List", ["Create New"] + list(list_dict.keys()))
    
    if selected_name != "Create New" and selected_name in list_dict:
        list_id = list_dict[selected_name]
        selected_data = next(row for row in lists_data if row[1] == selected_name)
        
        # Main content: List details and tasks
        st.header(selected_name)
        
        # Show dates
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            st.metric("Created", selected_data[3])
        with col_date2:
            if selected_data[4]:
                st.metric("Deadline", selected_data[4])
            else:
                st.write("No deadline")
        
        # Type accent
        type_color = "#3b82f6" if selected_data[2] == "Financial" else "#6b7280"
        st.markdown(f"**Type:** {selected_data[2]}")
        st.markdown(f"<div style='width: 100%; height: 4px; background-color: {type_color}; border-radius: 2px;'></div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Fetch and display tasks (sorted: important+urgent > important > urgent > none)
        tasks_data = query(
            "SELECT * FROM tasks WHERE list_id = ? ORDER BY (important + urgent) DESC, important DESC, urgent DESC, id ASC",
            [list_id]
        )
        
        for task in tasks_data:
            key_prefix = str(uuid.uuid4())  # Unique keys for dynamic reruns
            col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])
            
            with col1:
                edited_text = st.text_input("", value=task[2], placeholder="Task description", key=f"{key_prefix}_text")  # task[2] is task_text
            with col2:
                important = st.checkbox("!", value=bool(task[3]), key=f"{key_prefix}_imp")  # task[3] important
            with col3:
                urgent = st.checkbox("⚡", value=bool(task[4]), key=f"{key_prefix}_urg")  # task[4] urgent
            with col4:
                completed = st.checkbox("✓", value=bool(task[5]), key=f"{key_prefix}_comp")  # task[5] completed
            with col5:
                col_up, col_del = st.columns(2)
                with col_up:
                    if st.button("💾", key=f"{key_prefix}_update"):
                        execute(
                            "UPDATE tasks SET task_text = ?, important = ?, urgent = ?, completed = ? WHERE id = ?",
                            [edited_text, int(important), int(urgent), int(completed), task[0]]
                        )
                        st.success("Updated!")
                        st.rerun()
                with col_del:
                    if st.button("🗑️", key=f"{key_prefix}_delete"):
                        execute("DELETE FROM tasks WHERE id = ?", [task[0]])
                        st.success("Deleted!")
                        st.rerun()
        
        # Add new task form
        st.markdown("### + Add Task")
        with st.form("add_task", clear_on_submit=True):
            new_text = st.text_area("Description", placeholder="What needs to be done?")
            col_imp, col_urg = st.columns(2)
            with col_imp:
                new_important = st.checkbox("Important (!)")
            with col_urg:
                new_urgent = st.checkbox("Urgent (⚡)")
            add_btn = st.form_submit_button("Add Task", use_container_width=True)
            if add_btn and new_text.strip():
                execute(
                    "INSERT INTO tasks (list_id, task_text, important, urgent) VALUES (?, ?, ?, ?)",
                    [list_id, new_text, int(new_important), int(new_urgent)]
                )
                st.success("Task added!")
                st.rerun()
    
    # Manage lists (pin/delete) - in sidebar expander for cleanliness
    with st.sidebar.expander("Manage Lists", expanded=False):
        for lst in lists_data:
            col_m1, col_m2, col_m3 = st.columns([3, 1, 1])
            with col_m1:
                st.write(f"**{lst[1]}** ({lst[2]})")
            with col_m2:
                current_pin = st.checkbox("📌 Pin", value=bool(lst[5]), key=f"pin_{lst[0]}")
            with col_m3:
                if st.button("🗑️", key=f"del_lst_{lst[0]}"):
                    execute("DELETE FROM lists WHERE id = ?", [lst[0]])
                    st.success(f"Deleted {lst[1]}")
                    st.rerun()
            if st.button("Update", key=f"up_pin_{lst[0]}"):
                execute("UPDATE lists SET pinned = ? WHERE id = ?", [int(current_pin), lst[0]])
                st.success("Pinned updated!")
                st.rerun()
        st.markdown("---")

else:
    st.info("No lists yet. Create one below.")

# Create new list form (sidebar)
st.sidebar.markdown("### + New List")
with st.sidebar.form("new_list", clear_on_submit=True):
    new_name = st.text_input("Name", placeholder="Unique list name")
    list_type = st.selectbox("Type", ["Simple", "Financial"])
    deadline = st.date_input("Deadline (optional)")
    create_btn = st.form_submit_button("Create List", use_container_width=True)
    if create_btn and new_name.strip():
        today = date.today().isoformat()
        deadline_str = deadline.isoformat() if deadline else None
        if execute(
            "INSERT INTO lists (name, type, creation_date, deadline_date, pinned) VALUES (?, ?, ?, ?, 0)",
            [new_name, list_type, today, deadline_str]
        ):
            st.sidebar.success("List created!")
            st.rerun()
        else:
            st.sidebar.error("Error: List name must be unique.")

# Footer for minimalism
st.markdown("---")
st.markdown("<small>Powered by Turso HTTP API & Streamlit</small>", unsafe_allow_html=True)
