"""PySig Studio local browser application.

Place beside ``main.py`` with the ``ui`` directory beside it and run::

    python pysig_ui.py

The application binds to 127.0.0.1 by default and uses only the Python standard
library plus PyYAML, which PySig already requires.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import shutil
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import yaml

ROOT = Path(__file__).resolve().parent
UI_DIR = ROOT / "ui"
CONFIG_DIR = ROOT / "configs"
DEFAULT_OUTPUT = ROOT / "results"
PDF_DIR = ROOT / ".pysig_pdf"
PDF_DIR.mkdir(exist_ok=True)
MAX_BODY = 8 * 1024 * 1024


def _default_config() -> Path | None:
    candidates = (
        CONFIG_DIR / "LM00389.yaml",
        CONFIG_DIR / "example_intersection_optimisation.yaml",
    )
    return next((p for p in candidates if p.exists()), None)


APP = {"config": _default_config(), "output": DEFAULT_OUTPUT}


class RunState:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.process = None
        self.return_code = None
        self.started_at = None
        self.finished_at = None
        self.command = []
        self.log = []

    def snapshot(self):
        with self.lock:
            elapsed = 0.0
            if self.started_at:
                elapsed = (self.finished_at or time.time()) - self.started_at
            return {
                "running": self.running,
                "return_code": self.return_code,
                "elapsed_s": round(elapsed, 2),
                "command": self.command,
                "log": "".join(self.log[-3000:]),
            }


RUN = RunState()


def safe_resolve(base: Path, relative: str) -> Path:
    base = base.resolve()
    candidate = (base / relative).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("Path is outside the permitted directory")
    return candidate


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def save_yaml(path: Path, data: dict) -> None:
    text = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    path.write_text(text, encoding="utf-8")


def model_summary(data: dict) -> dict:
    intersections = data.get("intersections") or []
    lanes = data.get("lanes") or []
    movements = data.get("movements") or []
    arms = [
        {**arm, "intersection_id": intersection.get("id")}
        for intersection in intersections
        for arm in (intersection.get("arms") or [])
    ]
    return {
        "id": (data.get("model") or {}).get("id", "Untitled"),
        "name": (data.get("model") or {}).get("name", "Untitled model"),
        "intersections": len(intersections),
        "arms": len(arms),
        "lanes": len(lanes),
        "movements": len(movements),
        "calculation_method": (data.get("calculation") or {}).get(
            "method", "simulation"
        ),
    }


def list_configs() -> list[str]:
    if not CONFIG_DIR.exists():
        return []
    return sorted(
        str(path.relative_to(CONFIG_DIR)).replace(os.sep, "/")
        for path in CONFIG_DIR.rglob("*.yaml")
    )


def pdf_slot_dir(slot: str) -> Path:
    if slot not in {"LMA", "LMB"}:
        raise ValueError("PDF slot must be LMA or LMB")
    path = PDF_DIR / slot
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_metadata(slot: str) -> dict:
    folder = pdf_slot_dir(slot)
    metadata_file = folder / "metadata.json"
    if not metadata_file.exists():
        return {"slot": slot, "loaded": False}
    return json.loads(metadata_file.read_text(encoding="utf-8"))


def _render_with_pymupdf(pdf_path: Path, folder: Path) -> int:
    """Render with optional PyMuPDF when it is installed."""
    try:
        import fitz
    except ImportError:
        return 0

    document = fitz.open(pdf_path)
    try:
        matrix = fitz.Matrix(2.0, 2.0)
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(folder / f"page-{index}.png")
        return len(document)
    finally:
        document.close()


def _render_with_poppler(pdf_path: Path, folder: Path) -> int:
    """Render with Poppler when pdfinfo/pdftoppm are available on PATH."""
    pdfinfo = shutil.which("pdfinfo")
    pdftoppm = shutil.which("pdftoppm")
    if not pdfinfo or not pdftoppm:
        return 0

    info = subprocess.run(
        [pdfinfo, str(pdf_path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    pages = 1
    for line in info.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split(":", 1)[1].strip())
            break

    subprocess.run(
        [
            pdftoppm,
            "-png",
            "-r",
            "144",
            str(pdf_path),
            str(folder / "rendered"),
        ],
        check=True,
        capture_output=True,
    )
    generated = sorted(folder.glob("rendered-*.png"))
    for index, image in enumerate(generated, start=1):
        image.rename(folder / f"page-{index}.png")
    return pages


def render_pdf_slot(slot: str, pdf_path: Path) -> dict:
    folder = pdf_slot_dir(slot)
    for image in folder.glob("page-*.png"):
        image.unlink()
    for image in folder.glob("rendered-*.png"):
        image.unlink()

    # Prefer PyMuPDF because it is cross-platform and does not require a
    # separate Poppler executable on Windows. Fall back to Poppler when present.
    pages = _render_with_pymupdf(pdf_path, folder)
    renderer = "PyMuPDF" if pages else None
    if not pages:
        pages = _render_with_poppler(pdf_path, folder)
        renderer = "Poppler" if pages else None

    if not pages:
        raise RuntimeError(
            "No PDF renderer is available. Install PyMuPDF in the PySig "
            "environment with 'conda install -c conda-forge pymupdf', or add "
            "Poppler's pdfinfo and pdftoppm commands to PATH."
        )

    metadata = {
        "slot": slot,
        "loaded": True,
        "filename": pdf_path.name,
        "pages": pages,
        "renderer": renderer,
        "scale_m_per_px": None,
    }
    (folder / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def update_pdf_metadata(slot: str, updates: dict) -> dict:
    metadata = pdf_metadata(slot)
    metadata.update(updates)
    (pdf_slot_dir(slot) / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def output_files() -> list[dict]:
    output = APP["output"]
    if not output.exists():
        return []
    return [
        {"name": p.name, "size": p.stat().st_size, "suffix": p.suffix.lower()}
        for p in sorted(output.iterdir())
        if p.is_file()
    ]


def start_run(mode: str):
    config = APP["config"]
    if config is None:
        raise RuntimeError("Save or open a model before running PySig")
    with RUN.lock:
        if RUN.running:
            raise RuntimeError("A PySig calculation is already running")
        APP["output"].mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(ROOT / "main.py"),
            mode,
            "--config",
            str(config),
            "--output",
            str(APP["output"]),
        ]
        RUN.running = True
        RUN.process = None
        RUN.return_code = None
        RUN.started_at = time.time()
        RUN.finished_at = None
        RUN.command = command
        RUN.log = ["PySig Studio\n", "Command: " + " ".join(command) + "\n\n"]

    def worker():
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
            with RUN.lock:
                RUN.process = process
            assert process.stdout is not None
            for line in process.stdout:
                with RUN.lock:
                    RUN.log.append(line)
            code = process.wait()
            with RUN.lock:
                RUN.return_code = code
                RUN.log.append(f"\nProcess finished with exit code {code}.\n")
        except Exception:
            with RUN.lock:
                RUN.return_code = -1
                RUN.log.append("\n" + traceback.format_exc())
        finally:
            with RUN.lock:
                RUN.running = False
                RUN.finished_at = time.time()
                RUN.process = None

    threading.Thread(target=worker, daemon=True, name="pysig-calculation").start()


class Handler(BaseHTTPRequestHandler):
    server_version = "PySigStudio/0.4.5"

    def log_message(self, fmt, *args):
        print("UI:", fmt % args)

    def json_response(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def request_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def static(self, filename):
        path = safe_resolve(UI_DIR, filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        raw = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            route = parsed.path
            query = parse_qs(parsed.query)
            static_routes = {
                "/": "index.html",
                "/pysig.css": "pysig.css",
                "/pysig.js": "pysig.js",
            }
            if route in static_routes:
                return self.static(static_routes[route])
            if route == "/api/configs":
                selected = None
                if APP["config"] and CONFIG_DIR in APP["config"].parents:
                    selected = str(APP["config"].relative_to(CONFIG_DIR)).replace(
                        os.sep, "/"
                    )
                return self.json_response(
                    {"configs": list_configs(), "selected": selected}
                )
            if route == "/api/model":
                if APP["config"] is None:
                    return self.json_response({"model": {}, "summary": {}})
                data = load_yaml(APP["config"])
                return self.json_response(
                    {
                        "model": data,
                        "summary": model_summary(data),
                        "filename": APP["config"].name,
                    }
                )
            if route == "/api/open":
                name = query.get("name", [""])[0]
                APP["config"] = safe_resolve(CONFIG_DIR, name)
                data = load_yaml(APP["config"])
                return self.json_response(
                    {"model": data, "summary": model_summary(data)}
                )
            if route == "/api/pdf/state":
                return self.json_response(
                    {"LMA": pdf_metadata("LMA"), "LMB": pdf_metadata("LMB")}
                )
            if route == "/api/pdf/page":
                slot = query.get("slot", ["LMA"])[0]
                page = int(query.get("page", ["1"])[0])
                path = pdf_slot_dir(slot) / f"page-{page}.png"
                if not path.is_file():
                    raise FileNotFoundError(path.name)
                raw = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
                return
            if route == "/api/run":
                return self.json_response(RUN.snapshot())
            if route == "/api/outputs":
                return self.json_response({"files": output_files()})
            if route == "/api/output":
                name = query.get("name", [""])[0]
                path = safe_resolve(APP["output"], name)
                if path.suffix.lower() == ".json":
                    return self.json_response(json.loads(path.read_text(encoding="utf-8")))
                return self.json_response(
                    {"text": path.read_text(encoding="utf-8", errors="replace")[:500000]}
                )
            if route == "/download":
                name = query.get("name", [""])[0]
                path = safe_resolve(APP["output"], name)
                raw = path.read_bytes()
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                )
                self.send_header(
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{quote(path.name)}",
                )
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            self.json_response({"error": "Not found"}, 404)
        except Exception as exc:
            self.json_response({"error": str(exc)}, 400)

    def do_POST(self):
        try:
            route = urlparse(self.path).path
            body = self.request_json()
            if route == "/api/pdf/upload":
                slot = str(body.get("slot", "LMA"))
                filename = Path(str(body.get("filename", f"{slot}.pdf"))).name
                encoded = str(body.get("data", ""))
                if encoded.startswith("data:"):
                    encoded = encoded.split(",", 1)[1]
                raw = base64.b64decode(encoded, validate=True)
                if not raw.startswith(b"%PDF"):
                    raise ValueError("Uploaded file is not a PDF")
                folder = pdf_slot_dir(slot)
                pdf_path = folder / filename
                pdf_path.write_bytes(raw)
                return self.json_response(render_pdf_slot(slot, pdf_path))
            if route == "/api/pdf/metadata":
                slot = str(body.get("slot", "LMA"))
                updates = {
                    key: body[key]
                    for key in ("scale_m_per_px", "calibration_distance_m")
                    if key in body
                }
                return self.json_response(update_pdf_metadata(slot, updates))
            if route == "/api/model":
                data = body.get("model")
                if not isinstance(data, dict):
                    raise ValueError("model must be an object")
                filename = body.get("filename")
                if filename:
                    if not filename.endswith(".yaml"):
                        filename += ".yaml"
                    APP["config"] = safe_resolve(CONFIG_DIR, filename)
                if APP["config"] is None:
                    raise ValueError("filename is required for a new model")
                APP["config"].parent.mkdir(parents=True, exist_ok=True)
                save_yaml(APP["config"], data)
                return self.json_response(
                    {
                        "saved": True,
                        "filename": APP["config"].name,
                        "summary": model_summary(data),
                    }
                )
            if route == "/api/validate":
                data = body.get("model")
                errors = []
                for intersection in data.get("intersections", []):
                    arm_ids = {a.get("id") for a in intersection.get("arms", [])}
                    for lane in data.get("lanes", []):
                        if lane.get("intersection_id") == intersection.get("id"):
                            if lane.get("arm_id") and lane.get("arm_id") not in arm_ids:
                                errors.append(
                                    f"Lane {lane.get('id')} references missing arm "
                                    f"{lane.get('arm_id')}"
                                )
                return self.json_response({"valid": not errors, "errors": errors})
            if route == "/api/run":
                mode = body.get("mode", "run")
                if mode not in {"run", "optimise"}:
                    raise ValueError("mode must be run or optimise")
                start_run(mode)
                return self.json_response({"started": True})
            if route == "/api/stop":
                with RUN.lock:
                    process = RUN.process
                if process and process.poll() is None:
                    process.terminate()
                    return self.json_response({"stopped": True})
                return self.json_response({"stopped": False})
            self.json_response({"error": "Not found"}, 404)
        except RuntimeError as exc:
            self.json_response({"error": str(exc)}, 409)
        except Exception as exc:
            self.json_response({"error": str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser(description="PySig Studio browser interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    required = [UI_DIR / "index.html", UI_DIR / "pysig.css", UI_DIR / "pysig.js"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        parser.error("Missing UI files: " + ", ".join(missing))

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"PySig Studio: {url}")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PySig Studio")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
