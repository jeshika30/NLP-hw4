import json
import random

# Path to your predictions file
pred_file = "dev_predictions.json"

# Load predictions
with open(pred_file, "r") as f:
    data = json.load(f)

# Collect error examples
errors = []
for item in data:
    gold = item.get("gold_sql", "")
    pred = item.get("prediction", "")
    if pred != gold:
        errors.append({
            "query": item.get("query", ""),
            "prediction": pred,
            "gold_sql": gold
        })

print(f"Found {len(errors)} errors.")

# Randomly select 10 snippets
sample_errors = random.sample(errors, min(10, len(errors)))

# Print the errors
for e in sample_errors:
    print(f"Query: {e['query']}")
    print(f"Prediction: {e['prediction']}")
    print(f"Gold SQL: {e['gold_sql']}")
    print("-" * 50)
