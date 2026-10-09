import argparse
import glob
import logging
import sys
from pathlib import Path

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("analyze")

# High-resolution chart aesthetics
plt.style.use(
    "seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default"
)
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

# Critical t-values for two-tailed 95% confidence intervals (alpha = 0.05)
T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
    30: 2.042,
    50: 2.009,
    100: 1.984,
}


def compute_ci95(series: pd.Series) -> tuple[float, float, float]:
    """Compute mean and 95% confidence interval half-width using Student's t-distribution."""
    vals = series.dropna().to_numpy()
    n = len(vals)
    if n == 0:
        return np.nan, np.nan, np.nan
    mean_val = float(np.mean(vals))
    if n == 1:
        return mean_val, mean_val, 0.0

    df = n - 1
    t_val = T_CRITICAL_95.get(df, 1.96 if df > 30 else 2.571)
    se = float(np.std(vals, ddof=1) / np.sqrt(n))
    h = float(se * t_val)
    return mean_val, mean_val - h, h


def load_raw_dataset(raw_dir: Path) -> pd.DataFrame:
    files = glob.glob(str(raw_dir / "*.csv"))
    if not files:
        logger.warning("No CSV files found in %s", raw_dir)
        return pd.DataFrame()

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            if not df.empty and "backend" in df.columns:
                dfs.append(df)
        except Exception as e:
            logger.warning("Skipping file %s: %s", f, e)

    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    combined["users"] = pd.to_numeric(combined["users"], errors="coerce")
    combined["latency_ms"] = pd.to_numeric(combined["latency_ms"], errors="coerce")
    combined["run"] = pd.to_numeric(combined["run"], errors="coerce")
    return combined


def load_resource_dataset(res_dir: Path) -> pd.DataFrame:
    files = glob.glob(str(res_dir / "*.csv"))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            if not df.empty and "target" in df.columns:
                # Extract metadata from filename (e.g. postgres_small_u50_run1.csv)
                fname = Path(f).stem
                parts = fname.split("_")
                backend = parts[0]
                users = int(parts[2].replace("u", "")) if len(parts) > 2 and "u" in parts[2] else 0
                run = (
                    int(parts[3].replace("run", "")) if len(parts) > 3 and "run" in parts[3] else 1
                )
                df["backend"] = backend
                df["users"] = users
                df["run"] = run
                dfs.append(df)
        except Exception as e:
            logger.warning("Skipping resource file %s: %s", f, e)
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def generate_summary_tables(
    raw_df: pd.DataFrame, res_df: pd.DataFrame, results_dir: Path
) -> pd.DataFrame:
    if raw_df.empty:
        logger.warning("Raw dataset empty; skipping summary table generation.")
        return pd.DataFrame()

    # Per-run aggregates
    run_records = []
    for (backend, scale, users, run), group in raw_df.groupby(["backend", "scale", "users", "run"]):
        latencies = group["latency_ms"].dropna()
        total_reqs = len(group)
        success_reqs = (group["status"] == "SUCCESS").sum()
        fail_reqs = total_reqs - success_reqs
        error_rate = (fail_reqs / total_reqs) * 100 if total_reqs > 0 else 0.0

        # Calculate throughput based on timestamp span or count
        group_ts = pd.to_datetime(group["timestamp"], errors="coerce").dropna()
        span_s = (group_ts.max() - group_ts.min()).total_seconds() if len(group_ts) > 1 else 1.0
        rps = total_reqs / span_s if span_s > 0 else 0.0

        run_records.append(
            {
                "backend": backend,
                "scale": scale,
                "users": users,
                "run": run,
                "mean_latency_ms": latencies.mean(),
                "p50_latency_ms": latencies.median(),
                "p95_latency_ms": latencies.quantile(0.95),
                "p99_latency_ms": latencies.quantile(0.99),
                "throughput_rps": rps,
                "error_rate_pct": error_rate,
                "total_requests": total_reqs,
            }
        )
    runs_df = pd.DataFrame(run_records)

    # Cross-run statistical aggregation with 95% Confidence Interval
    summary_rows = []
    for (scale, users), group in runs_df.groupby(["scale", "users"]):
        pg_sub = group[group["backend"] == "postgres"]
        mg_sub = group[group["backend"] == "mongo"]

        metrics = [
            "throughput_rps",
            "mean_latency_ms",
            "p50_latency_ms",
            "p95_latency_ms",
            "p99_latency_ms",
            "error_rate_pct",
        ]
        row: dict = {"scale": scale, "concurrency_users": users}

        for m in metrics:
            pg_mean, _, pg_ci = (
                compute_ci95(pg_sub[m]) if not pg_sub.empty else (np.nan, np.nan, np.nan)
            )
            mg_mean, _, mg_ci = (
                compute_ci95(mg_sub[m]) if not mg_sub.empty else (np.nan, np.nan, np.nan)
            )

            row[f"postgres_{m}"] = pg_mean
            row[f"postgres_{m}_ci95"] = pg_ci
            row[f"mongo_{m}"] = mg_mean
            row[f"mongo_{m}_ci95"] = mg_ci

            # Percentage difference: (Mongo - Postgres) / Postgres * 100
            diff = (
                ((mg_mean - pg_mean) / pg_mean) * 100
                if pd.notna(pg_mean) and pg_mean > 0 and pd.notna(mg_mean)
                else np.nan
            )
            row[f"diff_pct_{m}"] = diff

        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows).sort_values("concurrency_users")

    # Export to CSV
    summary_csv = results_dir / "summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    logger.info("Summary table written to %s", summary_csv)

    # Export to Markdown
    summary_md = results_dir / "summary.md"
    generate_markdown_report(summary_df, raw_df, res_df, summary_md)
    logger.info("Summary report written to %s", summary_md)

    return summary_df


