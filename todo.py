import streamlit as st
from datetime import datetime, date
import uuid
import os
import libsql_client
import nest_asyncio

# Apply the patch for asyncio to allow nested event loops. This is crucial for compatibility.
nest_asyncio.apply()

# --- DATABASE SETUP ---
@st.cache_resource
def get_turso_client():
    """Establishes a cached, single connection to the Turso/libSQL database."""
    url = st.secrets.get("TURSO_DATABASE_URL")
    auth_token = st.secrets.get("TURSO_AUTH_TOKEN")
    
    if not url or not auth_token:
        st.error("Turso database credentials are not configured. Please set secrets.")
        st.stop()
        
    # Force an HTTPS connection which is more stable in Streamlit Cloud environments
    if url.startswith("libsql://"):
        url = "https" + url[6:]
        
    try:
        return libsql_client.create_client(url=url, auth_token=auth_token)
    except Exception as e:
        st.error(f"Failed to initialize the Turso client. Please check your credentials. Error: {e}")
        st.exception(e)
        st.stop()

def _convert_result_to_dicts(result):
    """
    Helper function to convert Turso query results into a list of dictionaries.
    This version gracefully handles empty results which may lack the .rows attribute.
    """
    if not hasattr(result, 'rows') or not result.rows:
        return []
        
    columns = result.columns
    return [dict(zip(columns, row)) for row in result.rows]

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    try:
        client = get_turso_client()
        client.batch([
            """
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                list_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                important INTEGER NOT NULL DEFAULT 0,
                urgent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                deadline TEXT,
                FOREIGN KEY (list_id) REFERENCES lists (id) ON DELETE CASCADE
            )
            """
        ])
        return True
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        st.exception(e)
        st.stop()

# --- DATABASE CRUD OPERATIONS ---
def db_create_list(name, list_type):
    client = get_turso_client()
    try:
        client.execute(
            "INSERT INTO lists (name, type, pinned, created_at) VALUES (?, ?, ?, ?)",
            (name, list_type, 0, datetime.now().isoformat())
        )
        # Clear the data cache whenever a list is created
        st.cache_data.clear()
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            st.error("A list with this name already exists.")
        else:
            st.error(f"Database error: {e}")

@st.cache_data
def db_get_all_lists():
    """Gets all lists from the database. Cached for performance."""
    client = get_turso_client()
    rs = client.execute("SELECT * FROM lists")
    lists = _convert_result_to_dicts(rs)
    for lst in lists:
        lst['pinned'] = bool(lst['pinned'])
        lst['created_at'] = datetime.fromisoformat(lst['created_at'])
    return lists

@st.cache_data
def db_get_list(list_id):
    """Gets a single list by its ID. Cached for performance."""
    client = get_turso_client()
    rs = client.execute("SELECT * FROM lists WHERE id = ?", (list_id,))
    lists = _convert_result_to_dicts(rs)
    if not lists: return None
    lst = lists[0]
    lst['pinned'] = bool(lst['pinned'])
    lst['created_at'] = datetime.fromisoformat(lst['created_at'])
    return lst

def db_toggle_pin_list(list_id, current_pin_status):
    client = get_turso_client()
    client.execute("UPDATE lists SET pinned = ? WHERE id = ?", (int(not current_pin_status), list_id))
    st.cache_data.clear()

def db_delete_list(list_id):
    client = get_turso_client()
    client.execute("DELETE FROM lists WHERE id = ?", (list_id,))
    st.cache_data.clear()

def db_add_task(list_id, text, deadline, important, urgent):
    deadline_str = deadline.isoformat() if deadline else None
    client = get_turso_client()
    client.execute(
        "INSERT INTO tasks (id, list_id, text, completed, important, urgent, created_at, deadline) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), list_id, text, 0, int(important), int(urgent), datetime.now().isoformat(), deadline_str)
    )
    st.cache_data.clear()
    
@st.cache_data
def db_get_tasks_for_list(list_id):
    """Gets all tasks for a specific list. Cached for performance."""
    client = get_turso_client()
    rs = client.execute("SELECT * FROM tasks WHERE list_id = ?", (list_id,))
    tasks = _convert_result_to_dicts(rs)
    for task in tasks:
        task['completed'] = bool(task['completed'])
        task['important'] = bool(task['important'])
        task['urgent'] = bool(task['urgent'])
        task['created_at'] = datetime.fromisoformat(task['created_at'])
        task['deadline'] = date.fromisoformat(task['deadline']) if task['deadline'] else None
    return tasks

def db_update_task_completion(task_id, completed):
    client = get_turso_client()
    client.execute("UPDATE tasks SET completed = ? WHERE id = ?", (int(completed), task_id))
    st.cache_data.clear()

def db_delete_task(task_id):
    client = get_turso_client()
    client.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    st.cache_data.clear()

def db_update_task_text(task_id, new_text):
    client = get_turso_client()
    client.execute("UPDATE tasks SET text = ? WHERE id = ?", (new_text, task_id))
    st.cache_data.clear()

# --- HELPER FUNCTIONS ---
def get_task_priority(task):
    if task['important'] and task['urgent']: return 4
    if task['important']: return 3
    if task['urgent']: return 2
    return 1

def sort_lists(lists):
    return sorted(lists, key=lambda x: (not x['pinned'], x['created_at']))

def sort_tasks(tasks):
    return sorted(tasks, key=lambda x: (x['completed'], -get_task_priority(x), x['created_at']))

