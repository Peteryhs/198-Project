"""Inventory and selectively CRC-check PHYTMO upper optical reference files."""
from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

from fetch_upper_range import RangeReader, URL

PATTERN = re.compile(
    r"^optical (raw|interp)/rigid_bodies/upper/([A-E])/([A-E]\d{1,2})(EAH|EFE|SQZ)([01])_([12])(?:_interp)?\.csv$"
)
CALIB_PATTERN = re.compile(r"^optical (raw|interp)/rigid_bodies/upper/([A-E])/([A-E]\d{1,2})Calib(?:_interp)?\.csv$")
ROOT = Path("data/phytmo")
LIMIT = 1_000_000_000


def candidates(infos, kind):
    found = []
    for info in infos:
        m = PATTERN.fullmatch(info.filename)
        if m and m[1] == kind:
            found.append((info, m))
    # One first-series file per person/exercise/quality; independent from side.
    return [item for item in found if item[1][6] == "1"]


def normalized_person(person: str) -> str:
    return person[0] + f"{int(person[1:]):02d}"


def inventory():
    reader = RangeReader(URL)
    with zipfile.ZipFile(reader) as zf:
        infos = zf.infolist()
        report = {
            "source_url": URL,
            "dataset": "PHYTMO, Zenodo record 6319979, DOI 10.5281/zenodo.6319979, CC-BY-4.0",
            "archive_bytes": reader.total,
            "catalogue_range_bytes": reader.downloaded,
            "catalogue_range_blocks": reader.cached_blocks,
            "archive_members": len(infos),
            "categories": {},
        }
        for kind in ("raw", "interp"):
            all_files = [i for i in infos if i.filename.startswith(f"optical {kind}/rigid_bodies/upper/") and not i.is_dir()]
            selected = candidates(infos, kind)
            paired = []
            for info, m in selected:
                group, exercise, quality, series = m[2], m[4], m[5], m[6]
                person = normalized_person(m[3])
                # The optical name contains no side; matching available board data is checked below.
                base = f"{person}{exercise}{quality}_{series}.csv"
                arms = [p for p in (ROOT / "inertial/upper" / group).glob(f"*arm/{base}")]
                if arms:
                    paired.append((info, m, [str(p) for p in arms]))
            report["categories"][kind] = {
                "upper_rigid_body_file_count": len(all_files),
                "upper_rigid_body_uncompressed_bytes": sum(i.file_size for i in all_files),
                "upper_rigid_body_compressed_bytes": sum(i.compress_size for i in all_files),
                "first_series_person_exercise_quality_count": len(selected),
                "first_series_uncompressed_bytes": sum(i.file_size for i, _ in selected),
                "first_series_compressed_bytes": sum(i.compress_size for i, _ in selected),
                "first_series_with_local_inertial_counterpart_count": len(paired),
                "first_series_with_local_inertial_counterpart_uncompressed_bytes": sum(i.file_size for i, _, _ in paired),
                "first_series_with_local_inertial_counterpart_compressed_bytes": sum(i.compress_size for i, _, _ in paired),
                "first_series_with_local_inertial_counterpart_members": [
                    {"member": i.filename, "bytes": i.file_size, "compressed_bytes": i.compress_size,
                     "crc32": f"{i.CRC:08x}", "normalized_person": normalized_person(m[3]),
                     "inertial_paths": paths}
                    for i, m, paths in paired
                ],
            }
            calibration = []
            for i in infos:
                m = CALIB_PATTERN.fullmatch(i.filename)
                if not m or m[1] != kind:
                    continue
                person = normalized_person(m[3])
                paths = sorted(str(p) for p in (ROOT / "inertial/upper" / m[2]).glob(f"*arm/{person}Calib.csv"))
                calibration.append({"member": i.filename, "bytes": i.file_size,
                                    "compressed_bytes": i.compress_size, "crc32": f"{i.CRC:08x}",
                                    "normalized_person": person, "inertial_paths": paths})
            report.setdefault("upper_calibration", {})[kind] = {
                "file_count": len(calibration),
                "uncompressed_bytes": sum(x["bytes"] for x in calibration),
                "compressed_bytes": sum(x["compressed_bytes"] for x in calibration),
                "members": calibration,
            }
        return report


