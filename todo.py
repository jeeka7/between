import streamlit as st
import requests
import os

# Your actual Turso credentials
TURSO_DB_URL = "https://betweentodo-deanhunter7.aws-ap-south-1.turso.io"
TURSO_AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJleHAiOjE3NjcwNjQxOTIsImlhdCI6MTc1OTI4ODE5MiwiaWQiOiJmNzQ3NDJiNi03ZGJhLTQ3MDYtYTk5Ny1iOWUzODg4YTIwN2QiLCJyaWQiOiI5YmZlMGE4Mi02Y2MyLTQzZDgtOTk3OS02NWFkOTE1MDhkNzIifQ.8_q5bQhBJAicC41n6qDa2f7u8DxV60FxnJxIembnMjDzL8rqeu-QvdiqXzpLJPBhWD8i0eyUit7BqmX7tMqJBw"

headers = {
    'Authorization': f'Bearer {TURSO_AUTH_TOKEN}',
    'Content-Type': 'application/json'
}

def format_value(value):
    """Format values for Turso API - they need explicit types"""
    if isinstance(value, str):
        return {"type": "text", "value": value}
    elif isinstance(value, bool):
        return {"type": "integer", "value": 1 if value else 0}
    elif isinstance(value, int):
        return {"type": "integer", "value": value}
    elif value is None:
        return {"type": "null"}
    else:
        return {"type": "text", "value": str(value)}

