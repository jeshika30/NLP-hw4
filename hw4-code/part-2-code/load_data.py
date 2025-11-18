# load_data.py

import os
from collections import Counter

from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence
import torch

import nltk
nltk.download('punkt')
from transformers import T5TokenizerFast

PAD_IDX = 0


class T5Dataset(Dataset):
    def __init__(self, data_folder, split):
        """
        Dataset class for T5 preprocessing.
        """
        self.data_folder = data_folder
        self.split = split
        self.tokenizer = T5TokenizerFast.from_pretrained("google-t5/t5-small")
        self.bos_token_id = self.tokenizer.convert_tokens_to_ids("<extra_id_0>")

        (
            self.encoder_ids,
            self.decoder_inputs,
            self.decoder_targets,
            self.initial_decoder_inputs,
        ) = self.process_data(data_folder, split, self.tokenizer)

    def process_data(self, data_folder, split, tokenizer):
        nl_path = os.path.join(data_folder, f"{split}.nl")
        nl_lines = load_lines(nl_path)

        if split != "test":
            sql_path = os.path.join(data_folder, f"{split}.sql")
            sql_lines = load_lines(sql_path)
            assert len(nl_lines) == len(sql_lines)
        else:
            sql_lines = [None] * len(nl_lines)

        encoder_ids = []
        decoder_inputs = []
        decoder_targets = []
        initial_decoder_inputs = []

        max_enc_len = 256
        max_dec_len = 256

        for i, nl in enumerate(nl_lines):
            # encoder tokenization
            enc = tokenizer(
                nl,
                truncation=True,
                max_length=max_enc_len,
                padding=False,
                return_tensors="pt",
            )
            enc_ids = enc["input_ids"].squeeze(0)
            encoder_ids.append(enc_ids)

            if split != "test":
                sql = sql_lines[i]
                tgt = tokenizer(
                    sql + tokenizer.eos_token,
                    truncation=True,
                    max_length=max_dec_len,
                    padding=False,
                    return_tensors="pt",
                )
                tgt_ids = tgt["input_ids"].squeeze(0)

                bos = torch.tensor([self.bos_token_id], dtype=torch.long)
                dec_in = torch.cat([bos, tgt_ids[:-1]], dim=0)

                decoder_inputs.append(dec_in)
                decoder_targets.append(tgt_ids)
                initial_decoder_inputs.append(self.bos_token_id)
            else:
                decoder_inputs.append(None)
                decoder_targets.append(None)
                initial_decoder_inputs.append(self.bos_token_id)

        return encoder_ids, decoder_inputs, decoder_targets, initial_decoder_inputs

    def __len__(self):
        return len(self.encoder_ids)

    def __getitem__(self, idx):
        return {
            "encoder_ids": self.encoder_ids[idx],
            "decoder_inputs": self.decoder_inputs[idx],
            "decoder_targets": self.decoder_targets[idx],
            "initial_decoder_input": self.initial_decoder_inputs[idx],
        }


def normal_collate_fn(batch):
    enc_list = [item["encoder_ids"] for item in batch]
    enc_padded = pad_sequence(enc_list, batch_first=True, padding_value=PAD_IDX)
    encoder_mask = (enc_padded != PAD_IDX).long()

    dec_in_list = [item["decoder_inputs"] for item in batch]
    dec_tgt_list = [item["decoder_targets"] for item in batch]
    dec_in_padded = pad_sequence(dec_in_list, batch_first=True, padding_value=PAD_IDX)
    dec_tgt_padded = pad_sequence(dec_tgt_list, batch_first=True, padding_value=PAD_IDX)

    init_list = [item["initial_decoder_input"] for item in batch]
    initial_decoder_inputs = torch.tensor(init_list, dtype=torch.long).unsqueeze(1)

    return enc_padded, encoder_mask, dec_in_padded, dec_tgt_padded, initial_decoder_inputs


def test_collate_fn(batch):
    enc_list = [item["encoder_ids"] for item in batch]
    enc_padded = pad_sequence(enc_list, batch_first=True, padding_value=PAD_IDX)
    encoder_mask = (enc_padded != PAD_IDX).long()

    init_list = [item["initial_decoder_input"] for item in batch]
    initial_decoder_inputs = torch.tensor(init_list, dtype=torch.long).unsqueeze(1)

    return enc_padded, encoder_mask, initial_decoder_inputs


def get_dataloader(batch_size, split):
    data_folder = 'data'
    dset = T5Dataset(data_folder, split)
    shuffle = split == "train"
    collate_fn = normal_collate_fn if split != "test" else test_collate_fn
    return DataLoader(dset, batch_size=batch_size, shuffle=shuffle, collate_fn=collate_fn)


def load_t5_data(batch_size, test_batch_size):
    train_loader = get_dataloader(batch_size, "train")
    dev_loader = get_dataloader(test_batch_size, "dev")
    test_loader = get_dataloader(test_batch_size, "test")
    return train_loader, dev_loader, test_loader


def load_lines(path):
    with open(path, 'r') as f:
        lines = [line.strip() for line in f.readlines()]
    return lines


def load_prompting_data(data_folder):
    train_x = load_lines(os.path.join(data_folder, "train.nl"))
    train_y = load_lines(os.path.join(data_folder, "train.sql"))
    dev_x = load_lines(os.path.join(data_folder, "dev.nl"))
    dev_y = load_lines(os.path.join(data_folder, "dev.sql"))
    test_x = load_lines(os.path.join(data_folder, "test.nl"))
    return train_x, train_y, dev_x, dev_y, test_x


def print_postprocessing_stats(data_folder):
    """
    Compute and print statistics after preprocessing (tokenization) for train/dev sets.
    """
    for split in ["train", "dev"]:
        dataset = T5Dataset(data_folder, split)

        # Tokenized lengths
        enc_lengths = [len(ids) for ids in dataset.encoder_ids]
        dec_lengths = [len(ids) for ids in dataset.decoder_targets]

        # Vocabulary (unique token IDs)
        enc_vocab = set()
        for ids in dataset.encoder_ids:
            enc_vocab.update(ids.tolist())

        dec_vocab = set()
        for ids in dataset.decoder_targets:
            dec_vocab.update(ids.tolist())

        print(f"{split.capitalize()} Statistics AFTER preprocessing:")
        print(f"Number of examples: {len(dataset)}")
        print(f"Mean tokenized sentence length: {sum(enc_lengths)/len(enc_lengths):.2f}")
        print(f"Mean tokenized SQL length: {sum(dec_lengths)/len(dec_lengths):.2f}")
        print(f"Vocabulary size (encoder tokens): {len(enc_vocab)}")
        print(f"Vocabulary size (decoder tokens): {len(dec_vocab)}")
        print("-" * 50)


if __name__ == "__main__":
    data_folder = "data"
    print_postprocessing_stats(data_folder)