def optical_tracks(path: Path):
    with path.open(newline="", errors="replace") as stream:
        reader = csv.reader(stream)
        rows = [next(reader) for _ in range(7)]
    type_row, name_row, field_row = rows[2], rows[3], rows[5]
    columns = [0, 1]
    blocks = {}
    for body in ("thigh", "shin", "thigh2", "shin2"):
        block = [i for i, (kind, name, field) in enumerate(zip(type_row, name_row, field_row))
                 if kind == "Rigid Body" and name == body and field in ("Rotation", "Position")]
        if len(block) == 7:
            blocks[body] = block
            columns.extend(block)
    if not blocks:
        raise ValueError(f"no upper rigid-body blocks found in {path}")
    data = __import__("numpy").genfromtxt(path, delimiter=",", skip_header=7,
                                              usecols=sorted(set(columns)), ndmin=2)
    # Map requested columns to the compact usecols result.
    index = {column: i for i, column in enumerate(sorted(set(columns)))}
    frames, times = data[:, index[0]], data[:, index[1]]
    masks = {}
    np = __import__("numpy")
    for body, block in blocks.items():
        q = data[:, [index[c] for c in block[:4]]]
        pose = data[:, [index[c] for c in block]]
        masks[body] = np.isfinite(pose).all(axis=1) & (np.linalg.norm(q, axis=1) > 0.5)
    metadata = dict(zip(rows[0][::2], rows[0][1::2]))
    return frames, times, masks, metadata


def coverage_audit(root: Path):
    import numpy as np
    rows = []
    for raw in sorted((root / "optical raw/rigid_bodies/upper").glob("*/*.csv")):
        name = re.sub(r"^([A-E])(\d{1,2})", lambda m: normalized_person(m[0]), raw.stem)
        name = name.removesuffix("_interp") + "_interp.csv"
        interp = root / "optical interp/rigid_bodies/upper" / raw.parent.name / name
        if not interp.exists():
            continue
        rf, rt, rm, rh = optical_tracks(raw)
        inf, it, im, ih = optical_tracks(interp)
        rlookup = {int(f): i for i, f in enumerate(rf) if np.isfinite(f)}
        ilookup = {int(f): i for i, f in enumerate(inf) if np.isfinite(f)}
        shared = sorted(rlookup.keys() & ilookup.keys())
        track_rows = {}
        for body in sorted(rm.keys() & im.keys()):
            rv = np.array([rm[body][rlookup[f]] for f in shared], dtype=bool)
            iv = np.array([im[body][ilookup[f]] for f in shared], dtype=bool)
            track_rows[body] = {
                "raw_valid_fraction_common_frames": float(rv.mean()) if len(rv) else None,
                "interp_valid_fraction_common_frames": float(iv.mean()) if len(iv) else None,
                "raw_invalid_interp_valid_frames": int((~rv & iv).sum()),
                "both_invalid_frames": int((~rv & ~iv).sum()),
                "common_frame_count": len(shared),
            }
        rows.append({
            "raw_path": str(raw), "interp_path": str(interp),
            "raw_capture_start_time": rh.get("Capture Start Time"),
            "interp_capture_start_time": ih.get("Capture Start Time"),
            "raw_take_name": rh.get("Take Name"), "interp_take_name": ih.get("Take Name"),
            "raw_total_frames_metadata": rh.get("Total Frames in Take"),
            "interp_total_frames_metadata": ih.get("Total Frames in Take"),
            "raw_rows": len(rf), "interp_rows": len(inf),
            "raw_first_frame_time": [float(rf[0]), float(rt[0])],
            "raw_last_frame_time": [float(rf[-1]), float(rt[-1])],
            "interp_first_frame_time": [float(inf[0]), float(it[0])],
            "interp_last_frame_time": [float(inf[-1]), float(it[-1])],
            "shared_frame_count": len(shared), "tracks": track_rows,
        })
    summaries = {
        "paired_files": len(rows),
        "nonzero_raw_first_frame_files": sum(r["raw_first_frame_time"][0] != 0 for r in rows),
        "nonzero_interp_first_frame_files": sum(r["interp_first_frame_time"][0] != 0 for r in rows),
        "records": rows,
    }
    return summaries


