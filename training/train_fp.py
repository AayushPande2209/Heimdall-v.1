"""
Train the Heimdall crop classifier on ForestPersonsIR crops.

Same CNN as exercise 3 (cnn.py). The differences:
  - normalize() divides by each crop's own spread, because these crops are
    grey levels, not degrees C (and so the Pi can feed it Lepton crops later)
  - random left/right flips during training (a mirrored person is still a person)
  - uses the Mac's GPU ("mps") if it's available, otherwise the CPU
  - reports results by pose and by how much of the person was visible

Run from the repository root:
  python3 -m training.train_fp
"""
from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fpir_full"         # made by the data-prep step
MODEL = ROOT / "models" / "_local" / "heimdall_cnn_full.pt"

torch.manual_seed(0)
device = "mps" if torch.backends.mps.is_available() else "cpu"
print("training on:", device)


# ---- 1. Load the crops ----
def load(path):
    d = np.load(path, allow_pickle=False)
    return {k: d[k] for k in d.files}

train = load(DATA / "crops_train.npz")
val = load(DATA / "crops_val.npz")
test = load(DATA / "crops_test.npz")
print("train crops:", train["crops"].shape, " val:", val["crops"].shape, " test:", test["crops"].shape)
print(f"train: {int(train['labels'].sum())} person, {int((1 - train['labels']).sum())} not")


# ---- 2. Normalize: unit-free, so grey levels and Lepton degrees look alike ----
# Background goes to ~0, and every crop gets a spread of 1.
# The Pi must do EXACTLY this to each Lepton crop before running the model.
def normalize(crops):
    med = np.median(crops, axis=(1, 2), keepdims=True)
    std = crops.std(axis=(1, 2), keepdims=True)
    return (crops - med) / (std + 1e-6)


def to_tensors(d):
    x = torch.tensor(normalize(d["crops"]), dtype=torch.float32).unsqueeze(1)  # (N, 1, 64, 32)
    y = torch.tensor(d["labels"], dtype=torch.float32)
    return x.to(device), y.to(device)

x_train, y_train = to_tensors(train)
x_val, y_val = to_tensors(val)
x_test, y_test = to_tensors(test)

train_loader = DataLoader(TensorDataset(x_train, y_train), batch_size=64, shuffle=True)


# ---- 3. The model (identical to cnn.py) ----
model = nn.Sequential(
    nn.Conv2d(1, 8, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),     # (8, 32, 16)
    nn.Conv2d(8, 16, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),    # (16, 16, 8)
    nn.Conv2d(16, 32, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),   # (32, 8, 4)
    nn.Flatten(),
    nn.Linear(1024, 32), nn.ReLU(),
    nn.Linear(32, 1),
).to(device)
print("learned numbers:", sum(p.numel() for p in model.parameters()))


# ---- 4. Train ----
def augment(xb):
    """Random changes to a batch of normalized crops, shape (B, 1, 64, 32).
    Each one makes the model rely on body shape instead of scene details."""
    B, dev = xb.shape[0], xb.device

    # 1. flip left-right (half the batch)
    flip = torch.rand(B, device=dev) < 0.5
    xb = torch.where(flip[:, None, None, None], xb.flip(3), xb)

    # 2. small zoom and shift: the tracker never centres crops perfectly
    s = torch.empty(B, device=dev).uniform_(0.85, 1.15)          # zoom
    tx = torch.empty(B, device=dev).uniform_(-0.1, 0.1)           # shift (fraction of width)
    ty = torch.empty(B, device=dev).uniform_(-0.1, 0.1)
    theta = torch.zeros(B, 2, 3, device=dev)
    theta[:, 0, 0], theta[:, 1, 1] = s, s
    theta[:, 0, 2], theta[:, 1, 2] = tx, ty
    grid = F.affine_grid(theta, xb.shape, align_corners=False)
    xb = F.grid_sample(xb, grid, padding_mode="border", align_corners=False)

    # 3. blur a third of the batch: less detail, like a farther person or a softer lens
    k = torch.tensor([1.0, 2.0, 1.0], device=dev)
    k2 = (k[:, None] * k[None, :]) / 16.0
    blurred = F.conv2d(F.pad(xb, (1, 1, 1, 1), mode="replicate"), k2[None, None])
    blur = torch.rand(B, device=dev) < 0.33
    xb = torch.where(blur[:, None, None, None], blurred, xb)

    # 4. fake trunk: a vertical background-coloured strip over part of 30% of crops
    occl = torch.rand(B, device=dev) < 0.3
    cols = torch.arange(32, device=dev)[None, :]                   # (1, 32)
    width = torch.randint(3, 11, (B, 1), device=dev)
    start = (torch.rand(B, 1, device=dev) * (32 - width)).long()
    strip = (cols >= start) & (cols < start + width) & occl[:, None]   # (B, 32)
    xb = torch.where(strip[:, None, None, :], torch.zeros_like(xb), xb)  # 0 = background after normalize

    # 5. sensor noise of random strength
    sigma = torch.empty(B, 1, 1, 1, device=dev).uniform_(0.0, 0.25)
    xb = xb + sigma * torch.randn_like(xb)
    return xb

optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
loss_fn = nn.BCEWithLogitsLoss()


def predict(x, batch=4096):
    model.eval()
    with torch.no_grad():
        p = torch.cat([torch.sigmoid(model(x[i:i + batch]).squeeze(1))
                       for i in range(0, len(x), batch)])
    model.train()
    return p


def accuracy(x, y):
    return ((predict(x) > 0.5).float() == y).float().mean().item() * 100


best_val, EPOCHS = 0.0, 25
for epoch in range(1, EPOCHS + 1):
    total = 0.0
    for xb, yb in train_loader:
        xb = augment(xb)                    # a new random variation every time

        loss = loss_fn(model(xb).squeeze(1), yb)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total += loss.item() * len(yb)

    tr, va = accuracy(x_train, y_train), accuracy(x_val, y_val)
    note = ""
    if va > best_val:                       # keep the epoch that does best on val
        best_val = va
        torch.save(model.state_dict(), MODEL)
        note = "  <- best so far, saved"
    print(f"epoch {epoch:2d}   loss {total / len(y_train):.3f}   train {tr:.1f}%   val {va:.1f}%{note}")


# ---- 5. Report on the best model ----
model.load_state_dict(torch.load(MODEL))


def report(name, d, x, y):
    pred = (predict(x) > 0.5).cpu().numpy()
    labels = d["labels"]
    print(f"\n{name}: {100 * (pred == labels).mean():.1f}% overall")
    for kind in ["person", "hard_neg", "rand_neg"]:
        m = d["kinds"] == kind
        if m.any():
            print(f"  {kind:<9} {100 * (pred[m] == labels[m]).mean():5.1f}%   ({m.sum()} crops)")
    print("  people found, by pose and % visible:")
    for pose in ["standing", "sitting", "lying"]:
        cells = []
        for v in [100, 70, 40, 20]:
            m = (d["kinds"] == "person") & (d["pose"] == pose) & (d["visibility"] == v)
            cells.append(f"{v:>3}%: {100 * pred[m].mean():5.1f}% of {m.sum():<4}" if m.any() else f"{v:>3}%:   n/a      ")
        print(f"    {pose:<9}" + "   ".join(cells))

report("VALIDATION", val, x_val, y_val)
# The test set is the honest final score. Only look at it once you're done
# tweaking things based on validation, or it stops being a fair test.
report("TEST", test, x_test, y_test)
print("\nbest model saved as models/_local/heimdall_cnn_full.pt")
