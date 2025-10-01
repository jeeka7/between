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

def parse_rows(result):
    """Parse the rows from Turso response into a list of dictionaries"""
    if not result or 'results' not in result or len(result['results']) == 0:
        return []
    
    first_result = result['results'][0]
    if ('response' not in first_result or 
        'result' not in first_result['response'] or 
        'rows' not in first_result['response']['result']):
        return []
    
    result_data = first_result['response']['result']
    cols = [col['name'] for col in result_data['cols']]
    rows = result_data['rows']
    
    parsed_rows = []
    for row in rows:
        row_dict = {}
        for i, col_name in enumerate(cols):
            if i < len(row):
                # Extract the value from the row cell structure
                cell = row[i]
                if isinstance(cell, dict) and 'value' in cell:
                    row_dict[col_name] = cell['value']
                else:
                    row_dict[col_name] = cell
        parsed_rows.append(row_dict)
    
    return parsed_rows

def get_todos():
    """Get all todos from database"""
    sql = "SELECT * FROM todos ORDER BY created_at DESC"
    result = execute_sql(sql)
    return parse_rows(result)

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

st.success("✅ Connected to Turso Database! Tables are ready.")

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

if st.button("Refresh Todos"):
    st.rerun()

todos = get_todos()

if not todos:
    st.info("No todos yet! Add your first todo above.")
else:
    for todo in todos:
        col1, col2, col3 = st.columns([1, 6, 1])
        
        with col1:
            # Convert completed to boolean (SQLite stores as 0/1)
            completed_bool = bool(todo.get('completed', 0))
            completed = st.checkbox(
                "",
                value=completed_bool,
                key=f"check_{todo['id']}",
                on_change=toggle_todo,
                args=(todo['id'], not completed_bool)
            )
        
        with col2:
            if todo.get('completed'):
                st.markdown(f"~~{todo['task']}~~")
            else:
                st.write(todo['task'])
            st.caption(f"ID: {todo['id']}")
        
        with col3:
            if st.button("🗑️", key=f"del_{todo['id']}"):
                if delete_todo(todo['id']):
                    st.success("Todo deleted!")
                    st.rerun()

# Debug section (collapsed by default)
with st.expander("🔧 Debug Info"):
    st.write("Current todos data:")
    st.json(todos)
    
    if st.button("Test Database Connection"):
        test_result = execute_sql("SELECT name FROM sqlite_master WHERE type='table';")
        st.write("Tables in database:")
        st.json(parse_rows(test_result))

st.markdown("---")
st.markdown("Built with ❤️ using Streamlit + Turso")