def fetch(kind: str, out: Path, report: dict, match_raw: bool = False, calibration_only: bool = False):
    category = report["categories"][kind]
    files = (report["upper_calibration"][kind]["members"] if calibration_only else
             category["first_series_with_local_inertial_counterpart_members"])
    if kind == "interp" and match_raw:
        raw = report["categories"]["raw"]["first_series_with_local_inertial_counterpart_members"]
        raw_ids = {(row["normalized_person"], re.search(r"(EAH|EFE|SQZ)([01])_([12])", row["member"]).groups()) for row in raw}
        files = [row for row in files if (row["normalized_person"], re.search(r"(EAH|EFE|SQZ)([01])_([12])", row["member"]).groups()) in raw_ids]
    total = sum(row["bytes"] for row in files)
    if total > LIMIT:
        raise ValueError(f"eligible first-series reference set is {total:,} bytes, above {LIMIT:,}; not downloading")
    reader = RangeReader(URL)
    written = []
    with zipfile.ZipFile(reader) as zf:
        for n, row in enumerate(files, 1):
            name = row["member"]
            target = out / name.removeprefix(f"optical {kind}/")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.stat().st_size != row["bytes"] or zlib.crc32(target.read_bytes()) != int(row["crc32"], 16):
                    raise ValueError(f"existing file fails size/CRC check: {target}")
                continue
            data = zf.read(name)
            if len(data) != row["bytes"] or zlib.crc32(data) != int(row["crc32"], 16):
                raise ValueError(f"downloaded member failed size/CRC: {name}")
            with target.open("xb") as stream:
                stream.write(data)
            written.append(name)
            if n % 10 == 0 or n == len(files):
                print(f"CRC-checked {n}/{len(files)} {kind} upper rigid-body optical files", flush=True)
    report["download"] = {
        "kind": kind,
        "selected_member_count": len(files),
        "selected_uncompressed_bytes": total,
        "range_bytes_transferred": reader.downloaded,
        "range_blocks_fetched": reader.cached_blocks,
        "crc_validation": "zipfile read members to EOF and explicit size/CRC32 comparisons",
        "saved_under": str(out),
        "newly_written_count": len(written),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kind", choices=("raw", "interp"), default="raw")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--match-raw-cohort", action="store_true", help="for interp, retain only files selected in the raw first-series cohort")
    ap.add_argument("--calibration-only", action="store_true", help="fetch upper calibration takes rather than exercise trials")
    ap.add_argument("--inventory-only", action="store_true")
    ap.add_argument("--audit-coverage", action="store_true", help="compare local raw/interpolated shared-frame coverage; no network")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    args.out = args.out or ROOT / ("optical raw" if args.kind == "raw" else "optical interp")
    args.report = args.report or Path(f"docs/runs/phase4/data-{args.kind}-archive.json")
    if args.audit_coverage:
        audit = coverage_audit(ROOT)
        args.report = Path("docs/runs/phase4/data-coverage.json") if args.report == Path(f"docs/runs/phase4/data-{args.kind}-archive.json") else args.report
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(audit, indent=2) + "\n")
        print(f"audited {audit['paired_files']} raw/interpolated files; nonzero frame starts raw={audit['nonzero_raw_first_frame_files']} interp={audit['nonzero_interp_first_frame_files']}")
        return
    report = inventory()
    print(json.dumps({k: {x: v for x, v in val.items() if not x.endswith("members")} for k, val in report["categories"].items()}, indent=2))
    if not args.inventory_only:
        fetch(args.kind, args.out, report, args.match_raw_cohort, args.calibration_only)
    report["retrieved_utc"] = datetime.now(timezone.utc).isoformat()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"saved catalogue report {args.report}")


if __name__ == "__main__":
    main()
