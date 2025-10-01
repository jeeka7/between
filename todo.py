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

def execute_sql(sql, params=None):
    """Execute SQL query against Turso database"""
    try:
        request_data = {
            "requests": [{
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": params if params else []
                }
            }]
        }
        
        response = requests.post(
            f"{TURSO_DB_URL}/v2/pipeline",
            headers=headers,
            json=request_data,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Database error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def init_database():
    """Create todos table if it doesn't exist"""
    sql = """
    CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        task TEXT, 
        completed BOOLEAN DEFAULT FALSE, 
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    result = execute_sql(sql)
    if result:
        st.success("✅ Database initialized successfully!")
        # Debug the response
        with st.expander("Debug Init Response"):
            st.json(result)

def get_todos():
    """Get all todos from database"""
    sql = "SELECT * FROM todos ORDER BY created_at DESC"
    result = execute_sql(sql)
    
    # Debug the response structure
    with st.expander("Debug Get Todos Response"):
        st.json(result)
    
    if result and 'results' in result:
        # Try different response structures
        if (len(result['results']) > 0 and 
            'response' in result['results'][0] and
            'result' in result['results'][0]['response'] and
            'rows' in result['results'][0]['response']['result']):
            return result['results'][0]['response']['result']['rows']
        elif (len(result['results']) > 0 and 
              'result' in result['results'][0] and
              'rows' in result['results'][0]['result']):
            return result['results'][0]['result']['rows']
        else:
            st.warning("Unexpected response structure")
            st.json(result)
    return []

def add_todo(task):
    """Add a new todo to database"""
    sql = "INSERT INTO todos (task) VALUES (?)"
    result = execute_sql(sql, [task])
    return result is not None

def toggle_todo(todo_id, completed):
    """Toggle todo completion status"""
    sql = "UPDATE todos SET completed = ? WHERE id = ?"
    result = execute_sql(sql, [completed, todo_id])
    return result is not None

def delete_todo(todo_id):
    """Delete a todo from database"""
    sql = "DELETE FROM todos WHERE id = ?"
    result = execute_sql(sql, [todo_id])
    return result is not None

# Streamlit UI
st.title("📝 Simple Todo App with Turso")
st.markdown("A minimal todo app using **Streamlit** and **Turso Database**")

st.success("🔗 Connected to Turso Database!")

# Initialize database first
if st.button("Initialize Database"):
    init_database()

# Add new todo
with st.form("add_todo_form"):
    new_task = st.text_input("Enter a new task:")
    submitted = st.form_submit_button("Add Todo")
    if submitted and new_task:
        if add_todo(new_task):
            st.success(f"Added: {new_task}")
            st.rerun()
        else:
            st.error("Failed to add todo")

# Display todos
st.subheader("Your Todos")

# Add a button to manually fetch todos
if st.button("Refresh Todos"):
    st.rerun()

todos = get_todos()

if not todos:
    st.info("No todos yet! Add one above or check the debug info for response structure.")
else:
    for todo in todos:
        col1, col2, col3 = st.columns([1, 6, 1])
        
        with col1:
            completed = st.checkbox(
                "",
                value=bool(todo.get('completed', False)),
                key=f"check_{todo['id']}",
                on_change=toggle_todo,
                args=(todo['id'], not bool(todo.get('completed', False)))
            )
        
        with col2:
            if todo.get('completed'):
                st.markdown(f"~~{todo['task']}~~")
            else:
                st.write(todo['task'])
        
        with col3:
            if st.button("🗑️", key=f"del_{todo['id']}"):
                if delete_todo(todo['id']):
                    st.success("Todo deleted!")
                    st.rerun()

st.markdown("---")
st.markdown("Built with ❤️ using Streamlit + Turso")
