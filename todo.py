import streamlit as st
from libsql_client import create_client_sync
import datetime
import pandas as pd

# ---------------------------------------------------------------------
# DB Configuration & Initialization
# ---------------------------------------------------------------------

def get_db_client():
    """
    Initializes and returns a Turso database client.
    """
    url = st.secrets["TURSO_DATABASE_URL"]
    auth_token = st.secrets["TURSO_AUTH_TOKEN"]

    # --- FIX ---
    # We still need to force the https:// protocol
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    
    # Use create_client_sync() for synchronous environments like Streamlit
    # This avoids the asyncio loop error.
    client = create_client_sync(
        url=url,
        auth_token=auth_token
    )
    # --- END FIX ---
    
    return client

def init_database(client):
    """
    Creates the necessary tables if they don't already exist.
    """
    # SQL for creating the 'lists' table
    create_lists_table = """
    CREATE TABLE IF NOT EXISTS lists (
        list_id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_name TEXT NOT NULL,
        list_type TEXT NOT NULL CHECK(list_type IN ('Simple', 'Financial')),
        last_modified TIMESTAMP
    );
    """
    
    # SQL for creating the 'tasks' table
    create_tasks_table = """
    CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER NOT NULL,
        task_name TEXT NOT NULL,
        urgent TEXT NOT NULL CHECK(urgent IN ('Yes', 'No')) DEFAULT 'No',
        important TEXT NOT NULL CHECK(important IN ('Yes', 'No')) DEFAULT 'No',
        completed INTEGER DEFAULT 0, -- 0 for False, 1 for True
        FOREIGN KEY (list_id) REFERENCES lists(list_id) ON DELETE CASCADE
    );
    """
    
    try:
        # --- FIX ---
        # The 'sync' client's batch method takes a list of statements,
        # not a 'with' block.
        client.batch([
            create_lists_table,
            create_tasks_table
        ])
        # --- END FIX ---
        
    except Exception as e:
        # This will now show any *real* errors if they happen
        st.error(f"Error initializing database: {e}")

def update_list_timestamp(client, list_id):
    """
    Updates the 'last_modified' timestamp for a list.
    """
    now = datetime.datetime.now()
    client.execute(
        "UPDATE lists SET last_modified = ? WHERE list_id = ?",
        (now, list_id)
    )

# ---------------------------------------------------------------------
# CRUD Functions for LISTS
# ---------------------------------------------------------------------

def add_list(client, name, list_type):
    if name:
        now = datetime.datetime.now()
        client.execute(
            "INSERT INTO lists (list_name, list_type, last_modified) VALUES (?, ?, ?)",
            (name, list_type, now)
        )
        st.success(f"Created list: {name}")

def get_all_lists(client, list_type="All"):
    """
    Gets all lists, with an optional filter for 'Simple' or 'Financial'.
    """
    query = "SELECT * FROM lists"
    params = []
    
    if list_type != "All":
        query += " WHERE list_type = ?"
        params.append(list_type)
        
    query += " ORDER BY last_modified DESC"
    
    # --- FIX ---
    # Call execute() differently based on whether params has content.
    # Passing an empty list [] was causing the crash.
    try:
        if params:
            rs = client.execute(query, params)
        else:
            rs = client.execute(query) # Call without the args parameter
        
        return rs.rows
    except Exception as e:
        st.error(f"Error fetching lists: {e}")
        return [] # Return an empty list on error to prevent other crashes
    # --- END FIX ---
def update_list_name(client, list_id, new_name):
    if new_name:
        client.execute("UPDATE lists SET list_name = ? WHERE list_id = ?", (new_name, list_id))
        update_list_timestamp(client, list_id)
        st.success("List renamed!")

def delete_list(client, list_id):
    client.execute("DELETE FROM lists WHERE list_id = ?", (list_id,))
    st.warning("List deleted!")

# ---------------------------------------------------------------------
# CRUD Functions for TASKS
# ---------------------------------------------------------------------

