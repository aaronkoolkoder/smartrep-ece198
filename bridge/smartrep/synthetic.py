"""Write deterministic raw MPU CSV fixtures with a still interval first."""
import argparse
import csv
from pathlib import Path
import random
from .sources.sim_source import sample_at


def write_csv(path, reps, period=2.5, amplitude=110, seed=1):
    rng = random.Random(seed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["ms", "ax", "ay", "az", "gx", "gy", "gz"]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for index in range(round((0.6 + reps * period + 0.5) * 50) + 1):
            time = index / 50
            movement = min(max(time - 0.6, 0), reps * period)
            sample = sample_at(movement, rng, period, amplitude)
            sample["ms"] = index * 20
            writer.writerow(sample)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic calibration and 10-rep replay CSVs")
    parser.add_argument("--output", type=Path, default=Path("recordings"))
    args = parser.parse_args()
    write_csv(args.output / "curls_cal.csv", 3)
    write_csv(args.output / "curls_good_10.csv", 10)
    print(f"Wrote {args.output / 'curls_cal.csv'} and {args.output / 'curls_good_10.csv'}")


if __name__ == "__main__":
    main()
