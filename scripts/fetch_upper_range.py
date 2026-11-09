"""Fetch only PHYTMO's inertial/upper ZIP members using verified HTTP ranges."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

URL = "https://zenodo.org/api/records/6319979/files/PHYTMO.zip/content"
PREFIX = "inertial/upper/"
RANGE_RE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
BLOCK = 8 * 1024 * 1024


def validate_range(status: int, content_range: str | None, body_length: int,
                   start: int, end: int, total: int | None = None) -> int:
    """Reject ignored, truncated, shifted, or inconsistent range responses."""
    m = RANGE_RE.fullmatch(content_range or "")
    if status != 206 or not m:
        raise ValueError(f"expected HTTP 206 with Content-Range; got {status}, {content_range!r}")
    got_start, got_end, got_total = map(int, m.groups())
    if (got_start, got_end) != (start, end) or body_length != end - start + 1:
        raise ValueError(f"range response mismatch: wanted {start}-{end}, got {got_start}-{got_end}, body={body_length}")
    if total is not None and total != got_total:
        raise ValueError(f"archive length changed: expected {total}, got {got_total}")
    return got_total


def safe_target(root: Path, member: str) -> Path:
    if "\\" in member:
        raise ValueError(f"unsafe ZIP member path: {member!r}")
    p = PurePosixPath(member)
    if p.is_absolute() or ".." in p.parts or not member.startswith(PREFIX):
        raise ValueError(f"unsafe or out-of-scope ZIP member path: {member!r}")
    target = root.joinpath(*p.parts[len(PurePosixPath(PREFIX).parts):]).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"ZIP member escapes destination: {member!r}")
    return target


class RangeReader:
    """Seekable read-only ZIP source backed by exact, cached HTTP range blocks."""
    def __init__(self, url: str, timeout: float = 40, retries: int = 3):
        self.url, self.timeout, self.retries = url, timeout, retries
        self.pos = 0
        self.downloaded = 0
        self.total = self._request(0, 63, None)[1]
        self.cache: OrderedDict[int, bytes] = OrderedDict()
        self.cached_blocks = 0

    def _request(self, start: int, end: int, total: int | None):
        last = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read(end - start + 2)
                    archive_size = validate_range(r.status, r.headers.get("Content-Range"), len(body), start, end, total)
                if len(body) != end - start + 1:
                    raise ValueError("server returned more bytes than requested")
                self.downloaded += len(body)
                return body, archive_size
            except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
                last = exc
                if attempt + 1 < self.retries:
                    time.sleep(1 + attempt)
        raise RuntimeError(f"Range request bytes={start}-{end} failed after {self.retries} attempts: {last}")

    def _block(self, index: int) -> bytes:
        if index in self.cache:
            self.cache.move_to_end(index)
            return self.cache[index]
        start = index * BLOCK
        end = min(start + BLOCK, self.total) - 1
        body, _ = self._request(start, end, self.total)
        self.cache[index] = body
        self.cached_blocks += 1
        while len(self.cache) > 4:
            self.cache.popitem(last=False)
        return body

    def seek(self, offset: int, whence: int = os.SEEK_SET):
        if whence == os.SEEK_SET:
            pos = offset
        elif whence == os.SEEK_CUR:
            pos = self.pos + offset
        elif whence == os.SEEK_END:
            pos = self.total + offset
        else:
            raise ValueError("invalid seek mode")
        if pos < 0:
            raise ValueError("negative seek")
        self.pos = pos
        return pos

    def tell(self):
        return self.pos

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self.total - self.pos
        size = min(size, max(0, self.total - self.pos))
        pieces = []
        while size:
            idx, within = divmod(self.pos, BLOCK)
            block = self._block(idx)
            take = min(size, len(block) - within)
            if take <= 0:
                break
            pieces.append(block[within:within + take])
            self.pos += take
            size -= take
        return b"".join(pieces)

    def readable(self): return True
    def seekable(self): return True


def self_check():
    assert validate_range(206, "bytes 0-3/10", 4, 0, 3) == 10
    for args in [(200, "bytes 0-3/10", 4, 0, 3),
                 (206, "bytes 1-3/10", 3, 0, 3),
                 (206, "bytes 0-3/10", 3, 0, 3),
                 (206, "bytes 0-3/11", 4, 0, 3, 10)]:
        try:
            validate_range(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid range response {args}")
    with __import__("tempfile").TemporaryDirectory() as d:
        root = Path(d)
        assert safe_target(root, PREFIX + "A/Larm/A01.csv") == root / "A/Larm/A01.csv"
        for name in ("../evil", "inertial/upper/../../evil", "inertial\\upper\\evil"):
            try:
                safe_target(root, name)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted unsafe ZIP path {name!r}")


def fetch(destination: Path):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination.parent / "fetch-upper-manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to replace existing completion manifest: {manifest_path}")
    reader = RangeReader(URL)
    with zipfile.ZipFile(reader) as zf:
        infos = [i for i in zf.infolist() if i.filename.startswith(PREFIX) and not i.is_dir()]
        if len(infos) != 1484:
            raise ValueError(f"expected 1484 upper-limb CSV/archive entries, found {len(infos)}")
        if any(i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for i in infos):
            raise ValueError("upper-limb archive uses an unsupported compression method")
        written = []
        for n, info in enumerate(infos, 1):
            target = safe_target(destination, info.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise FileExistsError(f"refusing to overwrite existing data: {target}")
            data = zf.read(info)  # Reading to EOF checks the ZIP member CRC.
            if len(data) != info.file_size:
                raise ValueError(f"uncompressed size mismatch for {info.filename}")
            with target.open("xb") as out:
                out.write(data)
            written.append({"member": info.filename, "bytes": len(data), "crc32": f"{info.CRC:08x}"})
            if n % 100 == 0 or n == len(infos):
                print(f"verified {n}/{len(infos)} upper-limb files", flush=True)
    summary = {
        "source_url": URL,
        "dataset": "PHYTMO, Zenodo record 6319979; doi 10.5281/zenodo.6319979; CC-BY-4.0",
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "archive_bytes": reader.total,
        "http_range_bytes_transferred": reader.downloaded,
        "http_range_blocks_fetched": reader.cached_blocks,
        "verified_file_count": len(written),
        "verified_uncompressed_bytes": sum(x["bytes"] for x in written),
        "crc_validation": "zipfile read each member to EOF; CRC checked by Python zipfile",
        "files": written,
    }
    manifest_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"verified {len(written)} files; transferred {reader.downloaded:,} bytes in {reader.cached_blocks} range blocks")
    print(f"saved under {destination.parent}; provenance: {manifest_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("data/phytmo/inertial/upper"))
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    self_check()
    print("range/path self-check passed", flush=True)
    if not args.self_check:
        fetch(args.out)


if __name__ == "__main__":
    main()