def add_task(client, list_id, task_name, urgent, important):
    if task_name:
        client.execute(
            "INSERT INTO tasks (list_id, task_name, urgent, important) VALUES (?, ?, ?, ?)",
            (list_id, task_name, urgent, important)
        )
        update_list_timestamp(client, list_id)

def get_tasks_for_list(client, list_id, sort_key="task_id", filter_urgent=False, filter_important=False):
    query = "SELECT * FROM tasks WHERE list_id = ?"
    params = [list_id]
    
    if filter_urgent:
        query += " AND urgent = 'Yes'"
    if filter_important:
        query += " AND important = 'Yes'"
        
    if sort_key == "urgent":
        query += " ORDER BY urgent DESC, important DESC"
    elif sort_key == "important":
        query += " ORDER BY important DESC, urgent DESC"
    else:
        query += " ORDER BY completed ASC, task_id DESC"
        
    rs = client.execute(query, params)
    return rs.rows


def update_task_details(client, task_id, task_name, urgent, important, list_id):
    """
    Updates the name, urgent, and important status of a task.
    """
    if not task_name:
        st.error("Task name cannot be empty.")
        return

    try:
        client.execute(
            "UPDATE tasks SET task_name = ?, urgent = ?, important = ? WHERE task_id = ?",
            (task_name, urgent, important, task_id)
        )
        update_list_timestamp(client, list_id)
        st.success("Task updated!")
    except Exception as e:
        st.error(f"Failed to update task: {e}")

def update_task_status(client, task_id, completed, list_id):
    client.execute("UPDATE tasks SET completed = ? WHERE task_id = ?", (1 if completed else 0, task_id))
    update_list_timestamp(client, list_id)

def delete_task(client, task_id, list_id):
    client.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
    update_list_timestamp(client, list_id)

# ---------------------------------------------------------------------
# Main Streamlit App UI
# ---------------------------------------------------------------------

