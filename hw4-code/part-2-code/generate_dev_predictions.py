import sqlite3
import pickle
from transformers import T5TokenizerFast, T5ForConditionalGeneration
import torch
from tqdm import tqdm

# Define the database connection
DB_PATH = 'data/flight_database.db'  # Adjust the path to your database

# Path to the trained model and tokenizer
MODEL_PATH = './checkpoints/ft_experiment'  # Adjust to your model's checkpoint directory
TOKENIZER_PATH = 't5-small'

# Function to execute SQL queries and return the results
def execute_sql_query(sql_query):
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(sql_query)
        records = cursor.fetchall()  # Fetch all the results
        return records
    except Exception as e:
        print(f"Error executing SQL query: {e}")
        return []
    finally:
        conn.close()

# Read the SQL queries from the file (assuming each query is on a new line)
def read_sql_file(sql_file_path):
    with open(sql_file_path, 'r') as f:
        queries = f.readlines()
    return queries

# Function to save the results to a pickle file
def save_results_to_pkl(results, output_pkl_path):
    with open(output_pkl_path, 'wb') as f:
        pickle.dump(results, f)

# Initialize model and tokenizer
def load_model_and_tokenizer():
    tokenizer = T5TokenizerFast.from_pretrained(TOKENIZER_PATH)
    model = T5ForConditionalGeneration.from_pretrained(MODEL_PATH).to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    return tokenizer, model

# Generate SQL queries using the fine-tuned T5 model
def generate_sql_queries(model, tokenizer, dev_data):
    model.eval()
    generated_sqls = []

    with torch.no_grad():
        for text in tqdm(dev_data, desc="Generating SQL queries", ncols=100):
            # Tokenize the input text
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            outputs = model.generate(input_ids=inputs["input_ids"], max_length=256)

            sql_query = tokenizer.decode(outputs[0], skip_special_tokens=True)
            generated_sqls.append(sql_query)

    return generated_sqls

# Main function
def main():
    # Adjust the path to your dev set or input data
    dev_data = ["Query 1", "Query 2", "Query 3"]  # Replace with your actual dev set queries

    # Load model and tokenizer
    tokenizer, model = load_model_and_tokenizer()

    # Generate SQL queries from the dev set
    generated_sqls = generate_sql_queries(model, tokenizer, dev_data)

    # Save the generated SQL queries to a .sql file
    with open('results/t5_ft_dev.sql', 'w') as f:
        for sql in generated_sqls:
            f.write(f"{sql}\n")

    # Execute the SQL queries and get the results
    all_results = []
    for sql_query in generated_sqls:
        results = execute_sql_query(sql_query)
        all_results.append(results)

    # Save the results into a .pkl file
    save_results_to_pkl(all_results, 'records/t5_ft_dev.pkl')

    print("SQL queries and results have been saved to 't5_ft_dev.sql' and 't5_ft_dev.pkl'")

if __name__ == "__main__":
    main()
