import streamlit as st
from datetime import datetime, date
import uuid
import sqld_client
import os

# --- DATABASE SETUP ---
@st.cache_resource
def get_turso_client():
    """Establishes a cached, single connection to the Turso database using sqld-client."""
    url = st.secrets.get("TURSO_DATABASE_URL")
    auth_token = st.secrets.get("TURSO_AUTH_TOKEN")
    
    if not url or not auth_token:
        st.error("Turso database credentials are not configured. Please set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in your Streamlit secrets.")
        st.stop()
        
    # The sqld-client prefers the libsql:// protocol
    if url.startswith("https://"):
        url = "libsql" + url[5:]
        
    return sqld_client.Client.from_url(url, auth_token=auth_token)

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
        return True # Indicate success
    except Exception as e:
        st.error(f"Failed to initialize database: {e}")
        st.exception(e)
        st.stop()


# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Between",
    page_icon="✅",
    layout="centered",
    initial_sidebar_state="auto"
)

# --- CUSTOM CSS FOR MINIMALIST STYLING ---
st.markdown("""
<style>
    /* General body styling */
    body {
        font-family: 'Inter', sans-serif;
    }

    /* Hide Streamlit's default header and footer */
    #MainMenu, footer {
        visibility: hidden;
    }
    
    /* Style for completed tasks */
    .completed-task {
        text-decoration: line-through;
        color: #888;
    }

    /* Styling for task containers for a cleaner look */
    .task-container {
        border-bottom: 1px solid #eee;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    /* Align buttons and other elements */
    div.stButton > button {
        width: 100%;
        border-radius: 5px;
    }

    /* Reduce top margin of the main block */
    .main .block-container {
        padding-top: 2rem;
    }

</style>
""", unsafe_allow_html=True)


# --- STATE MANAGEMENT & INITIALIZATION ---
def initialize_state():
    """Initializes session state variables for login and selection."""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'selected_list_id' not in st.session_state:
        st.session_state.selected_list_id = None
    if 'db_initialized' not in st.session_state:
        st.session_state.db_initialized = False

initialize_state()

# --- HELPER TO CONVERT TUPLES TO DICTS ---
def result_set_to_dicts(rs):
    """Converts a sqld_client ResultSet to a list of dictionaries."""
    return [dict(zip(rs.columns, row)) for row in rs]

# --- DATABASE CRUD OPERATIONS (USING SQLD-CLIENT) ---

def db_create_list(name, list_type):
    client = get_turso_client()
    try:
        client.execute(
            "INSERT INTO lists (name, type, pinned, created_at) VALUES (?, ?, ?, ?)",
            [name, list_type, 0, datetime.now().isoformat()]
        )
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            st.error("A list with this name already exists.")
        else:
            st.error(f"Database error: {e}")

def db_get_all_lists():
    client = get_turso_client()
    rs = client.execute("SELECT * FROM lists")
    lists = result_set_to_dicts(rs)
    for lst in lists:
        lst['pinned'] = bool(lst['pinned'])
        lst['created_at'] = datetime.fromisoformat(lst['created_at'])
    return lists

def db_get_list(list_id):
    client = get_turso_client()
    rs = client.execute("SELECT * FROM lists WHERE id = ?", [list_id])
    if not rs: return None
    lst = result_set_to_dicts(rs)[0]
    lst['pinned'] = bool(lst['pinned'])
    lst['created_at'] = datetime.fromisoformat(lst['created_at'])
    return lst

def db_toggle_pin_list(list_id, current_pin_status):
    client = get_turso_client()
    client.execute("UPDATE lists SET pinned = ? WHERE id = ?", [not current_pin_status, list_id])

def db_delete_list(list_id):
    client = get_turso_client()
    client.execute("DELETE FROM lists WHERE id = ?", [list_id])

def db_add_task(list_id, text, deadline, important, urgent):
    deadline_str = deadline.isoformat() if deadline else None
    client = get_turso_client()
    client.execute(
        "INSERT INTO tasks (id, list_id, text, completed, important, urgent, created_at, deadline) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [str(uuid.uuid4()), list_id, text, 0, int(important), int(urgent), datetime.now().isoformat(), deadline_str]
    )
    
def db_get_tasks_for_list(list_id):
    client = get_turso_client()
    rs = client.execute("SELECT * FROM tasks WHERE list_id = ?", [list_id])
    tasks = result_set_to_dicts(rs)
    for task in tasks:
        task['completed'] = bool(task['completed'])
        task['important'] = bool(task['important'])
        task['urgent'] = bool(task['urgent'])
        task['created_at'] = datetime.fromisoformat(task['created_at'])
        task['deadline'] = date.fromisoformat(task['deadline']) if task['deadline'] else None
    return tasks

def db_update_task_completion(task_id, completed):
    client = get_turso_client()
    client.execute("UPDATE tasks SET completed = ? WHERE id = ?", [int(completed), task_id])

def db_delete_task(task_id):
    client = get_turso_client()
    client.execute("DELETE FROM tasks WHERE id = ?", [task_id])


# --- HELPER FUNCTIONS ---
def get_task_priority(task):
    """Calculates a sortable priority score for a task."""
    if task['important'] and task['urgent']:
        return 4
    if task['important']:
        return 3
    if task['urgent']:
        return 2
    return 1

