"""Independently check the immutable mom20 development run. Requires pandas and scipy."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def verify(snapshot: Path, run: Path, *, ic_output=None) -> dict:
    manifest = json.loads((snapshot / "manifest.json").read_text("utf-8"))
    for filename, digest in manifest["sha256"].items():
        if hashlib.sha256((snapshot / filename).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Snapshot hash mismatch: {filename}")

    market = pd.read_csv(snapshot / "market.csv").set_index(["date", "asset"], verify_integrity=True)
    universe = pd.read_csv(snapshot / "universe.csv").set_index(["date", "asset"], verify_integrity=True)
    dates = pd.read_csv(snapshot / "calendar.csv").date
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Invalid calendar")
    prices = (market.close * market.adj_factor).unstack().reindex(dates)
    momentum = prices.div(prices.shift(20)).sub(1)
    observations = momentum.stack().rename("factor").to_frame()
    for days in (1, 5, 20):
        complete = prices.notna().rolling(days + 1).sum().shift(-1-days).eq(days+1)
        returns = prices.shift(-1-days).div(prices.shift(-1)).sub(1).where(complete)
        observations[f"{days}D"] = returns.stack()
    valid = observations.join(universe.eligible).query("eligible == 1").dropna().drop(columns="eligible")
    valid["factor_quantile"] = valid.factor.groupby(level="date").transform(
        lambda values: pd.qcut(values, 5, labels=False) + 1
    )
    clean = pd.read_csv(run / "clean_factor.csv").set_index(["date", "asset"], verify_integrity=True)
    if not valid.index.sort_values().equals(clean.index.sort_values()):
        raise ValueError("Research and independent sample membership differ")
    delta = (valid - clean).abs().max()
    independent_ic = pd.DataFrame({
        horizon: valid.groupby(level="date").apply(
            lambda block: block.factor.corr(block[horizon], method="spearman")
        ) for horizon in ("1D", "5D", "20D")
    })
    if ic_output is not None:
        independent_ic.to_csv(ic_output)
    reported_ic = pd.read_csv(run / "rank_ic.csv").set_index("date", verify_integrity=True)
    if not independent_ic.index.equals(reported_ic.index):
        raise ValueError("IC date membership differs")
    ic_delta = (independent_ic - reported_ic).abs()
    if not ic_delta.notna().all().all() or ic_delta.max().max() > 1e-8 or delta.max() > 1e-8:
        raise ValueError("Independent numerical reproduction failed")
    return dict(snapshot_files=len(manifest["sha256"]), market_rows=len(market),
                market_assets=market.index.get_level_values("asset").nunique(),
                sessions=len(dates), clean_rows=len(valid), ic_sessions=len(independent_ic),
                max_absolute_difference=delta.to_dict(), max_ic_difference=ic_delta.max().to_dict(),
                mean_ic=independent_ic.mean().to_dict(), pit_declared=manifest["pit_certified"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.snapshot, args.run), indent=2, allow_nan=False))
