import streamlit as st
import libsql_client
import uuid
from datetime import datetime, date
import hashlib
import os

# Page configuration
st.set_page_config(
    page_title="Between - Todo Lists",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Turso client
@st.cache_resource
def init_turso_client():
    db_url = st.secrets["TURSO_DB_URL"]
    auth_token = st.secrets["TURSO_AUTH_TOKEN"]
    return libsql_client.create_client_sync(url=db_url, auth_token=auth_token)

# Initialize database tables
def init_db():
    client = init_turso_client()
    
    # Create tables if they don't exist
    client.execute("""
        CREATE TABLE IF NOT EXISTS lists (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('simple', 'financial')),
            is_pinned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_password TEXT NOT NULL
        )
    """)
    
    client.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            list_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            is_important BOOLEAN DEFAULT FALSE,
            is_urgent BOOLEAN DEFAULT FALSE,
            created_date DATE DEFAULT CURRENT_DATE,
            deadline_date DATE,
            is_completed BOOLEAN DEFAULT FALSE,
            completed_at TIMESTAMP,
            FOREIGN KEY (list_id) REFERENCES lists (id) ON DELETE CASCADE
        )
    """)
    
    client.close()

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Admin authentication
def authenticate_admin():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔐 Between - Admin Login")
        password = st.text_input("Enter Admin Password:", type="password")
        
        if st.button("Login"):
            hashed_input = hash_password(password)
            # Check against the first list's admin password or a default
            client = init_turso_client()
            result = client.execute("SELECT admin_password FROM lists LIMIT 1")
            client.close()
            
            if result.rows:
                stored_hash = result.rows[0][0]
                if hashed_input == stored_hash:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
            else:
                # First time setup - use default password
                default_hash = hash_password("admin123")
                if hashed_input == default_hash:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
        st.stop()

# Main app functions
def create_list(name, list_type, admin_password):
    client = init_turso_client()
    try:
        list_id = str(uuid.uuid4())
        hashed_password = hash_password(admin_password)
        client.execute(
            "INSERT INTO lists (id, name, type, admin_password) VALUES (?, ?, ?, ?)",
            [list_id, name, list_type, hashed_password]
        )
        st.success(f"List '{name}' created successfully!")
    except Exception as e:
        st.error(f"Error creating list: {str(e)}")
    finally:
        client.close()

def delete_list(list_id):
    client = init_turso_client()
    try:
        client.execute("DELETE FROM lists WHERE id = ?", [list_id])
        st.success("List deleted successfully!")
    except Exception as e:
        st.error(f"Error deleting list: {str(e)}")
    finally:
        client.close()

def toggle_pin_list(list_id, current_state):
    client = init_turso_client()
    try:
        client.execute("UPDATE lists SET is_pinned = ? WHERE id = ?", [not current_state, list_id])
        st.rerun()
    except Exception as e:
        st.error(f"Error updating list: {str(e)}")
    finally:
        client.close()

def create_task(list_id, title, description, is_important, is_urgent, deadline_date):
    client = init_turso_client()
    try:
        task_id = str(uuid.uuid4())
        client.execute(
            """INSERT INTO tasks (id, list_id, title, description, is_important, is_urgent, deadline_date) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [task_id, list_id, title, description, is_important, is_urgent, deadline_date]
        )
        st.success("Task added successfully!")
    except Exception as e:
        st.error(f"Error creating task: {str(e)}")
    finally:
        client.close()

def update_task(task_id, title, description, is_important, is_urgent, deadline_date):
    client = init_turso_client()
    try:
        client.execute(
            """UPDATE tasks SET title = ?, description = ?, is_important = ?, is_urgent = ?, deadline_date = ? 
               WHERE id = ?""",
            [title, description, is_important, is_urgent, deadline_date, task_id]
        )
        st.success("Task updated successfully!")
    except Exception as e:
        st.error(f"Error updating task: {str(e)}")
    finally:
        client.close()