def sort_lists(lists):
    """Sorts lists by pinned status, then by creation date."""
    return sorted(lists, key=lambda x: (not x['pinned'], x['created_at']))

def sort_tasks(tasks):
    """Sorts tasks by completion, then by priority."""
    return sorted(tasks, key=lambda x: (x['completed'], -get_task_priority(x), x['created_at']))

# --- AUTHENTICATION ---
def login_page():
    """Displays the login page and handles authentication."""
    st.title("✅ Between")
    st.markdown("Your minimalist to-do list manager.")

    ADMIN_PASSWORD = "admin" 

    with st.form("login_form"):
        password = st.text_input("Admin Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if password == ADMIN_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Incorrect password")

# --- MAIN APPLICATION UI ---
def main_app():
    """The main UI of the to-do list application."""
    # --- SIDEBAR FOR LIST MANAGEMENT ---
    with st.sidebar:
        st.title("Your Lists")

        with st.expander("➕ Create New List"):
            with st.form("new_list_form", clear_on_submit=True):
                new_list_name = st.text_input("List Name")
                new_list_type = st.selectbox("List Type", ["Simple", "Financial"])
                create_list_submitted = st.form_submit_button("Create List")

                if create_list_submitted and new_list_name:
                    db_create_list(new_list_name, new_list_type)
                    st.success(f"List '{new_list_name}' created!")
        
        st.markdown("---")

        all_lists = db_get_all_lists()
        sorted_list_items = sort_lists(all_lists)
        if not sorted_list_items:
            st.write("No lists yet. Create one!")
        else:
            for lst in sorted_list_items:
                list_id = lst['id']
                icon = "📌" if lst['pinned'] else "📝"
                
                col1, col2, col3 = st.columns([5, 1, 1])
                with col1:
                    if st.button(f"{icon} {lst['name']}", key=f"select_{list_id}"):
                        st.session_state.selected_list_id = list_id
                        st.rerun()
                with col2:
                    if st.button("📍", key=f"pin_{list_id}", help="Pin/Unpin list"):
                        db_toggle_pin_list(list_id, lst['pinned'])
                        st.rerun()
                with col3:
                    if st.button("🗑️", key=f"delete_{list_id}", help="Delete list"):
                        db_delete_list(list_id)
                        if st.session_state.selected_list_id == list_id:
                             st.session_state.selected_list_id = None
                        st.rerun()

    # --- MAIN PANEL FOR TASK MANAGEMENT ---
    if not st.session_state.selected_list_id:
        st.title("Select a list to get started")
        st.markdown("Create a new list from the sidebar or click on an existing one.")
    else:
        current_list_id = st.session_state.selected_list_id
        current_list = db_get_list(current_list_id)

        if not current_list:
             st.error("The selected list could not be found. It may have been deleted.")
             st.session_state.selected_list_id = None
             st.rerun()
             return
             
        st.header(f"{current_list['name']} ({current_list['type']})")
        created_date_str = current_list['created_at'].strftime("%b %d, %Y")
        st.caption(f"Created on: {created_date_str}")
        
        with st.form("new_task_form", clear_on_submit=True):
            cols = st.columns([4, 2])
            with cols[0]:
                new_task_text = st.text_input("Add a new task...", label_visibility="collapsed")
            with cols[1]:
                new_task_deadline = st.date_input("Deadline", value=None)

            priority_cols = st.columns(2)
            with priority_cols[0]:
                is_important = st.checkbox("⭐ Important")
            with priority_cols[1]:
                is_urgent = st.checkbox("🔥 Urgent")

            add_task_submitted = st.form_submit_button("Add Task")
            
            if add_task_submitted and new_task_text:
                db_add_task(current_list_id, new_task_text, new_task_deadline, is_important, is_urgent)
                st.rerun()

        st.markdown("---")

        tasks = db_get_tasks_for_list(current_list_id)
        if not tasks:
            st.info("This list is empty. Add a task to get started!")
        else:
            sorted_task_list = sort_tasks(tasks)
            for task in sorted_task_list:
                task_id = task['id']
                with st.container():
                    st.markdown('<div class="task-container">', unsafe_allow_html=True)
                    cols = st.columns([1, 6, 1])
                    
                    with cols[0]:
                        is_completed = st.checkbox("", value=task['completed'], key=f"complete_{task_id}", label_visibility="collapsed")
                        if is_completed != task['completed']:
                            db_update_task_completion(task_id, is_completed)
                            st.rerun()

                    with cols[1]:
                        task_class = "completed-task" if task['completed'] else ""
                        priority_icons = ""
                        if task['important']: priority_icons += "⭐"
                        if task['urgent']: priority_icons += "🔥"
                        deadline_str = f" (Due: {task['deadline'].strftime('%b %d')})" if task.get('deadline') else ""
                        st.markdown(f'<p class="{task_class}">{priority_icons} {task["text"]}{deadline_str}</p>', unsafe_html=True)

                    with cols[2]:
                        if st.button("❌", key=f"delete_task_{task_id}", help="Delete task"):
                            db_delete_task(task_id)
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

# --- ROUTING LOGIC ---
if not st.session_state.logged_in:
    login_page()
else:
    # Initialize DB only after login and only once per session
    if not st.session_state.db_initialized:
        if init_db():
            st.session_state.db_initialized = True
    
    if st.session_state.db_initialized:
        main_app()