def main():
    st.set_page_config(layout="wide")
    st.title("✅ Turso To-Do List Manager")

    client = get_db_client()
    init_database(client) # Ensures tables exist

    # --- SIDEBAR (List Management) ---
    st.sidebar.title("My Lists")
    
    with st.sidebar.expander("➕ Create New List", expanded=False):
        list_type = st.selectbox("List Type", ["Simple", "Financial"], key="list_type")
        new_list_name = st.text_input("New List Name", key="new_list_name")
        if st.button("Create List"):
            add_list(client, new_list_name, list_type)
            st.rerun()

    # --- NEW: List Type Filter ---
    st.sidebar.markdown("---")
    list_filter = st.sidebar.radio(
        "Filter lists by type",
        ["All", "Simple", "Financial"],
        key="list_filter"
    )

    all_lists = get_all_lists(client, list_filter)
    
    if not all_lists:
        st.info(f"No '{list_filter}' lists found. Create one or change your filter.")
        st.stop()

    list_options = {l["list_id"]: f"{l['list_name']} ({l['list_type']})" for l in all_lists}
    selected_list_id = st.sidebar.radio(
        "Select a List",
        options=list_options.keys(),
        format_func=lambda x: list_options[x],
        key="selected_list"
    )

    # Get details of the selected list
    selected_list_details = next((l for l in all_lists if l["list_id"] == selected_list_id), None)
    
    # --- MOVED: Task Filters ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("Task Filters")
    filter_urgent = st.sidebar.checkbox("Show Urgent Only")
    filter_important = st.sidebar.checkbox("Show Important Only")

    if selected_list_details:
        st.sidebar.markdown("---")
        st.sidebar.subheader("List Operations")
        
        # Update List Name
        with st.sidebar.form(key="update_list_form"):
            new_name = st.text_input("Rename List", value=selected_list_details["list_name"])
            if st.form_submit_button("Rename"):
                update_list_name(client, selected_list_id, new_name)
                st.rerun()

        # Delete List
        if st.sidebar.button("⚠️ Delete This List"):
            delete_list(client, selected_list_id)
            st.rerun()
        
        st.sidebar.markdown("---")
        last_mod = selected_list_details['last_modified']
        st.sidebar.caption(f"Last modified:\n{last_mod}")

    # --- MAIN AREA (Task Management) ---
    if selected_list_id:
        st.header(f"Tasks for: {selected_list_details['list_name']}")
        
        # 1. Add New Task
        st.subheader("Add a New Task")
        with st.form("new_task_form", clear_on_submit=True):
            task_name = st.text_input("Task Description")
            col1, col2 = st.columns(2)
            with col1:
                urgent = st.selectbox("Urgent?", ["No", "Yes"])
            with col2:
                important = st.selectbox("Important?", ["No", "Yes"])
            
            if st.form_submit_button("Add Task"):
                add_task(client, selected_list_id, task_name, urgent, important)
                st.rerun()
        
        st.markdown("---")

        # 2. Filter and Sort Tasks
        st.subheader("Your Tasks")
        
        # --- CHANGED: Sort is still here, but filters are read from sidebar ---
        sort_by = st.selectbox("Sort By", ["Default", "Urgent", "Important"])

        # Re-fetch tasks with filters from the sidebar
        tasks = get_tasks_for_list(client, selected_list_id, sort_by, filter_urgent, filter_important)

        if not tasks:
            st.info("This list is empty or no tasks match your filter. Add a task above!")
            st.stop()

        # 3. Display Tasks (CRUD)
        for task in tasks:
            cols = st.columns([1, 5, 1, 1, 1, 1]) 
            
            with cols[0]:
                completed = st.checkbox(
                    "Done", 
                    value=bool(task["completed"]), 
                    key=f"check_{task['task_id']}",
                    on_change=update_task_status,
                    args=(client, task['task_id'], not bool(task["completed"]), selected_list_id)
                )
            
            task_display = f"~~{task['task_name']}~~" if completed else task['task_name']
            with cols[1]:
                st.markdown(task_display)
            
            with cols[2]:
                if task["urgent"] == 'Yes':
                    st.markdown("🔥 **Urgent**")
            
            with cols[3]:
                if task["important"] == 'Yes':
                    st.markdown("❗️ **Important**")
            
            with cols[4]:
                with st.popover("Edit"):
                    with st.form(key=f"edit_form_{task['task_id']}"):
                        
                        new_name = st.text_input("Task Name", value=task['task_name'])
                        
                        urgent_index = 0 if task['urgent'] == 'No' else 1
                        new_urgent = st.selectbox(
                            "Urgent?", ["No", "Yes"], 
                            index=urgent_index, 
                            key=f"urg_{task['task_id']}"
                        )
                        
                        important_index = 0 if task['important'] == 'No' else 1
                        new_important = st.selectbox(
                            "Important?", ["No", "Yes"], 
                            index=important_index, 
                            key=f"imp_{task['task_id']}"
                        )
                        
                        if st.form_submit_button("Save"):
                            update_task_details(
                                client, 
                                task['task_id'], 
                                new_name, 
                                new_urgent, 
                                new_important, 
                                selected_list_id
                            )
                            st.rerun()

            with cols[5]:
                if st.button("Delete", key=f"del_{task['task_id']}", type="primary"):
                    delete_task(client, task['task_id'], selected_list_id)
                    st.rerun()
            
            st.divider()

        # 4. "Print List" functionality
        st.markdown("---")
        st.subheader("Print List")
        if st.button("Show Printable View"):
            st.header(f"Printable View: {selected_list_details['list_name']}")
            
            df = pd.DataFrame(tasks)
            df_print = df[['task_name', 'urgent', 'important', 'completed']]
            df_print['completed'] = df_print['completed'].apply(lambda x: 'Yes' if x == 1 else 'No')
            
            st.dataframe(df_print, use_container_width=True)
            st.caption("You can print this page using your browser's Print function (Ctrl+P or Cmd+P).")
