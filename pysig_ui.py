"""PySig local browser UI.

Place this file beside main.py, with the ui/ directory beside it, then run:

    python pysig_ui.py

No web framework is required. The server binds to 127.0.0.1 by default.
"""
from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required. Install it with Conda before running the UI."
    ) from exc

ROOT = Path(__file__).resolve().parent
UI_DIR = ROOT / "ui"
CONFIG_DIR = ROOT / "configs"
DEFAULT_CONFIG = CONFIG_DIR / "example_intersection_optimisation.yaml"
DEFAULT_OUTPUT = ROOT / "results"
MAX_REQUEST_BYTES = 4 * 1024 * 1024


@dataclass
class RunState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    running: bool = False
    command: list[str] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None
    return_code: int | None = None
    log: list[str] = field(default_factory=list)
    process: subprocess.Popen | None = None

    def snapshot(self) -> dict:
        with self.lock:
            elapsed = 0.0
            if self.started_at:
                elapsed = (self.finished_at or time.time()) - self.started_at
            return {
                "running": self.running,
                "command": self.command,
                "return_code": self.return_code,
                "elapsed_s": round(elapsed, 2),
                "log": "".join(self.log[-3000:]),
            }


STATE = RunState()
APP = {"config": DEFAULT_CONFIG, "output": DEFAULT_OUTPUT}


def safe_resolve(base: Path, relative_name: str) -> Path:
    """Resolve a user-selected file while preventing directory traversal."""
    candidate = (base / relative_name).resolve()
    resolved_base = base.resolve()
    if candidate != resolved_base and resolved_base not in candidate.parents:
        raise ValueError("Path is outside the permitted directory")
    return candidate


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_model_yaml() -> dict:
    data = yaml.safe_load(read_text(APP["config"]))
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def model_summary(data: dict) -> dict:
    intersections = data.get("intersections") or []
    lanes = data.get("lanes") or []
    movements = data.get("movements") or []
    links = data.get("network_links") or []
    controllers = data.get("controllers") or (
        [data["controller"]] if data.get("controller") else []
    )
    routes = data.get("routes") or []
    od_values = (data.get("origin_destination_matrix") or {}).get("values") or {}
    od_total = sum(
        float(value)
        for row in od_values.values()
        if isinstance(row, dict)
        for value in row.values()
    )

    default_intersection = intersections[0].get("id", "I1") if intersections else "I1"
    lane_by_id = {lane.get("id"): lane for lane in lanes}
    enriched_movements = []
    for movement in movements:
        lane = lane_by_id.get(movement.get("from_lane_id"), {})
        enriched_movements.append(
            {
                **movement,
                "intersection_id": movement.get("intersection_id")
                or lane.get("intersection_id")
                or default_intersection,
            }
        )

    if not intersections and movements:
        intersections = [
            {
                "id": default_intersection,
                "controller_id": controllers[0].get("id", "C1")
                if controllers
                else "C1",
                "movement_ids": [movement.get("id") for movement in movements],
            }
        ]

    return {
        "model": data.get("model", {}),
        "run": data.get("run", {}),
        "settings": data.get("settings", {}),
        "intersections": intersections,
        "lanes": lanes,
        "movements": enriched_movements,
        "links": links,
        "controllers": controllers,
        "phases": data.get("phases") or [],
        "routes": routes,
        "od_total": od_total,
        "assignment": data.get("assignment", {}),
        "network": data.get("network", {}),
        "optimisation": data.get("optimisation", {}),
    }


def list_outputs() -> list[dict]:
    output_dir = APP["output"]
    if not output_dir.exists():
        return []
    rows = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name.lower()):
        if path.is_file():
            stat = path.stat()
            rows.append(
                {
                    "name": path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "kind": path.suffix.lower().lstrip(".") or "file",
                }
            )
    return rows


def preview_output(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return {"type": "json", "data": json.loads(read_text(path))}
    if suffix in {".yaml", ".yml"}:
        return {"type": "yaml", "text": read_text(path)}
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        return {"type": "csv", "rows": rows[:501], "truncated": len(rows) > 501}
    try:
        return {"type": "text", "text": read_text(path)[:500_000]}
    except UnicodeDecodeError:
        return {"type": "binary", "size": path.stat().st_size}


def start_model_run(mode: str) -> None:
    with STATE.lock:
        if STATE.running:
            raise RuntimeError("A PySig run is already in progress")
        APP["output"].mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(ROOT / "main.py"),
            mode,
            "--config",
            str(APP["config"]),
            "--output",
            str(APP["output"]),
        ]
        STATE.running = True
        STATE.command = command
        STATE.started_at = time.time()
        STATE.finished_at = None
        STATE.return_code = None
        STATE.log = ["PySig UI\n", f"Command: {' '.join(command)}\n\n"]
        STATE.process = None

    def worker() -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            with STATE.lock:
                STATE.process = process
            assert process.stdout is not None
            for line in process.stdout:
                with STATE.lock:
                    STATE.log.append(line)
                    if len(STATE.log) > 5000:
                        STATE.log = STATE.log[-4000:]
            return_code = process.wait()
            with STATE.lock:
                STATE.return_code = return_code
                STATE.log.append(f"\nProcess finished with exit code {return_code}.\n")
        except Exception:
            with STATE.lock:
                STATE.return_code = -1
                STATE.log.append("\n" + traceback.format_exc())
        finally:
            with STATE.lock:
                STATE.running = False
                STATE.finished_at = time.time()
                STATE.process = None

    threading.Thread(target=worker, name="pysig-runner", daemon=True).start()