def delete_task(task_id):
    client = init_turso_client()
    try:
        client.execute("DELETE FROM tasks WHERE id = ?", [task_id])
        st.success("Task deleted successfully!")
    except Exception as e:
        st.error(f"Error deleting task: {str(e)}")
    finally:
        client.close()

def toggle_task_completion(task_id, current_state):
    client = init_turso_client()
    try:
        completed_at = datetime.now() if not current_state else None
        client.execute(
            "UPDATE tasks SET is_completed = ?, completed_at = ? WHERE id = ?",
            [not current_state, completed_at, task_id]
        )
        st.rerun()
    except Exception as e:
        st.error(f"Error updating task: {str(e)}")
    finally:
        client.close()

# UI Components
def render_task_card(task, list_type):
    with st.container():
        col1, col2, col3, col4 = st.columns([1, 4, 2, 1])
        
        with col1:
            st.checkbox(
                "Done", 
                value=task['is_completed'], 
                key=f"done_{task['id']}",
                on_change=toggle_task_completion,
                args=(task['id'], task['is_completed'])
            )
        
        with col2:
            if task['is_completed']:
                st.markdown(f"~~{task['title']}~~")
                if task['description']:
                    st.markdown(f"~~{task['description']}~~")
            else:
                st.write(f"**{task['title']}**")
                if task['description']:
                    st.caption(task['description'])
        
        with col3:
            if task['deadline_date']:
                deadline = datetime.strptime(task['deadline_date'], '%Y-%m-%d').date()
                days_left = (deadline - date.today()).days
                if days_left < 0:
                    st.error(f"Overdue: {deadline.strftime('%b %d')}")
                elif days_left == 0:
                    st.warning("Today!")
                elif days_left <= 3:
                    st.warning(f"{days_left}d left")
                else:
                    st.info(f"{deadline.strftime('%b %d')}")
            
            # Priority indicators
            if task['is_important'] and task['is_urgent']:
                st.error("🔥 Important & Urgent")
            elif task['is_important']:
                st.warning("⭐ Important")
            elif task['is_urgent']:
                st.error("⚡ Urgent")
        
        with col4:
            st.button("✏️", key=f"edit_{task['id']}", on_click=show_edit_task, args=(task,))
            st.button("🗑️", key=f"delete_{task['id']}", on_click=delete_task, args=(task['id'],))

def show_edit_task(task):
    st.session_state.editing_task = task

def render_list_management():
    st.sidebar.header("📋 List Management")
    
    # Create new list
    with st.sidebar.expander("Create New List"):
        with st.form("create_list_form"):
            list_name = st.text_input("List Name")
            list_type = st.selectbox("List Type", ["simple", "financial"])
            admin_password = st.text_input("Admin Password", type="password")
            
            if st.form_submit_button("Create List"):
                if list_name and admin_password:
                    create_list(list_name, list_type, admin_password)
                    st.rerun()
                else:
                    st.error("Please fill all fields")

