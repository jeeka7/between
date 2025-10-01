import streamlit as st
import sqlite3
import uuid
from datetime import datetime, date
import hashlib
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="Between - Todo Lists",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('between_todo.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS lists (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('simple', 'financial')),
            is_pinned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_password TEXT NOT NULL
        )
    ''')
    
    c.execute('''
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
    ''')
    
    conn.commit()
    conn.close()

# Database connection
def get_db_connection():
    return sqlite3.connect('between_todo.db', check_same_thread=False)

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Admin authentication
def authenticate_admin():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔐 Between - Admin Login")
        password = st.text_input("Enter Admin Password:", type="password", value="admin123")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Login", use_container_width=True):
                hashed_input = hash_password(password)
                
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT admin_password FROM lists LIMIT 1")
                result = c.fetchone()
                conn.close()
                
                if result:
                    stored_hash = result[0]
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
        
        with col2:
            if st.button("Use Default Password", use_container_width=True):
                st.info("Default password: admin123")
        st.stop()

# List operations
def create_list(name, list_type, admin_password):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        list_id = str(uuid.uuid4())
        hashed_password = hash_password(admin_password)
        c.execute(
            "INSERT INTO lists (id, name, type, admin_password) VALUES (?, ?, ?, ?)",
            (list_id, name, list_type, hashed_password)
        )
        conn.commit()
        st.success(f"List '{name}' created successfully!")
        st.rerun()
    except sqlite3.IntegrityError:
        st.error("A list with this name already exists!")
    except Exception as e:
        st.error(f"Error creating list: {str(e)}")
    finally:
        conn.close()

def delete_list(list_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Delete tasks first (CASCADE should handle this, but being explicit)
        c.execute("DELETE FROM tasks WHERE list_id = ?", (list_id,))
        # Then delete the list
        c.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        conn.commit()
        st.success("List deleted successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Error deleting list: {str(e)}")
    finally:
        conn.close()

def toggle_pin_list(list_id, current_state):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE lists SET is_pinned = ? WHERE id = ?", (not current_state, list_id))
        conn.commit()
        st.rerun()
    except Exception as e:
        st.error(f"Error updating list: {str(e)}")
    finally:
        conn.close()

# Task operations
def create_task(list_id, title, description, is_important, is_urgent, deadline_date):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        task_id = str(uuid.uuid4())
        deadline_str = deadline_date.isoformat() if deadline_date else None
        c.execute(
            """INSERT INTO tasks (id, list_id, title, description, is_important, is_urgent, deadline_date) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, list_id, title, description, is_important, is_urgent, deadline_str)
        )
        conn.commit()
        st.success("Task added successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Error creating task: {str(e)}")
    finally:
        conn.close()

def update_task(task_id, title, description, is_important, is_urgent, deadline_date):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        deadline_str = deadline_date.isoformat() if deadline_date else None
        c.execute(
            """UPDATE tasks SET title = ?, description = ?, is_important = ?, is_urgent = ?, deadline_date = ? 
               WHERE id = ?""",
            (title, description, is_important, is_urgent, deadline_str, task_id)
        )
        conn.commit()
        st.success("Task updated successfully!")
        if 'editing_task' in st.session_state:
            del st.session_state.editing_task
        st.rerun()
    except Exception as e:
        st.error(f"Error updating task: {str(e)}")
    finally:
        conn.close()

def delete_task(task_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        st.success("Task deleted successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Error deleting task: {str(e)}")
    finally:
        conn.close()

def toggle_task_completion(task_id, current_state):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        completed_at = datetime.now().isoformat() if not current_state else None
        c.execute(
            "UPDATE tasks SET is_completed = ?, completed_at = ? WHERE id = ?",
            (not current_state, completed_at, task_id)
        )
        conn.commit()
        st.rerun()
    except Exception as e:
        st.error(f"Error updating task: {str(e)}")
    finally:
        conn.close()

# UI Components
def render_task_card(task, list_type):
    task_id, list_id, title, description, is_important, is_urgent, created_date, deadline_date, is_completed, completed_at = task
    
    with st.container():
        st.markdown("---")
        col1, col2, col3, col4 = st.columns([1, 4, 2, 1])
        
        with col1:
            st.checkbox(
                "Done", 
                value=is_completed,
                key=f"done_{task_id}",
                on_change=toggle_task_completion,
                args=(task_id, is_completed)
            )
        
        with col2:
            if is_completed:
                st.markdown(f"~~**{title}**~~")
                if description:
                    st.markdown(f"~~{description}~~")
            else:
                st.write(f"**{title}**")
                if description:
                    st.caption(description)
        
        with col3:
            if deadline_date:
                deadline = datetime.strptime(deadline_date, '%Y-%m-%d').date()
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
            if is_important and is_urgent:
                st.error("🔥 Important & Urgent")
            elif is_important:
                st.warning("⭐ Important")
            elif is_urgent:
                st.error("⚡ Urgent")
        
        with col4:
            col4a, col4b = st.columns(2)
            with col4a:
                st.button("✏️", key=f"edit_{task_id}", on_click=show_edit_task, args=(task,))
            with col4b:
                st.button("🗑️", key=f"delete_{task_id}", on_click=delete_task, args=(task_id,))

def show_edit_task(task):
    st.session_state.editing_task = task

def render_list_management():
    st.sidebar.header("📋 List Management")
    
    # Create new list
    with st.sidebar.expander("➕ Create New List", expanded=True):
        with st.form("create_list_form"):
            list_name = st.text_input("List Name", placeholder="Enter list name")
            list_type = st.selectbox("List Type", ["simple", "financial"])
            admin_password = st.text_input("Admin Password", type="password", value="admin123")
            
            if st.form_submit_button("Create List", use_container_width=True):
                if list_name and admin_password:
                    create_list(list_name, list_type, admin_password)
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
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, name, type, is_pinned, created_at 
        FROM lists 
        ORDER BY is_pinned DESC, created_at DESC
    """)
    lists_data = c.fetchall()
    conn.close()
    
    if not lists_data:
        st.info("🎯 No lists found. Create your first list using the sidebar!")
        return
    
    # Display lists in tabs
    tab_names = []
    for list_row in lists_data:
        list_id, name, list_type, is_pinned, created_at = list_row
        pin_icon = "📌 " if is_pinned else ""
        tab_names.append(f"{pin_icon}{name}")
    
    tabs = st.tabs(tab_names)
    
    for i, (tab, list_row) in enumerate(zip(tabs, lists_data)):
        list_id, name, list_type, is_pinned, created_at = list_row
        
        with tab:
            # Header with list info
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.subheader(f"{name}")
                st.caption(f"{list_type.title()} List • Created: {created_at[:10]}")
            
            with col2:
                # Pin/unpin button
                pin_label = "📌 Unpin" if is_pinned else "📌 Pin"
                st.button(
                    pin_label, 
                    key=f"pin_{list_id}",
                    on_click=toggle_pin_list,
                    args=(list_id, is_pinned),
                    use_container_width=True
                )
            
            with col3:
                # Delete list button
                st.button(
                    "🗑️ Delete", 
                    key=f"delete_list_{list_id}",
                    on_click=delete_list,
                    args=(list_id,),
                    use_container_width=True
                )
            
            # Add new task section
            with st.expander("➕ Add New Task", expanded=True):
                with st.form(f"add_task_{list_id}"):
                    title = st.text_input("Title*", placeholder="What needs to be done?")
                    description = st.text_area("Description", placeholder="Additional details...")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        is_important = st.checkbox("⭐ Important")
                    with col2:
                        is_urgent = st.checkbox("⚡ Urgent")
                    with col3:
                        deadline_date = st.date_input("📅 Deadline")
                    
                    if st.form_submit_button("Add Task", use_container_width=True):
                        if title:
                            create_task(list_id, title, description, is_important, is_urgent, deadline_date)
                        else:
                            st.error("Title is required")
            
            # Edit task form (if any task is being edited)
            if 'editing_task' in st.session_state:
                task = st.session_state.editing_task
                if task[1] == list_id:  # Check if task belongs to current list
                    st.markdown("---")
                    with st.form(f"edit_task_{task[0]}"):
                        st.subheader("✏️ Edit Task")
                        edit_title = st.text_input("Title", value=task[2])
                        edit_description = st.text_area("Description", value=task[3] or "")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            edit_important = st.checkbox("Important", value=task[4])
                        with col2:
                            edit_urgent = st.checkbox("Urgent", value=task[5])
                        with col3:
                            current_deadline = datetime.strptime(task[7], '%Y-%m-%d').date() if task[7] else None
                            edit_deadline = st.date_input("Deadline", value=current_deadline)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("✅ Update Task", use_container_width=True):
                                update_task(task[0], edit_title, edit_description, edit_important, edit_urgent, edit_deadline)
                        with col2:
                            if st.form_submit_button("❌ Cancel", use_container_width=True):
                                del st.session_state.editing_task
                                st.rerun()
            
            # Display tasks
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
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
            """, (list_id,))
            tasks_data = c.fetchall()
            conn.close()
            
            if not tasks_data:
                st.info("📝 No tasks yet. Add your first task above!")
            else:
                # Separate completed and pending tasks
                pending_tasks = [task for task in tasks_data if not task[8]]  # is_completed
                completed_tasks = [task for task in tasks_data if task[8]]    # is_completed
                
                if pending_tasks:
                    st.subheader(f"📋 Pending Tasks ({len(pending_tasks)})")
                    for task in pending_tasks:
                        render_task_card(task, list_type)
                
                if completed_tasks:
                    with st.expander(f"✅ Completed Tasks ({len(completed_tasks)})"):
                        for task in completed_tasks:
                            render_task_card(task, list_type)

if __name__ == "__main__":
    main_app()
