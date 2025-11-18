import os

def read_schema(schema_path):
    with open(schema_path, "r") as f:
        schema = f.read()
    return schema

def extract_sql_query(response):
    """Extract SQL query from model response."""
    if "SQL:" in response:
        return response.split("SQL:")[1].strip()
    return response.strip()

def save_logs(output_path, sql_em, record_em, record_f1, error_msgs):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(f"SQL EM: {sql_em}\nRecord EM: {record_em}\nRecord F1: {record_f1}\nModel Error Messages: {error_msgs}\n")