def main_app():
    # Initialize database
    init_db()
    
    # Authenticate user
    authenticate_admin()
    
    # Main UI
    st.title("📝 Between - Minimal Todo App")
    
    # Sidebar for list management
    render_list_management()
    
    # Get all lists
    client = init_turso_client()
    lists_result = client.execute("""
        SELECT id, name, type, is_pinned, created_at 
        FROM lists 
        ORDER BY is_pinned DESC, created_at DESC
    """)
    
    if not lists_result.rows:
        st.info("No lists found. Create your first list using the sidebar!")
        return
    
    lists = [dict(zip(['id', 'name', 'type', 'is_pinned', 'created_at'], row)) for row in lists_result.rows]
    
    # Display lists in tabs
    tab_names = [f"{'📌 ' if list_data['is_pinned'] else ''}{list_data['name']}" for list_data in lists]
    tabs = st.tabs(tab_names)
    
    for i, (tab, list_data) in enumerate(zip(tabs, lists)):
        with tab:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.subheader(f"{list_data['name']} ({list_data['type'].title()} List)")
            
            with col2:
                # Pin/unpin button
                pin_label = "📌 Unpin" if list_data['is_pinned'] else "📌 Pin"
                st.button(
                    pin_label, 
                    key=f"pin_{list_data['id']}",
                    on_click=toggle_pin_list,
                    args=(list_data['id'], list_data['is_pinned'])
                )
                
                # Delete list button
                st.button(
                    "🗑️ Delete List", 
                    key=f"delete_list_{list_data['id']}",
                    on_click=delete_list,
                    args=(list_data['id'],)
                )
            
            # Add new task
            with st.expander("➕ Add New Task"):
                with st.form(f"add_task_{list_data['id']}"):
                    title = st.text_input("Title*", key=f"title_{list_data['id']}")
                    description = st.text_area("Description", key=f"desc_{list_data['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        is_important = st.checkbox("Important", key=f"imp_{list_data['id']}")
                    with col2:
                        is_urgent = st.checkbox("Urgent", key=f"urg_{list_data['id']}")
                    with col3:
                        deadline_date = st.date_input("Deadline", key=f"deadline_{list_data['id']}")
                    
                    if st.form_submit_button("Add Task"):
                        if title:
                            create_task(list_data['id'], title, description, is_important, is_urgent, deadline_date)
                            st.rerun()
                        else:
                            st.error("Title is required")
            
            # Edit task form (if any task is being edited)
            if 'editing_task' in st.session_state:
                task = st.session_state.editing_task
                if task['list_id'] == list_data['id']:
                    with st.form(f"edit_task_{task['id']}"):
                        st.subheader("Edit Task")
                        edit_title = st.text_input("Title", value=task['title'])
                        edit_description = st.text_area("Description", value=task['description'] or "")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            edit_important = st.checkbox("Important", value=task['is_important'])
                        with col2:
                            edit_urgent = st.checkbox("Urgent", value=task['is_urgent'])
                        with col3:
                            current_deadline = datetime.strptime(task['deadline_date'], '%Y-%m-%d').date() if task['deadline_date'] else None
                            edit_deadline = st.date_input("Deadline", value=current_deadline)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Update Task"):
                                update_task(task['id'], edit_title, edit_description, edit_important, edit_urgent, edit_deadline)
                                del st.session_state.editing_task
                                st.rerun()
                        with col2:
                            if st.form_submit_button("Cancel"):
                                del st.session_state.editing_task
                                st.rerun()
            
            # Display tasks
            tasks_result = client.execute("""
                SELECT * FROM tasks 
                WHERE list_id = ? 
                ORDER BY 
                    is_completed ASC,
                    CASE 
                        WHEN is_important = 1 AND is_urgent = 1 THEN 1
                        WHEN is_important = 1 THEN 2
                        WHEN is_urgent = 1 THEN 3
                        ELSE 4
                    END,
                    created_date ASC
            """, [list_data['id']])
            
            tasks = [dict(zip(['id', 'list_id', 'title', 'description', 'is_important', 'is_urgent', 
                             'created_date', 'deadline_date', 'is_completed', 'completed_at'], row)) 
                    for row in tasks_result.rows]
            
            if not tasks:
                st.info("No tasks in this list. Add your first task above!")
            else:
                # Separate completed and pending tasks
                pending_tasks = [task for task in tasks if not task['is_completed']]
                completed_tasks = [task for task in tasks if task['is_completed']]
                
                if pending_tasks:
                    st.subheader("Pending Tasks")
                    for task in pending_tasks:
                        render_task_card(task, list_data['type'])
                
                if completed_tasks:
                    with st.expander(f"Completed Tasks ({len(completed_tasks)})"):
                        for task in completed_tasks:
                            render_task_card(task, list_data['type'])
    
    client.close()

if __name__ == "__main__":
    main_app()
