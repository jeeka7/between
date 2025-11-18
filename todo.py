import streamlit as st
import streamlit_authenticator as stauth
from libsql_client import create_client_sync
import datetime
import pandas as pd
from weasyprint import HTML
# ---------------------------------------------------------------------
# DB Configuration & Initialization
# ---------------------------------------------------------------------

def get_db_client():
    """
    Initializes and returns a Turso database client.
    This is cached to prevent re-creating the connection on every rerun.
    """
    url = st.secrets["TURSO_DATABASE_URL"]
    auth_token = st.secrets["TURSO_AUTH_TOKEN"]

    # --- We still need to force the https:// protocol
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    
    # Use create_client_sync() for synchronous environments like Streamlit
    client = create_client_sync(
        url=url,
        auth_token=auth_token
    )
    
    return client

def create_pdf_from_df(df, list_name):
    """
    Generates a PDF from a Pandas DataFrame and returns it as bytes.
    """
    
    # Convert DataFrame to HTML
    df_html = df.to_html(index=False)
    
    # Basic CSS for styling the table in the PDF
    css_style = """
    <style>
        body { font-family: sans-serif; }
        h1 { text-align: center; }
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin-top: 20px;
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left; 
        }
        th { 
            background-color: #f2f2f2; 
        }
    </style>
    """
    
    # Combine title, style, and table into one HTML string
    full_html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        {css_style}
    </head>
    <body>
        <h1>{list_name}</h1>
        {df_html}
    </body>
    </html>
    """
    
    # Generate PDF bytes
    pdf_bytes = HTML(string=full_html).write_pdf()
    return pdf_bytes

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
    st.title("Secrets Debugger")
    
    st.info("This is the final test. We are checking the secrets.")

    try:
        st.subheader("Attempting to read [credentials]:")
        
        # We will try to read the nested username 'jack'
        creds = st.secrets["credentials"]["usernames"]["jack"]
        st.success("SUCCESS: Found secrets for [credentials.usernames.jack]")
        st.json(creds)

    except Exception as e:
        st.error("FAILED to read [credentials.usernames.jack]")
        st.exception(e)
        st.warning("""
            This means your TOML format in Streamlit Cloud Secrets is wrong.
            It MUST look exactly like this (with your username):
            
            [credentials.usernames.jack]
            email = "jack@example.com"
            name = "Jack"
            password = "$2b$12$....YOUR_HASHED_PASSWORD"
        """)

    try:
        st.subheader("Attempting to read [cookie]:")
        cookie = st.secrets["cookie"]
        st.success("SUCCESS: Found secrets for [cookie]")
        st.json(cookie)

    except Exception as e:
        st.error("FAILED to read [cookie]")
        st.exception(e)
        st.warning("""
            This means your TOML format in Streamlit Cloud Secrets is wrong.
            It MUST look exactly like this:
            
            [cookie]
            name = "todo_cookie_name"
            key = "a_random_secret_key_12345"
            expiry_days = 30
        """)
