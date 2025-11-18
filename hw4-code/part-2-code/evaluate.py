from argparse import ArgumentParser
from utils import compute_metrics

def main():
    parser = ArgumentParser(description="Evaluate predicted SQL queries against ground-truth.")
    
    parser.add_argument(
        "-ps", "--predicted_sql", dest="pred_sql",
        required=True, help="Path to your model's predicted SQL queries"
    )
    parser.add_argument(
        "-pr", "--predicted_records", dest="pred_records",
        required=True, help="Path to the predicted development database records"
    )
    parser.add_argument(
        "-ds", "--development_sql", dest="dev_sql",
        required=True, help="Path to the ground-truth development SQL queries"
    )
    parser.add_argument(
        "-dr", "--development_records", dest="dev_records",
        required=True, help="Path to the ground-truth development database records"
    )

    args = parser.parse_args()

    # Compute all metrics using the utility function
    sql_em, record_em, record_f1, _ = compute_metrics(
        args.dev_sql, args.pred_sql, args.dev_records, args.pred_records
    )

    # Print results
    print("Evaluation Results:")
    print("-------------------")
    print(f"SQL Query Exact Match (SQL EM): {sql_em:.4f}")
    print(f"Record Exact Match (Record EM): {record_em:.4f}")
    print(f"Record F1: {record_f1:.4f}")

if __name__ == "__main__":
    main()
