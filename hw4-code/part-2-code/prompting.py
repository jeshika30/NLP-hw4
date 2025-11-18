import os, argparse, random
from tqdm import tqdm

import torch
from transformers import GemmaTokenizerFast, GemmaForCausalLM
from transformers import GemmaTokenizer, AutoModelForCausalLM
from transformers import BitsAndBytesConfig

from utils import set_random_seeds, compute_metrics, save_queries_and_records, compute_records
from prompting_utils import read_schema, extract_sql_query, save_logs
from load_data import load_prompting_data

DEVICE = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
MAX_NEW_TOKENS = 256  # max tokens to generate

def get_args():
    parser = argparse.ArgumentParser(description='Text-to-SQL experiments with prompting.')
    parser.add_argument('-s', '--shot', type=int, default=0, help='Number of examples for k-shot')
    parser.add_argument('-p', '--ptype', type=int, default=0, help='Prompt type')
    parser.add_argument('-m', '--model', type=str, default='gemma', help='Model: gemma or codegemma')
    parser.add_argument('-q', '--quantization', action='store_true', help='Use quantized model')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--experiment_name', type=str, default='experiment', help="Experiment name")
    return parser.parse_args()

def create_prompt(sentence, k, train_x=None, train_y=None):
    """Create a 0-shot or k-shot prompt for text-to-SQL."""
    prompt = ""
    # k-shot examples if available
    if k > 0 and train_x and train_y:
        for i in range(k):
            prompt += f"Text: {train_x[i]}\nSQL: {train_y[i]}\n\n"
    # Target sentence
    prompt += f"Text: {sentence}\nSQL:"
    return prompt

def exp_kshot(tokenizer, model, inputs, k, train_x=None, train_y=None):
    raw_outputs = []
    extracted_queries = []
    for sentence in tqdm(inputs):
        prompt = create_prompt(sentence, k, train_x, train_y)
        input_ids = tokenizer(prompt, return_tensors="pt").to(DEVICE)
        outputs = model.generate(**input_ids, max_new_tokens=MAX_NEW_TOKENS)
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        raw_outputs.append(response)
        extracted_queries.append(extract_sql_query(response))
    return raw_outputs, extracted_queries

def eval_outputs(gt_sql_path, model_sql_path, gt_record_path, model_record_path):
    sql_em, record_em, record_f1, model_error_msgs, error_rate = compute_metrics(
        gt_sql_path, model_sql_path, gt_record_path, model_record_path
    )
    return sql_em, record_em, record_f1, model_error_msgs, error_rate

def initialize_model_and_tokenizer(model_name, to_quantize=False):
    if model_name == "gemma":
        model_id = "google/gemma-1.1-2b-it"
        tokenizer = GemmaTokenizerFast.from_pretrained(model_id)
        model = GemmaForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16).to(DEVICE)
    elif model_name == "codegemma":
        model_id = "google/codegemma-7b-it"
        tokenizer = GemmaTokenizer.from_pretrained(model_id)
        if to_quantize:
            nf4_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4")
            model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, config=nf4_config).to(DEVICE)
        else:
            model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16).to(DEVICE)
    return tokenizer, model

def main():
    args = get_args()
    set_random_seeds(args.seed)

    train_x, train_y, dev_x, dev_y, test_x = load_prompting_data("data")
    tokenizer, model = initialize_model_and_tokenizer(args.model, args.quantization)

    for eval_split in ["dev", "test"]:
        eval_x, eval_y = (dev_x, dev_y) if eval_split == "dev" else (test_x, None)
        raw_outputs, extracted_queries = exp_kshot(tokenizer, model, eval_x, args.shot, train_x, train_y)

        gt_sql_path = f"data/{eval_split}.sql"
        gt_record_path = f"records/{eval_split}_gt_records.pkl"
        model_sql_path = f"results/{args.model}_{args.experiment_name}_{eval_split}.sql"
        model_record_path = f"records/{args.model}_{args.experiment_name}_{eval_split}.pkl"

        sql_em, record_em, record_f1, model_error_msgs, error_rate = eval_outputs(
            gt_sql_path, model_sql_path, gt_record_path, model_record_path
        )

        print(f"{eval_split} results - SQL EM: {sql_em}, Record EM: {record_em}, Record F1: {record_f1}, Error Rate: {error_rate*100:.2f}%")

        log_path = f"results/{args.model}_{args.experiment_name}_{eval_split}_log.txt"
        save_logs(log_path, sql_em, record_em, record_f1, model_error_msgs)

if __name__ == "__main__":
    main()
