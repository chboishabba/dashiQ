"""
Minimal p-adic toy illustrating non-monotonic detectability via digit aliasing.

We treat epsilon as a scaled integer and observe only a single base-p digit.
When that digit aliases to 0, a more complex model becomes indistinguishable
from a simpler one, producing non-monotonic detection vs epsilon.
"""

import argparse
import math
import random


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--p", type=int, default=3, help="p-adic base")
    p.add_argument("--scale", type=int, default=100, help="epsilon scaling to integer")
    p.add_argument("--eps-min", type=float, default=0.0)
    p.add_argument("--eps-max", type=float, default=1.2)
    p.add_argument("--eps-steps", type=int, default=13)
    p.add_argument("--trials", type=int, default=1000)
    p.add_argument("--noise", type=int, default=1, help="integer noise added before digit readout")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--plot", action="store_true", help="write plot if matplotlib is available")
    p.add_argument("--plot-path", default="p_adic_toy.png")
    p.add_argument("--csv-path", default="p_adic_toy.csv")
    return p.parse_args()


def detect_rate(eps, p_base, scale, trials, noise, rng):
    n = int(round(eps * scale))
    hits = 0
    for _ in range(trials):
        n_obs = n + rng.randint(-noise, noise)
        digit = abs(n_obs) % p_base
        if digit != 0:
            hits += 1
    return hits / trials


def main():
    args = parse_args()
    rng = random.Random(args.seed)
    epsilons = [
        args.eps_min + i * (args.eps_max - args.eps_min) / (args.eps_steps - 1)
        for i in range(args.eps_steps)
    ]
    rows = []
    for eps in epsilons:
        rate = detect_rate(
            eps, args.p, args.scale, args.trials, args.noise, rng
        )
        rows.append((eps, rate))

    with open(args.csv_path, "w", encoding="utf-8") as f:
        f.write("eps,detect\n")
        for eps, rate in rows:
            f.write(f"{eps:.6f},{rate:.6f}\n")

    print("p-adic toy detectability")
    print(f"p={args.p} scale={args.scale} trials={args.trials} noise=±{args.noise}")
    for eps, rate in rows:
        print(f"  eps={eps:.3f} detect={rate:.2f}")
    print(f"wrote {args.csv_path}")

    if args.plot:
        try:
            import matplotlib.pyplot as plt
        except Exception:
            print("matplotlib not available; skip plot")
            return
        xs = [r[0] for r in rows]
        ys = [r[1] for r in rows]
        plt.figure(figsize=(6, 3.5))
        plt.plot(xs, ys, marker="o", linewidth=1.5)
        plt.xlabel("epsilon")
        plt.ylabel("detect rate")
        plt.title("p-adic digit aliasing (toy)")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(args.plot_path, dpi=150)
        print(f"wrote {args.plot_path}")


if __name__ == "__main__":
    main()
