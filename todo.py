import streamlit as st
import requests
import os

# Turso configuration - with URL validation
TURSO_DB_URL = os.getenv('TURSO_DB_URL', 'https://betweentodo-deanhunter7.aws-ap-south-1.turso.io')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN', 'eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJleHAiOjE3NjcwNjQxOTIsImlhdCI6MTc1OTI4ODE5MiwiaWQiOiJmNzQ3NDJiNi03ZGJhLTQ3MDYtYTk5Ny1iOWUzODg4YTIwN2QiLCJyaWQiOiI5YmZlMGE4Mi02Y2MyLTQzZDgtOTk3OS02NWFkOTE1MDhkNzIifQ.8_q5bQhBJAicC41n6qDa2f7u8DxV60FxnJxIembnMjDzL8rqeu-QvdiqXzpLJPBhWD8i0eyUit7BqmX7tMqJBw')

# Ensure the URL has https:// scheme
if not TURSO_DB_URL.startswith(('https://', 'http://')):
    TURSO_DB_URL = f"https://{TURSO_DB_URL}"

headers = {
    'Authorization': f'Bearer {TURSO_AUTH_TOKEN}',
    'Content-Type': 'application/json'
}

def init_database():
    """Create todos table if it doesn't exist"""
    create_table_sql = {
        "statements": [
            "CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, completed BOOLEAN DEFAULT FALSE, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);"
        ]
    }
    
    try:
        response = requests.post(
            f"{TURSO_DB_URL}/v2/pipeline",
            headers=headers,
            json=create_table_sql
        )
        if response.status_code == 200:
            st.success("Database initialized!")
        else:
            st.error(f"Error initializing database: {response.text}")
    except Exception as e:
        st.error(f"Connection error: {e}")

def get_todos():
    """Get all todos from database"""
    try:
        sql = {"statements": [{"q": "SELECT * FROM todos ORDER BY created_at DESC"}]}
        response = requests.post(f"{TURSO_DB_URL}/v2/pipeline", headers=headers, json=sql)
        
        if response.status_code == 200:
            data = response.json()
            if data and data[0]['results']:
                return data[0]['results'][0]['response']['result']['rows']
        return []
    except Exception as e:
        st.error(f"Error fetching todos: {e}")
        return []

def add_todo(task):
    """Add a new todo to database"""
    try:
        sql = {"statements": [{"q": "INSERT INTO todos (task) VALUES (?)", "params": [task]}]}
        response = requests.post(f"{TURSO_DB_URL}/v2/pipeline", headers=headers, json=sql)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error adding todo: {e}")
        return False

def toggle_todo(todo_id, completed):
    """Toggle todo completion status"""
    try:
        sql = {"statements": [{"q": "UPDATE todos SET completed = ? WHERE id = ?", "params": [completed, todo_id]}]}
        response = requests.post(f"{TURSO_DB_URL}/v2/pipeline", headers=headers, json=sql)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error updating todo: {e}")
        return False

def delete_todo(todo_id):
    """Delete a todo from database"""
    try:
        sql = {"statements": [{"q": "DELETE FROM todos WHERE id = ?", "params": [todo_id]}]}
        response = requests.post(f"{TURSO_DB_URL}/v2/pipeline", headers=headers, json=sql)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error deleting todo: {e}")
        return False

# Streamlit UI
st.title("📝 Simple Todo App with Turso")
st.markdown("A minimal todo app using **Streamlit** and **Turso Database**")

# Show current configuration (for debugging)
with st.expander("🔧 Debug Info (Remove in production)"):
    st.write(f"Database URL: {TURSO_DB_URL}")
    st.write(f"Token exists: {'Yes' if TURSO_AUTH_TOKEN != 'your-turso-auth-token' else 'No'}")

# Initialize database
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
todos = get_todos()

if not todos:
    st.info("No todos yet! Add one above.")
else:
    for todo in todos:
        col1, col2, col3 = st.columns([1, 6, 1])
        
        with col1:
            completed = st.checkbox(
                "",
                value=todo['completed'],
                key=f"check_{todo['id']}",
                on_change=toggle_todo,
                args=(todo['id'], not todo['completed'])
            )
        
        with col2:
            if todo['completed']:
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
