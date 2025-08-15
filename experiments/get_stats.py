#!/usr/bin/env python3
import argparse
import csv
import math
from statistics import mean, median, stdev
from collections import defaultdict
from typing import List, Dict, Tuple

def load_csv(path: str) -> Dict[str, List[float]]:
    groups: Dict[str, List[float]] = defaultdict(list)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if "test" not in reader.fieldnames or "duration_ms" not in reader.fieldnames:
            raise ValueError("CSV must have headers: test,duration_ms")
        for _lineno, row in enumerate(reader, start=2):  # line 1 is header
            test = (row.get("test") or "").strip()
            val = row.get("duration_ms")
            if not test:
                continue
            try:
                dur = float(val)
            except (TypeError, ValueError):
                continue
            groups[test].append(dur)
    if not groups:
        raise ValueError("No valid rows found.")
    return groups

def summarize(groups: Dict[str, List[float]]) -> List[Tuple[str, int, float, float, float, float, float]]:
    rows = []
    for test, vals in groups.items():
        if not vals:
            continue
        cnt = len(vals)
        mn = min(vals)
        mx = max(vals)
        avg = mean(vals)
        med = median(vals)
        sd = stdev(vals) if cnt > 1 else 0.0   # sample stdev (n-1)
        rows.append((test, cnt, mn, mx, avg, med, sd))
    rows.sort(key=lambda r: r[0])  # sort by test name
    return rows

def format_number(x: float) -> str:
    if math.isfinite(x) and abs(x - round(x)) < 1e-12:
        return f"{int(round(x))}"
    return f"{x:.3f}"

def print_table(rows: List[Tuple[str, int, float, float, float, float, float]]) -> None:
    headers = ["test", "count", "min_ms", "max_ms", "mean_ms", "median_ms", "stddev_ms"]
    str_rows = [
        [r[0], str(r[1]), format_number(r[2]), format_number(r[3]),
         format_number(r[4]), format_number(r[5]), format_number(r[6])]
        for r in rows
    ]
    widths = [len(h) for h in headers]
    for r in str_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep  = "  ".join("-" * widths[i] for i in range(len(headers)))
    print(line)
    print(sep)
    for r in str_rows:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))

def write_csv(rows: List[Tuple[str, int, float, float, float, float, float]], out_path: str) -> None:
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["test", "count", "min_ms", "max_ms", "mean_ms", "median_ms", "stddev_ms"])
        for test, cnt, mn, mx, avg, med, sd in rows:
            writer.writerow([test, cnt, f"{mn:.6f}", f"{mx:.6f}", f"{avg:.6f}", f"{med:.6f}", f"{sd:.6f}"])

def main():
    ap = argparse.ArgumentParser(
        description="Summarize duration_ms by test (min, max, mean, median, stddev) from a CSV."
    )
    ap.add_argument("input", help="Path to input CSV with columns: test,duration_ms")
    ap.add_argument("output", help="Path to write summary CSV")
    args = ap.parse_args()

    groups = load_csv(args.input)
    rows = summarize(groups)
    print_table(rows)
    write_csv(rows, args.output)

if __name__ == "__main__":
    main()
