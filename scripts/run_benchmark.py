import argparse
import json
import logging
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil

from loadtest.sampler import ResourceSampler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")


def collect_environment_metadata(results_dir: Path) -> dict:
    meta = {
        "timestamp": datetime.now(UTC).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "hardware": {
            "cpu_physical_cores": psutil.cpu_count(logical=False),
            "cpu_logical_cores": psutil.cpu_count(logical=True),
            "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        },
        "python": {
            "version": sys.version,
            "executable": sys.executable,
        },
    }

    # Query Docker info if docker is running
    try:
        res = subprocess.run(
            ["docker", "version", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if res.returncode == 0:
            meta["docker"] = json.loads(res.stdout)
    except Exception:
        meta["docker"] = "Docker daemon not reachable"

    out_file = results_dir / "environment.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    logger.info("Environment metadata logged to %s", out_file)
    return meta


class BenchmarkOrchestrator:
    def __init__(
        self,
        backends: list[str],
        concurrency_levels: list[int],
        runs_per_level: int,
        warmup_seconds: int,
        duration_seconds: int,
        scale: str,
        results_dir: Path,
        app_host: str = "http://localhost:8000",
    ):
        self.backends = backends
        self.concurrency_levels = concurrency_levels
        self.runs_per_level = runs_per_level
        self.warmup_seconds = warmup_seconds
        self.duration_seconds = duration_seconds
        self.scale = scale
        self.results_dir = results_dir
        self.app_host = app_host

        self.raw_dir = results_dir / "raw"
        self.res_dir = results_dir / "resources"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.res_dir.mkdir(parents=True, exist_ok=True)

    def run_matrix(self):
        logger.info("================================================================")
        logger.info("STARTING BENCHMARK MATRIX")
        logger.info("Backends: %s", self.backends)
        logger.info("Concurrency Levels: %s", self.concurrency_levels)
        logger.info(
            "Runs per level: %d | Warmup: %ds | Measured: %ds",
            self.runs_per_level,
            self.warmup_seconds,
            self.duration_seconds,
        )
        logger.info("================================================================")

        for run_idx in range(1, self.runs_per_level + 1):
            # Alternating backend order to eliminate bias
            current_backends = list(self.backends)
            if run_idx % 2 == 0:
                current_backends.reverse()

            for backend in current_backends:
                for users in self.concurrency_levels:
                    self._execute_single_run(backend=backend, users=users, run_idx=run_idx)

        logger.info("All benchmark runs completed successfully.")

    def _execute_single_run(self, backend: str, users: int, run_idx: int):
        logger.info(
            "--- Running test: backend=%s | users=%d | run=%d/%d ---",
            backend,
            users,
            run_idx,
            self.runs_per_level,
        )

        raw_csv = self.raw_dir / f"{backend}_{self.scale}_u{users}_run{run_idx}.csv"
        resource_csv = self.res_dir / f"{backend}_{self.scale}_u{users}_run{run_idx}.csv"

        # Determine target container name for resource sampling
        target_container = "benchmark_postgres" if backend == "postgres" else "benchmark_mongo"

        sampler = ResourceSampler(
            target_name=target_container, output_csv=resource_csv, interval=1.0
        )
        sampler.start()

        total_run_time = self.warmup_seconds + self.duration_seconds
        now_ts = datetime.now(UTC).timestamp()
        warmup_until = now_ts + self.warmup_seconds

        # Spawn rate: 10% of total users per second, min 2/sec
        spawn_rate = max(2, int(users * 0.2))

        locust_env = os.environ.copy()
        locust_env["BENCH_BACKEND"] = backend
        locust_env["BENCH_SCALE"] = self.scale
        locust_env["BENCH_USERS"] = str(users)
        locust_env["BENCH_RUN"] = str(run_idx)
        locust_env["RAW_CSV_PATH"] = str(raw_csv)
        locust_env["WARMUP_UNTIL"] = str(warmup_until)

        cmd = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            "loadtest/locustfile.py",
            "--headless",
            "--users",
            str(users),
            "--spawn-rate",
            str(spawn_rate),
            "--run-time",
            f"{total_run_time}s",
            "--host",
            self.app_host,
            "--only-summary",
        ]

        logger.info(
            "Starting Locust execution (%ds total: %ds warmup + %ds measurement)...",
            total_run_time,
            self.warmup_seconds,
            self.duration_seconds,
        )
        try:
            res = subprocess.run(cmd, env=locust_env, capture_output=True, text=True)
            if res.returncode != 0:
                logger.warning(
                    "Locust returned non-zero code: %d\nStderr: %s", res.returncode, res.stderr
                )
        except Exception as e:
            logger.error("Failed executing Locust: %s", e)
        finally:
            sampler.stop()

        logger.info("Run finished. Raw data written to: %s", raw_csv)


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrator for MongoDB vs PostgreSQL Research Benchmark"
    )
    parser.add_argument("--backends", nargs="+", default=["postgres", "mongo"])
    parser.add_argument("--concurrency", nargs="+", type=int, default=[10, 50, 100, 500])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--warmup", type=int, default=60, help="Warmup duration in seconds (discarded)"
    )
    parser.add_argument("--duration", type=int, default=300, help="Measured duration in seconds")
    parser.add_argument("--scale", choices=["test", "small", "medium", "large"], default="small")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode for testing: concurrency=[10, 20], runs=1, duration=10s, warmup=2s",
    )
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--results-dir", default="results")

    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    # Collect host environment snapshot
    collect_environment_metadata(results_dir)

    concurrency = args.concurrency
    runs = args.runs
    warmup = args.warmup
    duration = args.duration

    if args.quick:
        concurrency = [10, 20]
        runs = 1
        warmup = 2
        duration = 10
        logger.info("Running in QUICK mode for validation.")

    orchestrator = BenchmarkOrchestrator(
        backends=args.backends,
        concurrency_levels=concurrency,
        runs_per_level=runs,
        warmup_seconds=warmup,
        duration_seconds=duration,
        scale=args.scale,
        results_dir=results_dir,
        app_host=args.host,
    )
    orchestrator.run_matrix()


if __name__ == "__main__":
    main()
