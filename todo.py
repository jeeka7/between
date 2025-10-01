import streamlit as st
import libsql_client
import os
from datetime import datetime, date

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Between",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="auto",
)

# --- DATABASE CONNECTION & SETUP ---

# Establish connection to Turso DB using Streamlit secrets
@st.cache_resource
def connect_to_db():
    """Connects to the Turso database and returns a client object."""
    url = st.secrets["TURSO_DB_URL"]
    auth_token = st.secrets["TURSO_DB_AUTH_TOKEN"]
    
    # The 'secure' flag should be True for production connections to Turso
    client = libsql_client.create_client(url=url, auth_token=auth_token)
    return client

def setup_database(client):
    """Creates the necessary tables if they don't already exist."""
    # Using 'ON DELETE CASCADE' means if a list is deleted, all its tasks are also deleted.
    client.batch([
        """
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            list_type TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            is_important INTEGER DEFAULT 0,
            is_urgent INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0,
            deadline TEXT,
            FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE
        )
        """
    ])

# --- CRUD OPERATIONS ---

# LISTS
def get_all_lists(client):
    rs = client.execute("SELECT * FROM lists ORDER BY is_pinned DESC, created_at DESC")
    return list(rs)

def add_list(client, name, list_type):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client.execute(
        "INSERT INTO lists (name, list_type, created_at) VALUES (?, ?, ?)",
        (name, list_type, created_at)
    )

def delete_list(client, list_id):
    client.execute("DELETE FROM lists WHERE id = ?", (list_id,))

def toggle_pin_list(client, list_id, current_pin_status):
    new_status = 1 - current_pin_status # Flips 0 to 1 and 1 to 0
    client.execute("UPDATE lists SET is_pinned = ? WHERE id = ?", (new_status, list_id))

# TASKS
def get_tasks_for_list(client, list_id):
    # Sort by completion status first, then by urgency/importance
    rs = client.execute(
        """
        SELECT * FROM tasks 
        WHERE list_id = ? 
        ORDER BY is_completed ASC, (is_urgent + is_important) DESC, id DESC
        """,
        (list_id,)
    )
    return list(rs)

def add_task(client, list_id, description, is_important, is_urgent, deadline):
    deadline_str = deadline.strftime("%Y-%m-%d") if deadline else None
    client.execute(
        """
        INSERT INTO tasks (list_id, description, is_important, is_urgent, deadline)
        VALUES (?, ?, ?, ?, ?)
        """,
        (list_id, description, int(is_important), int(is_urgent), deadline_str)
    )

def delete_task(client, task_id):
    client.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

def update_task_completion(client, task_id, is_completed):
    client.execute("UPDATE tasks SET is_completed = ? WHERE id = ?", (int(is_completed), task_id))


# --- AUTHENTICATION & UI ---

def login_page():
    """Displays the login page."""
    st.title("🔐 Admin Login")
    st.write("Welcome to **Between**. Please enter the password to continue.")
    
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        # Compare with the password stored in Streamlit secrets
        if password == st.secrets["ADMIN_PASSWORD"]:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")

def main_app():
    """The main application interface after successful login."""
    client = connect_to_db()
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("Between")
        st.write("Your minimalistic to-do manager.")
        st.markdown("---")
        
        with st.form("new_list_form", clear_on_submit=True):
            st.header("✨ Create a New List")
            new_list_name = st.text_input("List Name", placeholder="e.g., Groceries, Project X")
            new_list_type = st.selectbox("List Type", ["Simple", "Financial"])
            submitted = st.form_submit_button("Create List")
            
            if submitted and new_list_name:
                try:
                    add_list(client, new_list_name, new_list_type)
                    st.success(f"List '{new_list_name}' created!")
                    st.rerun()
                except Exception as e:
                    # This handles the UNIQUE constraint violation
                    st.error(f"A list with the name '{new_list_name}' already exists.")
        
        st.markdown("---")
        if st.button("Logout"):
            st.session_state["logged_in"] = False
            st.rerun()

    # --- MAIN CONTENT ---
    st.header("Your Lists")
    
    all_lists = get_all_lists(client)
    if not all_lists:
        st.info("You don't have any lists yet. Create one from the sidebar to get started! 🚀")
        return

    for lst in all_lists:
        list_id = lst["id"]
        list_name = lst["name"]
        is_pinned = lst["is_pinned"]
        
        # Determine icon based on type and pinned status
        pin_icon = "📌" if is_pinned else ""
        type_icon = "💰" if lst["list_type"] == "Financial" else "📝"
        
        with st.expander(f"{pin_icon} **{list_name}** {type_icon}", expanded=True):
            
            # --- ADD NEW TASK FORM ---
            with st.form(f"add_task_form_{list_id}", clear_on_submit=True):
                cols = st.columns((4, 1, 1))
                with cols[0]:
                    new_task_desc = st.text_input("New task", label_visibility="collapsed", placeholder="Add a task...")
                with cols[1]:
                    deadline = st.date_input("Deadline", label_visibility="collapsed")
                with cols[2]:
                    add_task_button = st.form_submit_button("Add")

                sub_cols = st.columns((1, 1, 4))
                with sub_cols[0]:
                    is_important = st.checkbox("Important ⭐", key=f"important_{list_id}")
                with sub_cols[1]:
                    is_urgent = st.checkbox("Urgent 🔥", key=f"urgent_{list_id}")
                
                if add_task_button and new_task_desc:
                    add_task(client, list_id, new_task_desc, is_important, is_urgent, deadline)
                    st.rerun()

            st.markdown("---")

            # --- DISPLAY TASKS ---
            tasks = get_tasks_for_list(client, list_id)
            if not tasks:
                st.write("_This list is empty._")

            for task in tasks:
                task_id = task["id"]
                is_completed = bool(task["is_completed"])
                
                # Create a row of columns for each task
                task_cols = st.columns([0.1, 0.5, 0.15, 0.15, 0.1])
                
                # Completion Checkbox
                with task_cols[0]:
                    completed = st.checkbox(
                        "", 
                        value=is_completed, 
                        key=f"complete_{task_id}",
                        on_change=update_task_completion, 
                        args=(client, task_id, not is_completed)
                    )
                
                # Task Description with priority icons
                with task_cols[1]:
                    desc = task["description"]
                    if task["is_important"]: desc += " ⭐"
                    if task["is_urgent"]: desc += " 🔥"
                    
                    if completed:
                        st.markdown(f"~~{desc}~~")
                    else:
                        st.write(desc)
                
                # Deadline
                with task_cols[2]:
                    if task["deadline"]:
                        dl = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
                        if not completed and dl < date.today():
                            st.error(f"{dl.strftime('%b %d')}") # Overdue
                        else:
                            st.info(f"{dl.strftime('%b %d')}")

                # Pin List Button
                with task_cols[3]:
                    pin_text = "Unpin" if is_pinned else "Pin"
                    if st.button(pin_text, key=f"pin_{list_id}"):
                         toggle_pin_list(client, list_id, is_pinned)
                         st.rerun()

                # Delete Task Button
                with task_cols[4]:
                    if st.button("🗑️", key=f"del_task_{task_id}"):
                        delete_task(client, task_id)
                        st.rerun()
            
            # --- LIST ACTIONS ---
            st.markdown("---")
            if st.button("Delete this entire list", key=f"del_list_{list_id}", type="primary"):
                delete_list(client, list_id)
                st.rerun()
                

# --- MAIN EXECUTION ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_page()
else:
    # Connect and setup DB after login
    client = connect_to_db()
    setup_database(client)
    main_app()
