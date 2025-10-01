import streamlit as st
import libsql
from datetime import date
import uuid  # For unique keys in dynamic elements

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

# Database connection
@st.cache_resource
def init_db():
    db_url = st.secrets["turso"]["url"]
    auth_token = st.secrets["turso"]["token"]
    conn = libsql.connect("between.db", sync_url=db_url, auth_token=auth_token)
    conn.sync()  # Initial sync
    
    # Create tables if not exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT CHECK(type IN ('Financial', 'Simple')) NOT NULL,
            creation_date DATE NOT NULL,
            deadline_date DATE,
            pinned INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
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
    conn.sync()  # Sync schema changes
    return conn

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
conn = init_db()  # Re-init post-login

# Sidebar: Lists overview
st.sidebar.title("📋 Lists")
st.sidebar.markdown("---")

# Fetch lists (pinned first, then by creation date)
cur = conn.execute("SELECT * FROM lists ORDER BY pinned DESC, creation_date ASC")
lists_data = cur.fetchall()
list_dict = {row[1]: row[0] for row in lists_data}  # name: id

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
        cur_tasks = conn.execute(
            "SELECT * FROM tasks WHERE list_id = ? ORDER BY (important + urgent) DESC, important DESC, urgent DESC, id ASC",
            [list_id]
        )
        tasks_data = cur_tasks.fetchall()
        
        for task in tasks_data:
            key_prefix = str(uuid.uuid4())  # Unique keys for dynamic reruns
            col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])
            
            with col1:
                edited_text = st.text_input("", value=task[3], placeholder="Task description", key=f"{key_prefix}_text")
            with col2:
                important = st.checkbox("!", value=bool(task[4]), key=f"{key_prefix}_imp")
            with col3:
                urgent = st.checkbox("⚡", value=bool(task[5]), key=f"{key_prefix}_urg")
            with col4:
                completed = st.checkbox("✓", value=bool(task[6]), key=f"{key_prefix}_comp")
            with col5:
                if st.button("💾", key=f"{key_prefix}_update", use_container_width=True):
                    conn.execute(
                        "UPDATE tasks SET task_text = ?, important = ?, urgent = ?, completed = ? WHERE id = ?",
                        [edited_text, int(important), int(urgent), int(completed), task[0]]
                    )
                    conn.sync()
                    st.success("Updated!")
                    st.rerun()
                if st.button("🗑️", key=f"{key_prefix}_delete", use_container_width=True):
                    conn.execute("DELETE FROM tasks WHERE id = ?", [task[0]])
                    conn.sync()
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
                conn.execute(
                    "INSERT INTO tasks (list_id, task_text, important, urgent) VALUES (?, ?, ?, ?)",
                    [list_id, new_text, int(new_important), int(new_urgent)]
                )
                conn.sync()
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
                    conn.execute("DELETE FROM lists WHERE id = ?", [lst[0]])
                    conn.sync()
                    st.success(f"Deleted {lst[1]}")
                    st.rerun()
            if st.button("Update", key=f"up_pin_{lst[0]}", use_container_width=True):
                conn.execute("UPDATE lists SET pinned = ? WHERE id = ?", [int(current_pin), lst[0]])
                conn.sync()
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
    deadline = st.date_input("Deadline (optional)", value=None)
    create_btn = st.form_submit_button("Create List", use_container_width=True)
    if create_btn and new_name.strip():
        today = date.today().isoformat()
        try:
            conn.execute(
                "INSERT INTO lists (name, type, creation_date, deadline_date, pinned) VALUES (?, ?, ?, ?, 0)",
                [new_name, list_type, today, deadline.isoformat() if deadline else None]
            )
            conn.sync()
            st.sidebar.success("List created!")
            st.rerun()
        except Exception as e:
            st.sidebar.error("Error: List name must be unique.")

# Footer for minimalism
st.markdown("---")
st.markdown("<small>Powered by Turso & Streamlit</small>", unsafe_allow_html=True)