def generate_markdown_report(
    summary_df: pd.DataFrame, raw_df: pd.DataFrame, res_df: pd.DataFrame, out_path: Path
):
    lines = [
        "# Benchmark Results Summary: PostgreSQL 16 vs MongoDB 7",
        "",
        "Empirical performance evaluation across identical e-commerce workloads under strict hardware and schema parity.",
        "",
        "## Overall Throughput and Latency Matrix (95% CI across runs)",
        "",
        "| Concurrency | Metric | PostgreSQL 16 | MongoDB 7 | % Difference (Mongo vs PG) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for _, row in summary_df.iterrows():
        u = int(row["concurrency_users"])
        # Throughput
        pg_rps = (
            f"{row['postgres_throughput_rps']:.1f} ± {row['postgres_throughput_rps_ci95']:.1f} rps"
            if pd.notna(row["postgres_throughput_rps"])
            else "N/A"
        )
        mg_rps = (
            f"{row['mongo_throughput_rps']:.1f} ± {row['mongo_throughput_rps_ci95']:.1f} rps"
            if pd.notna(row["mongo_throughput_rps"])
            else "N/A"
        )
        d_rps = (
            f"{row['diff_pct_throughput_rps']:+.1f}%"
            if pd.notna(row["diff_pct_throughput_rps"])
            else "N/A"
        )
        lines.append(f"| **{u} users** | **Throughput** | {pg_rps} | {mg_rps} | **{d_rps}** |")

        # p95 Latency
        pg_p95 = (
            f"{row['postgres_p95_latency_ms']:.2f} ± {row['postgres_p95_latency_ms_ci95']:.2f} ms"
            if pd.notna(row["postgres_p95_latency_ms"])
            else "N/A"
        )
        mg_p95 = (
            f"{row['mongo_p95_latency_ms']:.2f} ± {row['mongo_p95_latency_ms_ci95']:.2f} ms"
            if pd.notna(row["mongo_p95_latency_ms"])
            else "N/A"
        )
        d_p95 = (
            f"{row['diff_pct_p95_latency_ms']:+.1f}%"
            if pd.notna(row["diff_pct_p95_latency_ms"])
            else "N/A"
        )
        lines.append(f"| {u} users | p95 Latency | {pg_p95} | {mg_p95} | {d_p95} |")

        # p99 Latency
        pg_p99 = (
            f"{row['postgres_p99_latency_ms']:.2f} ± {row['postgres_p99_latency_ms_ci95']:.2f} ms"
            if pd.notna(row["postgres_p99_latency_ms"])
            else "N/A"
        )
        mg_p99 = (
            f"{row['mongo_p99_latency_ms']:.2f} ± {row['mongo_p99_latency_ms_ci95']:.2f} ms"
            if pd.notna(row["mongo_p99_latency_ms"])
            else "N/A"
        )
        d_p99 = (
            f"{row['diff_pct_p99_latency_ms']:+.1f}%"
            if pd.notna(row["diff_pct_p99_latency_ms"])
            else "N/A"
        )
        lines.append(f"| {u} users | p99 Latency | {pg_p99} | {mg_p99} | {d_p99} |")

    lines.extend(
        [
            "",
            "## Per-Endpoint Latency Comparison",
            "",
            "| Endpoint | PostgreSQL Mean (ms) | MongoDB Mean (ms) | % Difference |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )

    for ep, group in raw_df.groupby("endpoint"):
        pg_lat = group[group["backend"] == "postgres"]["latency_ms"].mean()
        mg_lat = group[group["backend"] == "mongo"]["latency_ms"].mean()
        diff = (
            ((mg_lat - pg_lat) / pg_lat) * 100
            if pd.notna(pg_lat) and pg_lat > 0 and pd.notna(mg_lat)
            else np.nan
        )

        pg_str = f"{pg_lat:.2f}" if pd.notna(pg_lat) else "N/A"
        mg_str = f"{mg_lat:.2f}" if pd.notna(mg_lat) else "N/A"
        d_str = f"{diff:+.1f}%" if pd.notna(diff) else "N/A"
        lines.append(f"| `{ep}` | {pg_str} | {mg_str} | {d_str} |")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def generate_figures(raw_df: pd.DataFrame, res_df: pd.DataFrame, figures_dir: Path):
    if raw_df.empty:
        logger.warning("Raw dataset empty; skipping figure generation.")
        return

    figures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Throughput vs Concurrency
    fig, ax = plt.subplots(figsize=(8, 5), dpi=200)
    for backend, color, marker in [("postgres", "#2563eb", "o"), ("mongo", "#16a34a", "s")]:
        sub = raw_df[raw_df["backend"] == backend]
        if sub.empty:
            continue
        users_list = []
        rps_list = []
        err_list = []
        for u, u_group in sub.groupby("users"):
            # Throughput per run
            run_rps = []
            for _, r_group in u_group.groupby("run"):
                ts = pd.to_datetime(r_group["timestamp"], errors="coerce").dropna()
                span = (ts.max() - ts.min()).total_seconds() if len(ts) > 1 else 1.0
                run_rps.append(len(r_group) / span if span > 0 else 0)
            mean_r, _, ci = compute_ci95(pd.Series(run_rps))
            users_list.append(u)
            rps_list.append(mean_r)
            err_list.append(ci)

        if users_list:
            ax.errorbar(
                users_list,
                rps_list,
                yerr=err_list,
                label=f"{backend.capitalize()} 16/7",
                color=color,
                marker=marker,
                linewidth=2,
                markersize=7,
                capsize=4,
            )

    ax.set_title("Throughput vs Concurrency (Requests/sec)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Concurrent Users", fontsize=11)
    ax.set_ylabel("Throughput (req/s)", fontsize=11)
    ax.legend(frameon=True, fontsize=10)
    plt.tight_layout()
    fig.savefig(figures_dir / "throughput_vs_concurrency.png")
    plt.close(fig)

    # 2. p95 and p99 Latency vs Concurrency
    fig, ax = plt.subplots(figsize=(8, 5), dpi=200)
    for backend, color, marker in [("postgres", "#2563eb", "o"), ("mongo", "#16a34a", "s")]:
        sub = raw_df[raw_df["backend"] == backend]
        if sub.empty:
            continue
        users_list = []
        p95_list = []
        err_list = []
        for u, u_group in sub.groupby("users"):
            p95s = [r_group["latency_ms"].quantile(0.95) for _, r_group in u_group.groupby("run")]
            mean_p95, _, ci = compute_ci95(pd.Series(p95s))
            users_list.append(u)
            p95_list.append(mean_p95)
            err_list.append(ci)

        if users_list:
            ax.errorbar(
                users_list,
                p95_list,
                yerr=err_list,
                label=f"{backend.capitalize()} p95",
                color=color,
                marker=marker,
                linewidth=2,
                markersize=7,
                capsize=4,
            )

    ax.set_title("Tail Latency (p95) vs Concurrency", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Concurrent Users", fontsize=11)
    ax.set_ylabel("Latency (ms)", fontsize=11)
    ax.legend(frameon=True, fontsize=10)
    plt.tight_layout()
    fig.savefig(figures_dir / "latency_p95_vs_concurrency.png")
    plt.close(fig)

    # 3. Bar Chart: Latency by Endpoint
    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    endpoints = sorted(raw_df["endpoint"].unique())
    x = np.arange(len(endpoints))
    width = 0.35

    pg_means = [
        raw_df[(raw_df["backend"] == "postgres") & (raw_df["endpoint"] == ep)]["latency_ms"].mean()
        for ep in endpoints
    ]
    mg_means = [
        raw_df[(raw_df["backend"] == "mongo") & (raw_df["endpoint"] == ep)]["latency_ms"].mean()
        for ep in endpoints
    ]

    ax.bar(x - width / 2, pg_means, width, label="PostgreSQL 16", color="#2563eb")
    ax.bar(x + width / 2, mg_means, width, label="MongoDB 7", color="#16a34a")

    ax.set_title("Mean Latency by Endpoint", fontsize=13, fontweight="bold", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(endpoints, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Mean Latency (ms)", fontsize=11)
    ax.legend(frameon=True, fontsize=10)
    plt.tight_layout()
    fig.savefig(figures_dir / "latency_by_endpoint.png")
    plt.close(fig)

    # 4. Resource Utilization (CPU & RAM)
    if not res_df.empty and "cpu_percent" in res_df.columns:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=200)

        # Average CPU by backend
        cpu_pg = res_df[res_df["backend"] == "postgres"]["cpu_percent"].dropna()
        cpu_mg = res_df[res_df["backend"] == "mongo"]["cpu_percent"].dropna()
        mem_pg = res_df[res_df["backend"] == "postgres"]["memory_mb"].dropna()
        mem_mg = res_df[res_df["backend"] == "mongo"]["memory_mb"].dropna()

        ax1.bar(
            ["PostgreSQL", "MongoDB"],
            [cpu_pg.mean() if not cpu_pg.empty else 0, cpu_mg.mean() if not cpu_mg.empty else 0],
            color=["#2563eb", "#16a34a"],
        )
        ax1.set_title("Database CPU Utilization (%)", fontsize=12, fontweight="bold")
        ax1.set_ylabel("Average CPU %")

        ax2.bar(
            ["PostgreSQL", "MongoDB"],
            [mem_pg.mean() if not mem_pg.empty else 0, mem_mg.mean() if not mem_mg.empty else 0],
            color=["#2563eb", "#16a34a"],
        )
        ax2.set_title("Database Memory Footprint (MB)", fontsize=12, fontweight="bold")
        ax2.set_ylabel("Average RAM (MB)")

        plt.tight_layout()
        fig.savefig(figures_dir / "resource_utilization.png")
        plt.close(fig)

    logger.info("High-resolution figures (200 dpi) exported to %s", figures_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Empirical Statistical Analysis & Figure Generator"
    )
    parser.add_argument(
        "--results-dir", default="results", help="Directory containing raw/ and resources/ CSVs"
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    raw_dir = results_dir / "raw"
    res_dir = results_dir / "resources"
    figures_dir = results_dir / "figures"

    raw_df = load_raw_dataset(raw_dir)
    res_df = load_resource_dataset(res_dir)

    if raw_df.empty:
        logger.warning(
            "No benchmark data found in %s. Run `python scripts/run_benchmark.py` first.", raw_dir
        )
        return

    generate_summary_tables(raw_df, res_df, results_dir)
    generate_figures(raw_df, res_df, figures_dir)


if __name__ == "__main__":
    main()
