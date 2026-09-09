import numpy as np

np.random.seed(42)
steps = 1000
t = np.arange(steps)

prices = 100 + (0.05 * t) + (15 * np.sin(t / 25)) + np.random.normal(0, 0.2, steps)

with open('synthetic_stock_prices.txt', 'w') as f:
    for price in prices:
        f.write(f"{price:.4f}\n")
