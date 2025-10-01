import streamlit as st
import requests
import json

# Your actual Turso credentials
TURSO_DB_URL = "https://betweentodo-deanhunter7.aws-ap-south-1.turso.io"
TURSO_AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJleHAiOjE3NjcwNjQxOTIsImlhdCI6MTc1OTI4ODE5MiwiaWQiOiJmNzQ3NDJiNi03ZGJhLTQ3MDYtYTk5Ny1iOWUzODg4YTIwN2QiLCJyaWQiOiI5YmZlMGE4Mi02Y2MyLTQzZDgtOTk3OS02NWFkOTE1MDhkNzIifQ.8_q5bQhBJAicC41n6qDa2f7u8DxV60FxnJxIembnMjDzL8rqeu-QvdiqXzpLJPBhWD8i0eyUit7BqmX7tMqJBw"

headers = {
    'Authorization': f'Bearer {TURSO_AUTH_TOKEN}',
    'Content-Type': 'application/json'
}

def test_connection():
    """Test the connection and see the actual response structure"""
    st.info("Testing connection...")
    
    # Test with a simple SQL
    test_sql = "SELECT name FROM sqlite_master WHERE type='table';"
    
    request_data = {
        "requests": [{
            "type": "execute",
            "stmt": {
                "sql": test_sql
            }
        }]
    }
    
    try:
        response = requests.post(
            f"{TURSO_DB_URL}/v2/pipeline",
            headers=headers,
            json=request_data,
            timeout=10
        )
        
        st.write(f"Status Code: {response.status_code}")
        st.write("Full Response:")
        st.json(response.json())
        
    except Exception as e:
        st.error(f"Error: {e}")

# Simple UI for testing
st.title("🔧 Turso Connection Tester")
st.markdown("Let's first see what the actual API response looks like")

if st.button("Test Connection"):
    test_connection()

st.markdown("---")
st.markdown("Once we see the response structure, we can fix the todo app.")