def stop_model_run() -> bool:
    with STATE.lock:
        process = STATE.process
    if process and process.poll() is None:
        process.terminate()
        return True
    return False


class Handler(BaseHTTPRequestHandler):
    server_version = "PySigStudio/0.4.3"

    def log_message(self, format_string: str, *args) -> None:
        print("UI:", format_string % args)

    def send_json(self, data, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def send_static(self, filename: str) -> None:
        path = safe_resolve(UI_DIR, filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        raw = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_REQUEST_BYTES:
            raise ValueError("Request is too large")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            static_routes = {
                "/": "index.html",
                "/pysig.css": "pysig.css",
                "/pysig.js": "pysig.js",
            }
            if path in static_routes:
                self.send_static(static_routes[path])
                return

            if path == "/api/state":
                self.send_json(
                    {
                        "config": str(APP["config"].relative_to(ROOT)),
                        "output": str(APP["output"].relative_to(ROOT)),
                        "model": model_summary(load_model_yaml()),
                    }
                )
                return

            if path == "/api/configs":
                configs = sorted(
                    str(item.relative_to(CONFIG_DIR)).replace(os.sep, "/")
                    for item in CONFIG_DIR.rglob("*.yaml")
                )
                selected = str(APP["config"].relative_to(CONFIG_DIR)).replace(
                    os.sep, "/"
                )
                self.send_json({"configs": configs, "selected": selected})
                return

            if path == "/api/config":
                default_name = str(APP["config"].relative_to(CONFIG_DIR))
                name = query.get("name", [default_name])[0]
                APP["config"] = safe_resolve(CONFIG_DIR, name)
                self.send_json({"name": name, "text": read_text(APP["config"])})
                return

            if path == "/api/run":
                self.send_json(STATE.snapshot())
                return

            if path == "/api/outputs":
                self.send_json({"files": list_outputs()})
                return

            if path in {"/api/output", "/download"}:
                name = query.get("name", [""])[0]
                file_path = safe_resolve(APP["output"], name)
                if not file_path.is_file():
                    raise FileNotFoundError(name)
                if path == "/api/output":
                    self.send_json(preview_output(file_path))
                    return
                raw = file_path.read_bytes()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    mimetypes.guess_type(file_path.name)[0]
                    or "application/octet-stream",
                )
                self.send_header(
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{quote(file_path.name)}",
                )
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            self.send_json({"error": "Not found"}, 404)
        except FileNotFoundError as exc:
            self.send_json({"error": f"File not found: {exc}"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path

            if path == "/api/config":
                body = self.read_json()
                target = safe_resolve(CONFIG_DIR, body.get("name", ""))
                text = body.get("text", "")
                data = yaml.safe_load(text)
                if not isinstance(data, dict):
                    raise ValueError("YAML root must be a mapping")
                target.write_text(text, encoding="utf-8")
                APP["config"] = target
                self.send_json({"saved": True, "name": target.name})
                return

            if path == "/api/validate":
                data = yaml.safe_load(self.read_json().get("text", ""))
                if not isinstance(data, dict):
                    raise ValueError("YAML root must be a mapping")
                self.send_json(
                    {
                        "valid": True,
                        "intersections": len(data.get("intersections") or [1]),
                    }
                )
                return

            if path == "/api/run":
                mode = self.read_json().get("mode", "optimise")
                if mode not in {"run", "optimise"}:
                    raise ValueError("Mode must be run or optimise")
                start_model_run(mode)
                self.send_json({"started": True, "mode": mode})
                return

            if path == "/api/stop":
                self.send_json({"stopped": stop_model_run()})
                return

            self.send_json({"error": "Not found"}, 404)
        except RuntimeError as exc:
            self.send_json({"error": str(exc)}, 409)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)


def main() -> int:
    parser = argparse.ArgumentParser(description="PySig local browser UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    APP["config"] = args.config.resolve()
    APP["output"] = args.output.resolve()

    required_files = [UI_DIR / "index.html", UI_DIR / "pysig.css", UI_DIR / "pysig.js"]
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        parser.error("Missing UI file(s): " + ", ".join(missing))
    if not APP["config"].is_file():
        parser.error(f"Config not found: {APP['config']}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"PySig Studio is running at {url}")
    print("Press Ctrl+C to stop the server.")

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PySig Studio...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
