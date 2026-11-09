"""Preview parity, explicit lineage, and read-only HTTP trust boundaries."""
import json
import csv
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import numpy as np

from augmentation_pipeline import config_hash, transform, validate_config
from inspection_server import handler, optical_preview, preview, source_index


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "phytmo/inertial/upper"
        for segment, start in [("Larm", 12), ("Lforearm", 71)]:
            path = root / "A" / segment / "A01EFE0_1.csv"
            path.parent.mkdir(parents=True)
            sig = np.zeros((1800, 10))
            t = np.arange(len(sig)) / 100
            sig[:, 0] = t + start
            sig[:, 4] = .4 * np.sin(2 * np.pi * t / 2)
            sig[:, 6] = 1 + .3 * np.cos(2 * np.pi * t / 2)
            np.savetxt(path, sig, delimiter=",", header="time,gx,gy,gz,ax,ay,az,mx,my,mz", comments="")
        sources = source_index(root)
        name = "A/Larm/A01EFE0_1.csv"
        assert list(sources) == [name]
        config = validate_config({"orientation": {"max_degrees": 10}, "noise_std_g": .002})
        request = dict(source=name, config=config, seed=31)
        result = preview(root, sources, request)
        assert result == preview(root, sources, request)
        assert result["config"]["seed"] == result["seed"] == 31
        assert result["config_sha256"] == config_hash(result["config"])
        assert np.array_equal(result["augmented_g"], transform(np.asarray(result["original_g"]), config, 31))
        assert np.allclose(np.diff(result["time_s"]), .01)
        assert result["provenance"]["volunteer"] == "A01"
        assert result["provenance"]["series_label"] == 0
        assert result["provenance"]["counterpart"] == "A/Lforearm/A01EFE0_1.csv"
        assert "illustrative" in result["provenance"]["motion"]
        assert len(result["boundaries_s"]) > 0
        assert len(result["provenance"]["source_sha256"]) == 64
        assert len(result["transformation"]["orientation_matrices"]) == 2
        assert not result["optical"]["available"]
        optical = root.parent.parent / "optical interp/rigid_bodies/upper/A/A01EFE0_1_interp.csv"
        optical.parent.mkdir(parents=True)
        with optical.open("w") as handle:
            writer = csv.writer(handle)
            writer.writerows([["meta"], [], ["", "Type"] + ["Rigid Body"] * 14,
                              ["", "Name"] + ["thigh2"] * 7 + ["shin2"] * 7,
                              [], ["", ""] + (["Rotation"] * 4 + ["Position"] * 3) * 2,
                              ["Frame", "Time"] + ["X", "Y", "Z", "W", "X", "Y", "Z"] * 2])
            for i in range(50):
                body = [0, 0, 0, 1, 0, 1, 0] if i != 10 else [0] * 7
                writer.writerow([i, i / 100] + body * 2)
        poses = optical_preview(root, name, "L")
        assert poses["available"] and len(poses["time_s"]) == 10
        assert poses["boards"][0][2] is None
        assert poses["boards"][0][0]["position_m"] == [0., 1., 0.]
        json.dumps(poses, allow_nan=False)
        text = optical.read_text()
        optical.write_text(text.replace("1,0.01,", "1,0.02,"))
        assert not optical_preview(root, name, "L")["available"]
        optical.write_text(text)
        for bad in [{**request, "source": "../../etc/passwd"}, {**request, "seed": True},
                    {**request, "seed": -1}, {**request, "config": {"unknown": 1}},
                    {**request, "seed": 2**32}, {**request, "extra": 1}]:
            try:
                preview(root, sources, bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Accepted invalid preview: {bad}")
        server = HTTPServer(("127.0.0.1", 0), handler(root))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"

        def call(route, body=None, headers=None):
            payload = None if body is None else json.dumps(body).encode()
            req = urllib.request.Request(url + route, payload, headers={"Content-Type": "application/json", **(headers or {})})
            try:
                with urllib.request.urlopen(req) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as failure:
                return failure.code, failure.read()

        try:
            assert call("/")[0] == 200
            assert len(json.loads(call("/api/bootstrap")[1])["sources"]) == 1
            assert call("/api/preview", request)[0] == 200
            assert call("/api/preview", request, {"Origin": "http://unrelated.test"})[0] == 403
            assert call("/api/bootstrap", headers={"Host": "unrelated.test"})[0] == 403
            assert call("/api/preview", {**request, "seed": -1})[0] == 400
            assert call("/api/preview", request, {"Content-Type": "text/plain"})[0] == 400
            assert call("/api/preview", {"config": "x" * 17000})[0] == 400
            assert call("/../data/phytmo/inertial/upper/A/Larm/A01EFE0_1.csv")[0] == 404
            assert call("/api/unknown", request)[0] == 404
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    print("Inspection preview: exact Python transform parity, 100 Hz timing, seeded reproducibility, source/counterpart lineage and C-event markers passed")
    print("HTTP: read-only allowlist, source traversal, malformed configuration, size/type limits, loopback Host and cross-origin rejection passed")


if __name__ == "__main__":
    main()
