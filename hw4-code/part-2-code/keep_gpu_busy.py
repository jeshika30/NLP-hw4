cat > keep_gpu_busy.py

import torch
import time

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

x = torch.randn(256, 256, device=device)

while True:
    x = x @ x
    torch.cuda.synchronize()
    time.sleep(10)
