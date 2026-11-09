"""Local, read-only recording inspection; preview uses the real augmentation implementation."""
from __future__ import annotations

import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np

from harness import parse_name, read_inertial
from paired_pipeline import aligned_pair
from streaming_pipeline import StreamExtractor

ROOT = Path(__file__).resolve().parents[1]


def source_index(root):
    result = {}
    for side in "LR":
        for path in sorted(root.glob(f"*/{side}arm/*.csv")):
            meta = parse_name(str(path))
            counterpart = path.parent.parent / f"{side}forearm" / path.name
            if meta and meta[1] in {"EAH", "EFE", "SQZ"} and counterpart.is_file():
                name = path.relative_to(root).as_posix()
                result[name] = dict(source=name, volunteer=meta[0], exercise=meta[1],
                                    series_label=meta[3], side=side)
    return result


def optical_preview(root, name, side):
    """Board poses only; no optical/IMU alignment or anatomical angle inference."""
    from placement_replay import read_board

    parts = Path(name).parts
    path = root.parent.parent / "optical interp/rigid_bodies/upper" / parts[0] / parts[-1].replace(".csv", "_interp.csv")
    if not path.is_file():
        return {"available": False, "reason": "Matching optical board recording is not in the local subset"}
    try:
        time, boards = read_board(path, side)
        if len(time) < 2 or not np.isfinite(time).all() or not np.allclose(np.diff(time), .01, atol=1e-5):
            raise ValueError("Optical preview requires finite regular 100 Hz source poses")
        selection = np.arange(0, len(time), 5)
        result = []
        for quaternion, position, valid in boards:
            result.append([{"quaternion_xyzw": quaternion[i].tolist(), "position_m": position[i].tolist()}
                           if valid[i] else None for i in selection])
        return dict(available=True, time_s=(time[selection] - time[0]).tolist(), boards=result,
                    source=str(path.relative_to(root.parent.parent)),
                    source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    status="Measured optical board poses at 20 Hz preview; clock unaligned to IMU; segment axes/lengths assumed")
    except (ValueError, OSError) as error:
        return {"available": False, "reason": str(error)}


def preview(root, sources, request):
    from augmentation_pipeline import config_hash, transform_with_provenance, validate_config

    if not isinstance(request, dict) or set(request) - {"source", "config", "seed"}:
        raise ValueError("Expected source, config and seed fields")
    name = request.get("source")
    if not isinstance(name, str) or name not in sources:
        raise ValueError("Choose a listed paired source recording")
    seed = request.get("seed", 0)
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Seed must be an integer in [0, 4294967295]")
    config = validate_config(request.get("config", {}))
    config["seed"] = seed
    path = root / name
    counterpart = path.parent.parent / (sources[name]["side"] + "forearm") / path.name
    original = aligned_pair(read_inertial(str(path)), read_inertial(str(counterpart)))
    changed, parameters = transform_with_provenance(original, config, seed)
    with StreamExtractor() as extractor:
        extractor(np.clip(original, -3, 3))
        boundaries = (extractor.ends / 100).tolist()
        extractor(np.clip(changed, -3, 3))
        changed_boundaries = (extractor.ends / 100).tolist()
    return dict(time_s=(np.arange(len(original)) / 100).tolist(),
                original_g=original.tolist(), augmented_g=changed.tolist(),
                boundaries_s=boundaries, augmented_boundaries_s=changed_boundaries,
                config=config, seed=seed, transformation=parameters,
                optical=optical_preview(root, name, sources[name]["side"]),
                config_sha256=config_hash(config),
                provenance={**sources[name], "kind": "transformed measured recording",
                            "label_origin": "PHYTMO whole-series label inherited; no repetition truth",
                            "counterpart": counterpart.relative_to(root).as_posix(),
                            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "counterpart_sha256": hashlib.sha256(counterpart.read_bytes()).hexdigest(),
                            "validation_status": "mathematical preview; physical ADXL335 transfer unvalidated",
                            "timing": "record-relative 100 Hz interpolation; residual cross-device alignment unverified",
                            "motion": "illustrative animation; no measured joint angles or calibrated geometry"})


def handler(root):
    sources = source_index(root)

    class Handler(BaseHTTPRequestHandler):
        def trusted_host(self):
            port = self.server.server_port
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def respond(self, status, data, content_type="application/json"):
            body = (json.dumps(data, allow_nan=False).encode() if content_type == "application/json"
                    else data)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.trusted_host():
                self.respond(403, {"error": "Use the loopback URL printed by the server"})
                return
            route = urlsplit(self.path).path
            if route == "/api/bootstrap":
                placements = json.loads((ROOT / "simulation/placements.json").read_text())
                config = json.loads((ROOT / "configs/augmentation-example.json").read_text())
                self.respond(200, dict(sources=list(sources.values()), placements=placements, config=config))
            elif route in {"/", "/inspection.js", "/inspection.css"}:
                file = "index.html" if route == "/" else route[1:]
                mime = {"index.html": "text/html; charset=utf-8", "inspection.js": "text/javascript; charset=utf-8",
                        "inspection.css": "text/css; charset=utf-8"}[file]
                self.respond(200, (ROOT / "tools/inspection" / file).read_bytes(), mime)
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if not self.trusted_host():
                self.respond(403, {"error": "Use the loopback URL printed by the server"})
                return
            if self.path != "/api/preview":
                self.respond(404, {"error": "Not found"})
                return
            # This service binds loopback and allows only same-origin JSON previews.
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                self.respond(403, {"error": "Cross-origin previews are unavailable"})
                return
            try:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("Expected Content-Type application/json")
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16384:
                    raise ValueError("Expected a JSON request of at most 16 KiB")
                request = json.loads(self.rfile.read(size))
                self.respond(200, preview(root, sources, request))
            except (ValueError, TypeError, OSError, KeyError) as error:
                self.respond(400, {"error": str(error)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/phytmo/inertial/upper")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error("Raw upper-limb dataset is unavailable; see docs/MODELLING-ENVIRONMENT.md")
    server = HTTPServer(("127.0.0.1", args.port), handler(args.root))
    print(f"Inspection tool: http://127.0.0.1:{server.server_port} (Ctrl-C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
