from load_data import load_lines

def tokenize(text):
    # Simple whitespace tokenizer, you can use nltk.word_tokenize if you want
    return text.strip().split()

def compute_stats(nl_lines, sql_lines):
    num_examples = len(nl_lines)
    
    nl_lengths = [len(tokenize(line)) for line in nl_lines]
    sql_lengths = [len(tokenize(line)) for line in sql_lines]
    
    nl_vocab = set()
    sql_vocab = set()
    
    for line in nl_lines:
        nl_vocab.update(tokenize(line))
    for line in sql_lines:
        sql_vocab.update(tokenize(line))
        
    mean_nl_len = sum(nl_lengths) / num_examples
    mean_sql_len = sum(sql_lengths) / num_examples
    
    stats = {
        "Number of examples": num_examples,
        "Mean sentence length": mean_nl_len,
        "Mean SQL query length": mean_sql_len,
        "Vocabulary size (natural language)": len(nl_vocab),
        "Vocabulary size (SQL)": len(sql_vocab),
    }
    return stats

from sklearn.metrics import f1_score
import numpy as np

# Compute exact match (EM) for SQL queries
def compute_sql_exact_match(gt_sqls, pred_sqls):
    exact_matches = 0
    total = len(gt_sqls)

    for gt, pred in zip(gt_sqls, pred_sqls):
        if gt.strip() == pred.strip():
            exact_matches += 1

    return exact_matches / total


# Compute F1 score between ground truth and predicted records
def compute_record_f1(gt_records, model_records):
    f1_scores = []
    for gt, model in zip(gt_records, model_records):
        gt_set = set(gt)
        model_set = set(model)

        # Precision
        precision = len(gt_set.intersection(model_set)) / (len(model_set) + 1e-8)
        
        # Recall
        recall = len(gt_set.intersection(model_set)) / (len(gt_set) + 1e-8)
        
        # F1 Score
        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)

        f1_scores.append(f1)

    return np.mean(f1_scores)


# Main function to compute EM and F1 score
def compute_metrics(gt_sql_path, pred_sql_path, gt_records_path, pred_records_path):
    # Load ground truth and predicted SQL queries
    with open(gt_sql_path, 'r') as f:
        gt_sqls = [line.strip() for line in f.readlines()]
    
    with open(pred_sql_path, 'r') as f:
        pred_sqls = [line.strip() for line in f.readlines()]

    # Compute Query EM
    query_em = compute_sql_exact_match(gt_sqls, pred_sqls)

    # Load ground truth and predicted records
    with open(gt_records_path, 'rb') as f:
        gt_records, _ = pickle.load(f)
    
    with open(pred_records_path, 'rb') as f:
        model_records, _ = pickle.load(f)

    # Compute F1 score for records
    record_f1 = compute_record_f1(gt_records, model_records)

    return query_em, record_f1


if __name__ == "__main__":
    train_nl = load_lines("data/train.nl")
    train_sql = load_lines("data/train.sql")
    
    dev_nl = load_lines("data/dev.nl")
    dev_sql = load_lines("data/dev.sql")
    
    train_stats = compute_stats(train_nl, train_sql)
    dev_stats = compute_stats(dev_nl, dev_sql)
    
    print("Train Statistics:")
    for k, v in train_stats.items():
        print(f"{k}: {v}")
    print("\nDev Statistics:")
    for k, v in dev_stats.items():
        print(f"{k}: {v}")
