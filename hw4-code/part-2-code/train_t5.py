import os
import argparse
from tqdm import tqdm
import torch
import torch.nn as nn
import wandb

from transformers import T5ForConditionalGeneration, T5TokenizerFast, AdamW, get_linear_schedule_with_warmup
from utils import compute_metrics, save_queries_and_records
from load_data import load_t5_data

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

TOKENIZER = T5TokenizerFast.from_pretrained("t5-small")
TOKENIZER.pad_token = TOKENIZER.eos_token  # IMPORTANT
MAX_NEW_TOKENS = 256  # SQL is long

def get_args():
    '''
    Arguments for training. You may choose to change or extend these as you see fit.
    '''
    parser = argparse.ArgumentParser(description='T5 training loop')

    # Model hyperparameters
    parser.add_argument('--finetune', action='store_true', help="Whether to finetune T5 or not")

    # NEW: Training hyperparameters
    parser.add_argument('--learning_rate', type=float, default=3e-4,
                        help="Learning rate for optimizer")
    parser.add_argument('--freeze_encoder_epochs', type=int, default=5,
                        help="Number of initial epochs to freeze encoder")

    # Existing training hyperparameters
    parser.add_argument('--optimizer_type', type=str, default="AdamW", choices=["AdamW"],
                        help="What optimizer to use")
    parser.add_argument('--weight_decay', type=float, default=0)
    parser.add_argument('--scheduler_type', type=str, default="cosine", choices=["none", "cosine", "linear"],
                        help="Whether to use a LR scheduler and what type to use if so")
    parser.add_argument('--num_warmup_epochs', type=int, default=0)
    parser.add_argument('--max_n_epochs', type=int, default=25,
                        help="How many epochs to train the model for")
    parser.add_argument('--patience_epochs', type=int, default=5,
                        help="How many epochs to wait before early stopping")

    # Wandb + experiment name
    parser.add_argument('--use_wandb', action='store_true')
    parser.add_argument('--experiment_name', type=str, default='ft_experiment')

    # Data
    parser.add_argument('--batch_size', type=int, default=16)
    parser.add_argument('--test_batch_size', type=int, default=16)

    args = parser.parse_args()
    return args

def initialize_model(args):
    model = T5ForConditionalGeneration.from_pretrained("t5-small")
    model = model.to(DEVICE)
    model.config.pad_token_id = TOKENIZER.pad_token_id
    return model

def freeze_encoder(model):
    for name, param in model.named_parameters():
        if "encoder" in name:
            param.requires_grad = False

def unfreeze_encoder(model):
    for name, param in model.named_parameters():
        if "encoder" in name:
            param.requires_grad = True

def train_epoch(model, loader, optimizer, scheduler):
    model.train()
    total_loss = 0

    for enc_in, enc_mask, dec_in, dec_tgt, _ in tqdm(loader):
        enc_in, enc_mask, dec_tgt = (
            enc_in.to(DEVICE),
            enc_mask.to(DEVICE),
            dec_tgt.to(DEVICE),
        )
        optimizer.zero_grad()

        outputs = model(
            input_ids=enc_in,
            attention_mask=enc_mask,
            labels=dec_tgt
        )

        loss = outputs.loss
        loss.backward()

        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss / len(loader)

def eval_epoch(model, loader, gt_sql, model_sql, gt_rec, model_rec):
    model.eval()
    total_loss = 0
    all_sql = []

    with torch.no_grad():
        for enc_in, enc_mask, dec_in, dec_tgt, _ in tqdm(loader):
            enc_in, enc_mask, dec_tgt = (
                enc_in.to(DEVICE),
                enc_mask.to(DEVICE),
                dec_tgt.to(DEVICE)
            )

            out = model(
                input_ids=enc_in,
                attention_mask=enc_mask,
                labels=dec_tgt
            )

            total_loss += out.loss.item()

            gen = model.generate(
                input_ids=enc_in,
                attention_mask=enc_mask,
                max_new_tokens=MAX_NEW_TOKENS
            )
            decoded = TOKENIZER.batch_decode(gen, skip_special_tokens=True)
            all_sql.extend([x.strip() for x in decoded])

    eval_loss = total_loss / len(loader)
    save_queries_and_records(all_sql, model_sql, model_rec)

    sql_em, record_em, record_f1, errors = compute_metrics(gt_sql, model_sql, gt_rec, model_rec)
    error_rate = sum(1 for e in errors if e) / len(errors)

    return eval_loss, record_f1, record_em, sql_em, error_rate

# Modify your generate_and_save_test_results function to match the data structure
def generate_and_save_test_results(test_loader, model, tokenizer):
    model.eval()
    predicted_sqls = []

    with torch.no_grad():
        for enc_in, enc_mask in tqdm(test_loader, desc="Generating SQL queries", ncols=100):  # Adjust unpacking here
            enc_in, enc_mask = enc_in.to(DEVICE), enc_mask.to(DEVICE)

            outputs = model.generate(
                input_ids=enc_in,
                attention_mask=enc_mask,
                max_length=256
            )
            decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
            predicted_sqls.extend([sql.strip() for sql in decoded])

    # Save the SQL predictions
    os.makedirs("results", exist_ok=True)
    with open("results/t5_ft_test.sql", "w") as f:
        for sql in predicted_sqls:
            f.write(sql + "\n")

    print("Test SQL queries saved to 'results/t5_ft_test.sql'")



def main():
    args = get_args()

    # wandb
    if args.use_wandb:
        wandb.init(project="t5-sql", name=args.experiment_name)

    # Load data
    train_loader, dev_loader, test_loader = load_t5_data(
        args.batch_size, args.test_batch_size
    )

    model = initialize_model(args)

    if args.freeze_encoder_epochs > 0:
        freeze_encoder(model)

    optimizer = AdamW(model.parameters(), lr=args.learning_rate)
    total_steps = len(train_loader) * args.max_n_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(0.05 * total_steps),
        num_training_steps=total_steps,
    )

    best_f1 = -1
    patience = 0

    checkpoint = f"checkpoints/{args.experiment_name}"
    os.makedirs(checkpoint, exist_ok=True)

    # Train loop
    for epoch in range(args.max_n_epochs):
        print(f"\n=== Epoch {epoch} ===")

        if epoch == args.freeze_encoder_epochs:
            unfreeze_encoder(model)
            print("Unfroze encoder!")

        train_loss = train_epoch(model, train_loader, optimizer, scheduler)
        print(f"Train loss: {train_loss:.4f}")

        # Evaluate
        eval_loss, f1, rec_em, sql_em, err = eval_epoch(
            model, dev_loader,
            "data/dev.sql",
            f"results/{args.experiment_name}_dev.sql",
            "records/ground_truth_dev.pkl",
            f"records/{args.experiment_name}_dev.pkl"
        )
        print(f"Dev loss: {eval_loss:.4f} | F1: {f1:.4f} | EM: {rec_em:.4f} | SQL EM: {sql_em:.4f}")

        # Save best model
        if f1 > best_f1:
            best_f1 = f1
            patience = 0
            model.save_pretrained(checkpoint)
            TOKENIZER.save_pretrained(checkpoint)
            print("Saved new best model!")

        else:
            patience += 1

        if patience >= args.patience_epochs:
            print("Early stopping.")
            break

    # After training is done, generate test results
    generate_and_save_test_results(
        model,
        test_loader,
        "results/t5_ft_experiment_test.sql",
        "records/t5_ft_experiment_test.pkl"
    )

if __name__ == "__main__":
    main()