def execute_sql(sql, params=None):
    """Execute SQL query against Turso database"""
    try:
        formatted_args = [format_value(param) for param in params] if params else []
        
        request_data = {
            "requests": [{
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": formatted_args
                }
            }]
        }
        
        st.write(f"🔍 Executing SQL: {sql}")
        st.write(f"🔍 With params: {params}")
        
        response = requests.post(
            f"{TURSO_DB_URL}/v2/pipeline",
            headers=headers,
            json=request_data,
            timeout=10
        )
        
        st.write(f"🔍 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            st.write(f"🔍 Response data: {result}")
            return result
        else:
            st.error(f"❌ Database error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"❌ Connection error: {e}")
        return None

def parse_rows(result):
    """Parse the rows from Turso response into a list of dictionaries"""
    if not result or 'results' not in result or len(result['results']) == 0:
        st.write("🔍 No results to parse")
        return []
    
    first_result = result['results'][0]
    if ('response' not in first_result or 
        'result' not in first_result['response'] or 
        'rows' not in first_result['response']['result']):
        st.write("🔍 Unexpected response structure")
        return []
    
    result_data = first_result['response']['result']
    cols = [col['name'] for col in result_data['cols']]
    rows = result_data['rows']
    
    parsed_rows = []
    for row in rows:
        row_dict = {}
        for i, col_name in enumerate(cols):
            if i < len(row):
                cell = row[i]
                if isinstance(cell, dict) and 'value' in cell:
                    row_dict[col_name] = cell['value']
                else:
                    row_dict[col_name] = cell
        parsed_rows.append(row_dict)
    
    st.write(f"🔍 Parsed {len(parsed_rows)} rows")
    return parsed_rows

def initialize_database():
    """Create the necessary tables if they don't exist"""
    st.info("🔄 Initializing database...")
    
    # First, let's see what tables exist
    check_sql = "SELECT name FROM sqlite_master WHERE type='table';"
    existing_tables_result = execute_sql(check_sql)
    
    if existing_tables_result:
        existing_tables = parse_rows(existing_tables_result)
        table_names = [table['name'] for table in existing_tables]
        st.success(f"📊 Existing tables: {table_names}")
        
        # Check if we have the tables we need
        has_tools_list = 'tools_list' in table_names
        has_tasks = 'tasks' in table_names
        
        if has_tools_list and has_tasks:
            st.success("✅ Required tables already exist!")
            return True
        else:
            st.warning(f"⚠️ Missing tables. tools_list: {has_tools_list}, tasks: {has_tasks}")
    
    # Create the tables we need
    st.info("📝 Creating required tables...")
    
    create_tools_list_sql = """
    CREATE TABLE IF NOT EXISTS tools_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        list_type TEXT NOT NULL DEFAULT 'simple',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    create_tasks_sql = """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER,
        task TEXT NOT NULL,
        completed BOOLEAN DEFAULT FALSE,
        important BOOLEAN DEFAULT FALSE,
        urgent BOOLEAN DEFAULT FALSE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (list_id) REFERENCES tools_list (id)
    );
    """
    
    # Execute table creation
    result1 = execute_sql(create_tools_list_sql)
    result2 = execute_sql(create_tasks_sql)
    
    if result1 and result2:
        st.success("✅ Database tables created successfully!")
        return True
    else:
        st.error("❌ Failed to create database tables")
        return False

def get_todo_lists():
    """Get all todo lists"""
    sql = "SELECT * FROM tools_list ORDER BY created_at DESC"
    result = execute_sql(sql)
    return parse_rows(result)

def get_tasks(list_id):
    """Get all tasks for a specific list"""
    sql = "SELECT * FROM tasks WHERE list_id = ? ORDER BY created_at DESC"
    result = execute_sql(sql, [list_id])
    return parse_rows(result)

def create_todo_list(name, list_type):
    """Create a new todo list"""
    st.info(f"🔄 Creating list: {name} (type: {list_type})")
    sql = "INSERT INTO tools_list (name, list_type) VALUES (?, ?)"
    result = execute_sql(sql, [name, list_type])
    
    if result:
        st.success(f"✅ Successfully created list: {name}")
        return True
    else:
        st.error(f"❌ Failed to create list: {name}")
        return False

def update_todo_list(list_id, name, list_type):
    """Update a todo list"""
    sql = "UPDATE tools_list SET name = ?, list_type = ? WHERE id = ?"
    result = execute_sql(sql, [name, list_type, list_id])
    return result is not None

def delete_todo_list(list_id):
    """Delete a todo list and its tasks"""
    execute_sql("DELETE FROM tasks WHERE list_id = ?", [list_id])
    sql = "DELETE FROM tools_list WHERE id = ?"
    result = execute_sql(sql, [list_id])
    return result is not None

def add_task(list_id, task, important=False, urgent=False):
    """Add a new task to a list"""
    sql = "INSERT INTO tasks (list_id, task, important, urgent) VALUES (?, ?, ?, ?)"
    # Convert booleans to integers for SQLite
    important_int = 1 if important else 0
    urgent_int = 1 if urgent else 0
    result = execute_sql(sql, [list_id, task, important_int, urgent_int])
    return result is not None

def update_task(task_id, task, important, urgent):
    """Update a task"""
    sql = "UPDATE tasks SET task = ?, important = ?, urgent = ? WHERE id = ?"
    important_int = 1 if important else 0
    urgent_int = 1 if urgent else 0
    result = execute_sql(sql, [task, important_int, urgent_int, task_id])
    return result is not None

def toggle_task_completion(task_id, completed):
    """Toggle task completion status"""
    sql = "UPDATE tasks SET completed = ? WHERE id = ?"
    completed_int = 1 if completed else 0
    result = execute_sql(sql, [completed_int, task_id])
    return result is not None

def delete_task(task_id):
    """Delete a task"""
    sql = "DELETE FROM tasks WHERE id = ?"
    result = execute_sql(sql, [task_id])
    return result is not None

# Initialize database at startup
if 'db_initialized' not in st.session_state:
    st.session_state.db_initialized = initialize_database()

# Streamlit UI
st.set_page_config(page_title="Advanced Todo App", page_icon="✅", layout="wide")

st.title("✅ Advanced Todo App with Turso")
st.markdown("Manage multiple todo lists with different types and priority tasks")

# Debug controls
with st.expander("🔧 Debug Controls", expanded=True):
    st.write("**Database State**")
    if st.button("🔄 Check Database"):
        initialize_database()
    
    if st.button("📋 List All Tables"):
        result = execute_sql("SELECT name FROM sqlite_master WHERE type='table';")
        if result:
            tables = parse_rows(result)
            st.write(f"**Tables found:** {[table['name'] for table in tables]}")
    
    if st.button("👀 Show Current Lists"):
        lists = get_todo_lists()
        st.write(f"**Current lists:** {len(lists)}")
        for lst in lists:
            st.write(f"- {lst['name']} (ID: {lst['id']}, Type: {lst['list_type']})")

# Sidebar for Todo Lists Management
with st.sidebar:
    st.header("📋 Todo Lists Management")
    
    # Create new todo list
    with st.expander("➕ Create New Todo List", expanded=True):
        with st.form("create_list_form"):
            list_name = st.text_input("List Name", placeholder="Enter list name...")
            list_type = st.selectbox("List Type", ["simple", "financial"])
            submitted = st.form_submit_button("Create Todo List")
            if submitted and list_name:
                st.write(f"🔄 Form submitted: {list_name}, {list_type}")
                if create_todo_list(list_name, list_type):
                    st.rerun()
                else:
                    st.error("❌ Failed to create list")
            elif submitted:
                st.warning("⚠️ Please enter a list name")
    
    st.markdown("---")
    
    # Display existing todo lists
    st.write("**Current Lists**")
    todo_lists = get_todo_lists()
    
    if not todo_lists:
        st.info("📝 No todo lists yet. Create your first one above!")
    else:
        for todo_list in todo_lists:
            col1, col2 = st.columns([4, 1])
            
            with col1:
                list_type_icon = "💰" if todo_list['list_type'] == 'financial' else "📝"
                st.write(f"**{list_type_icon} {todo_list['name']}**")
            
            with col2:
                if st.button("🗑️", key=f"del_list_{todo_list['id']}"):
                    if delete_todo_list(todo_list['id']):
                        st.success("🗑️ List deleted!")
                        st.rerun()
            
            st.markdown("---")

# Main content area for tasks
st.header("📝 Tasks Management")

todo_lists = get_todo_lists()
if todo_lists:
    # Create tabs for each todo list
    tab_titles = [f"{'💰' if lst['list_type'] == 'financial' else '📝'} {lst['name']}" 
                  for lst in todo_lists]
    
    tabs = st.tabs(tab_titles)
    
    for i, (tab, todo_list) in enumerate(zip(tabs, todo_lists)):
        with tab:
            st.subheader(f"Tasks in {todo_list['name']}")
            
            # Add new task to this list
            with st.form(f"add_task_{todo_list['id']}"):
                new_task = st.text_input("New Task", key=f"task_{todo_list['id']}")
                col1, col2 = st.columns(2)
                with col1:
                    important = st.checkbox("⭐ Important", key=f"imp_{todo_list['id']}")
                with col2:
                    urgent = st.checkbox("🚨 Urgent", key=f"urg_{todo_list['id']}")
                
                if st.form_submit_button("Add Task") and new_task:
                    if add_task(todo_list['id'], new_task, important, urgent):
                        st.success("✅ Task added!")
                        st.rerun()
            
            st.markdown("---")
            
            # Display tasks for this list
            tasks = get_tasks(todo_list['id'])
            
            if not tasks:
                st.info(f"📝 No tasks in '{todo_list['name']}' yet.")
            else:
                for task in tasks:
                    col1, col2, col3, col4 = st.columns([1, 6, 2, 1])
                    
                    with col1:
                        completed_bool = bool(task.get('completed', 0))
                        completed = st.checkbox(
                            "",
                            value=completed_bool,
                            key=f"check_{task['id']}",
                            on_change=toggle_task_completion,
                            args=(task['id'], not completed_bool)
                        )
                    
                    with col2:
                        task_text = task['task']
                        if task.get('important'):
                            task_text = f"⭐ {task_text}"
                        if task.get('urgent'):
                            task_text = f"🚨 {task_text}"
                        
                        if task.get('completed'):
                            st.markdown(f"~~{task_text}~~")
                        else:
                            st.write(task_text)
                    
                    with col3:
                        with st.expander("✏️"):
                            with st.form(f"edit_task_{task['id']}"):
                                edit_task = st.text_input("Task", value=task['task'])
                                edit_important = st.checkbox("Important", value=bool(task.get('important', 0)))
                                edit_urgent = st.checkbox("Urgent", value=bool(task.get('urgent', 0)))
                                if st.form_submit_button("Update"):
                                    if update_task(task['id'], edit_task, edit_important, edit_urgent):
                                        st.success("✅ Task updated!")
                                        st.rerun()
                    
                    with col4:
                        if st.button("🗑️", key=f"del_task_{task['id']}"):
                            if delete_task(task['id']):
                                st.success("🗑️ Task deleted!")
                                st.rerun()
else:
    st.info("👈 Create your first todo list using the sidebar!")

st.markdown("---")
st.markdown("Built with ❤️ using Streamlit + Turso")
