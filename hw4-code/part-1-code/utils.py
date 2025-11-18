import datasets
from datasets import load_dataset
from transformers import AutoTokenizer
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification
from torch.optim import AdamW
from transformers import get_scheduler
import torch
from tqdm.auto import tqdm
import evaluate
import random
import argparse
from nltk.corpus import wordnet
from nltk import word_tokenize
from nltk.tokenize.treebank import TreebankWordDetokenizer
import string

random.seed(0)


def example_transform(example):
    example["text"] = example["text"].lower()
    return example

QWERTY_NEIGHBORS= {
    "a": ["s", "q", "w", "z"],
    "b": ["v", "g", "h", "n"],
    "c": ["x", "d", "f", "v"],
    "d": ["s", "e", "r", "f", "c", "x"],
    "e": ["w", "s", "d", "r"],
    "f": ["d", "r", "t", "g", "v", "c"],
    "g": ["f", "t", "y", "h", "b", "v"],
    "h": ["g", "y", "u", "j", "n", "b"],
    "i": ["u", "j", "k", "o"],
    "j": ["h", "u", "i", "k", "m", "n"],
    "k": ["j", "i", "o", "l", "m"],
    "l": ["k", "o", "p"],
    "m": ["n", "j", "k"],
    "n": ["b", "h", "j", "m"],
    "o": ["i", "k", "l", "p"],
    "p": ["o", "l"],
    "q": ["w", "a"],
    "r": ["e", "d", "f", "t"],
    "s": ["a", "w", "e", "d", "x", "z"],
    "t": ["r", "f", "g", "y"],
    "u": ["y", "h", "j", "i"],
    "v": ["c", "f", "g", "b"],
    "w": ["q", "a", "s", "e"],
    "x": ["z", "s", "d", "c"],
    "y": ["t", "g", "h", "u"],
    "z": ["a", "s", "x"]
}

def _introduce_typo(word):
    if len(word) <= 1:
        return word
    idx = random.randint(0, len(word) - 1)
    letter = word[idx].lower()
    if letter in QWERTY_NEIGHBORS:
        replacement = random.choice(QWERTY_NEIGHBORS[letter])
        return word[:idx] + replacement + word[idx + 1:]
    return word

# Get a random synonym
def _get_synonym(word):
    synsets = wordnet.synsets(word)
    if not synsets:
        return None
    lemmas = [l.name() for s in synsets for l in s.lemmas() if l.name().lower() != word.lower()]
    return random.choice(lemmas) if lemmas else None
### Rough guidelines --- typos
# For typos, you can try to simulate nearest keys on the QWERTY keyboard for some of the letter (e.g. vowels)
# You can randomly select each word with some fixed probability, and replace random letters in that word with one of the
# nearest keys on the keyboard. You can vary the random probablity or which letters to use to achieve the desired accuracy.


### Rough guidelines --- synonym replacement
# For synonyms, use can rely on wordnet (already imported here). Wordnet (https://www.nltk.org/howto/wordnet.html) includes
# something called synsets (which stands for synonymous words) and for each of them, lemmas() should give you a possible synonym word.
# You can randomly select each word with some fixed probability to replace by a synonym.


# Aggressive transform function
def custom_transform(example):
    text = example["text"]
    tokens = word_tokenize(text)
    transformed_tokens = []

    for tok in tokens:
        r = random.random()

        # Only transform alphabetic words
        if tok.isalpha():
            if r < 0.20:  # 20% chance synonym
                syn = _get_synonym(tok)
                if syn:
                    transformed_tokens.append(syn)
                    continue
            elif r < 0.40:  # 20% chance typo
                transformed_tokens.append(_introduce_typo(tok))
                continue
            elif r < 0.45:  # 5% chance punctuation/noise
                transformed_tokens.append(tok + random.choice(string.punctuation))
                continue

        # Keep original token if no transformation applied
        transformed_tokens.append(tok)

    # Detokenize
    detok = TreebankWordDetokenizer().detokenize(transformed_tokens)
    example["text"] = detok
    return example

