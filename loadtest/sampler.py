import logging
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

logger = logging.getLogger("sampler")


class ResourceSampler:
    """
    Background resource monitor that samples CPU % and Memory (MB)
    every 1 second for a target database container or process.
    """

    def __init__(self, target_name: str, output_csv: Path, interval: float = 1.0):
        self.target_name = target_name
        self.output_csv = Path(output_csv)
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._samples: list[dict] = []

    def start(self) -> None:
        self._stop_event.clear()
        self._samples.clear()
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True, name="ResourceSampler")
        self._thread.start()
        logger.info(
            "Resource sampler started for target '%s' -> %s", self.target_name, self.output_csv
        )

    def stop(self) -> None:
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=5.0)
        self._flush_to_file()
        logger.info("Resource sampler stopped. Collected %d samples.", len(self._samples))

    def _run(self) -> None:
        while not self._stop_event.is_set():
            sample = self._collect_sample()
            if sample:
                self._samples.append(sample)
            time.sleep(self.interval)

    def _collect_sample(self) -> dict | None:
        now_iso = datetime.now(UTC).isoformat()

        # 1. Attempt Docker stats first
        docker_sample = self._sample_docker()
        if docker_sample:
            return {
                "timestamp": now_iso,
                "target": self.target_name,
                "cpu_percent": docker_sample["cpu_percent"],
                "memory_mb": docker_sample["memory_mb"],
            }

        # 2. Attempt psutil process matching
        proc_sample = self._sample_process()
        if proc_sample:
            return {
                "timestamp": now_iso,
                "target": self.target_name,
                "cpu_percent": proc_sample["cpu_percent"],
                "memory_mb": proc_sample["memory_mb"],
            }

        # 3. Fallback to system-level metrics
        return {
            "timestamp": now_iso,
            "target": f"{self.target_name}_system",
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_mb": round(psutil.virtual_memory().used / (1024 * 1024), 2),
        }

    def _sample_docker(self) -> dict | None:
        try:
            cmd = [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}},{{.CPUPerc}},{{.MemUsage}}",
                self.target_name,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split(",")
                if len(parts) >= 3:
                    cpu_str = parts[1].replace("%", "").strip()
                    cpu = float(cpu_str) if cpu_str else 0.0

                    mem_usage_str = parts[2].split("/")[0].strip()
                    mem_mb = self._parse_memory_mb(mem_usage_str)
                    return {"cpu_percent": cpu, "memory_mb": mem_mb}
        except Exception:
            pass
        return None

    def _sample_process(self) -> dict | None:
        try:
            target_lower = self.target_name.lower()
            matching_procs = []
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    pname = (proc.info["name"] or "").lower()
                    if (
                        target_lower in pname
                        or ("postgres" in target_lower and "postgres" in pname)
                        or ("mongo" in target_lower and "mongo" in pname)
                    ):
                        matching_procs.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if matching_procs:
                total_cpu = sum(p.cpu_percent(interval=None) for p in matching_procs)
                total_mem = sum(p.memory_info().rss for p in matching_procs) / (1024 * 1024)
                return {"cpu_percent": round(total_cpu, 2), "memory_mb": round(total_mem, 2)}
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_memory_mb(mem_str: str) -> float:
        mem_str = mem_str.strip().upper()
        try:
            if "GIB" in mem_str or "GB" in mem_str:
                num = float(mem_str.replace("GIB", "").replace("GB", "").strip())
                return round(num * 1024.0, 2)
            elif "MIB" in mem_str or "MB" in mem_str:
                num = float(mem_str.replace("MIB", "").replace("MB", "").strip())
                return round(num, 2)
            elif "KIB" in mem_str or "KB" in mem_str:
                num = float(mem_str.replace("KIB", "").replace("KB", "").strip())
                return round(num / 1024.0, 2)
            elif "B" in mem_str:
                num = float(mem_str.replace("B", "").strip())
                return round(num / (1024.0 * 1024.0), 2)
        except ValueError:
            pass
        return 0.0

    def _flush_to_file(self) -> None:
        if not self._samples:
            return
        with open(self.output_csv, "w", encoding="utf-8") as f:
            f.write("timestamp,target,cpu_percent,memory_mb\n")
            for s in self._samples:
                f.write(f"{s['timestamp']},{s['target']},{s['cpu_percent']},{s['memory_mb']}\n")