# --- UI COMPONENT FUNCTIONS ---
def local_css():
    """Applies custom CSS for a minimalist look and feel."""
    st.markdown("""
    <style>
        body { font-family: 'Inter', sans-serif; }
        #MainMenu, footer { visibility: hidden; }
        .completed-task { text-decoration: line-through; color: #888; }
        div.stButton > button { width: 100%; border-radius: 5px; }
        .main .block-container { padding-top: 2rem; }
    </style>
    """, unsafe_html=True)

def initialize_state():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'selected_list_id' not in st.session_state: st.session_state.selected_list_id = None
    if 'db_initialized' not in st.session_state: st.session_state.db_initialized = False
    if 'editing_task_id' not in st.session_state: st.session_state.editing_task_id = None

def login_page():
    st.title("✅ Between")
    st.markdown("Your minimalist to-do list manager.")
    ADMIN_PASSWORD = "admin" 
    with st.form("login_form"):
        password = st.text_input("Admin Password", type="password")
        if st.form_submit_button("Login"):
            if password == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Incorrect password")

def main_app_ui():
    local_css()
    with st.sidebar:
        st.title("Your Lists")
        with st.expander("➕ Create New List"):
            with st.form("new_list_form", clear_on_submit=True):
                new_list_name = st.text_input("List Name")
                new_list_type = st.selectbox("List Type", ["Simple", "Financial"])
                if st.form_submit_button("Create List") and new_list_name:
                    db_create_list(new_list_name, new_list_type)
                    st.success(f"List '{new_list_name}' created!")
                    st.rerun()
        st.markdown("---")
        sorted_list_items = sort_lists(db_get_all_lists())
        if not sorted_list_items:
            st.write("No lists yet. Create one!")
        else:
            for lst in sorted_list_items:
                col1, col2, col3 = st.columns([5, 1, 1])
                if col1.button(f"{'📌' if lst['pinned'] else '📝'} {lst['name']}", key=f"select_{lst['id']}"):
                    st.session_state.selected_list_id = lst['id']
                    st.rerun()
                if col2.button("📍", key=f"pin_{lst['id']}", help="Pin/Unpin list"):
                    db_toggle_pin_list(lst['id'], lst['pinned'])
                    st.rerun()
                if col3.button("🗑️", key=f"delete_{lst['id']}", help="Delete list"):
                    db_delete_list(lst['id'])
                    if st.session_state.selected_list_id == lst['id']: st.session_state.selected_list_id = None
                    st.rerun()

    if not st.session_state.selected_list_id:
        st.title("Select a list to get started")
    else:
        current_list = db_get_list(st.session_state.selected_list_id)
        if not current_list:
            st.error("The selected list may have been deleted.")
            st.session_state.selected_list_id = None
            st.rerun()
        st.header(f"{current_list['name']} ({current_list['type']})")
        with st.form("new_task_form", clear_on_submit=True):
            new_task_text = st.text_input("Add a new task...", label_visibility="collapsed")
            cols = st.columns([2, 1, 1])
            new_task_deadline = cols[0].date_input("Deadline", value=None)
            is_important = cols[1].checkbox("⭐ Important")
            is_urgent = cols[2].checkbox("🔥 Urgent")
            if st.form_submit_button("Add Task") and new_task_text:
                db_add_task(current_list['id'], new_task_text, new_task_deadline, is_important, is_urgent)
                st.rerun()
        st.markdown("---")
        sorted_task_list = sort_tasks(db_get_tasks_for_list(current_list['id']))
        for task in sorted_task_list:
            task_id = task['id']
            is_editing = st.session_state.get('editing_task_id') == task_id

            if is_editing:
                with st.form(key=f"edit_form_{task_id}"):
                    edit_cols = st.columns([5, 1])
                    new_text = edit_cols[0].text_input("Edit task", value=task['text'], label_visibility="collapsed")
                    if edit_cols[1].form_submit_button("Save"):
                        db_update_task_text(task_id, new_text)
                        st.session_state.editing_task_id = None
                        st.rerun()
            else:
                cols = st.columns([1, 6, 1, 1])
                completed = cols[0].checkbox("", value=task['completed'], key=f"complete_{task_id}", label_visibility="collapsed")
                if completed != task['completed']:
                    db_update_task_completion(task_id, completed)
                    st.rerun()
                with cols[1]:
                    task_class = "completed-task" if completed else ""
                    priority = "⭐" if task['important'] else ""
                    priority += "🔥" if task['urgent'] else ""
                    deadline = f" (Due: {task['deadline'].strftime('%b %d')})" if task['deadline'] else ""
                    st.markdown(f'<p class="{task_class}">{priority} {task["text"]}{deadline}</p>', unsafe_html=True)
                with cols[2]:
                    if st.button("✏️", key=f"edit_task_{task_id}", help="Edit task"):
                        st.session_state.editing_task_id = task_id
                        st.rerun()
                with cols[3]:
                    if st.button("❌", key=f"delete_task_{task_id}", help="Delete task"):
                        db_delete_task(task_id)
                        st.rerun()

# --- SCRIPT EXECUTION ---
st.set_page_config(
    page_title="Between",
    page_icon="✅",
    layout="centered",
    initial_sidebar_state="auto"
)
initialize_state()

# --- ROUTING LOGIC ---
if not st.session_state.logged_in:
    login_page()
else:
    if not st.session_state.db_initialized:
        if init_db(): st.session_state.db_initialized = True
    if st.session_state.db_initialized: main_app_ui()

