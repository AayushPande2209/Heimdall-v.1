import numpy as np

X = np.array([
    [0.9, 0.9],
    [0.8, 0.7],   
    [0.7, 0.9],  
    [0.6, 0.6],   
    [0.2, 0.3],   
    [0.9, 0.1],   
    [0.3, 0.8],   
    [0.1, 0.1],
])

y = np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=float)
N = len(y)


w = np.zeros(X.shape[1])
b = 0.0


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


learning_rate = 10.0

for step in range(5001):
    z = X @ w + b
    p = sigmoid(z)
    p = np.clip(p, 1e-7, 1 - 1e-7)
    
    loss = -np.mean(y * np.log(p) + (1 - y) * np.log(1-p))
    
    error = p - y
    dw = X.T @ error / N
    db = error.mean()
    
    if step == 0:
        print(f"first step: dw = {dw.round(3)}, db = {db:.3f}")
    if step % 500 == 0:
        accuracy = ((p > 0.5) == y).mean()
        print(f"step {step:5d}   loss {loss:.3f}   accuracy {accuracy * 100:.0f}%")
        
    w = w - learning_rate * dw
    b = b - learning_rate * db
    

print(f"\nlearned weights: contrast {w[0]:.2f}, temperature {w[1]:.2f}   bias {b:.2f}")

print("\npredictions on the training blobs:")
for xi, yi in zip(X, y):
    print(f"  {xi}  label {int(yi)}  ->  {sigmoid(xi @ w + b):.2f}")

print("\nnew blobs it has never seen:")
for xi in [np.array([0.95, 0.15]), np.array([0.85, 0.85])]:
    print(f"  {xi}  ->  {sigmoid(xi @ w + b):.2f}")
    





