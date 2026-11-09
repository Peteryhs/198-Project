"""Minimal selection and source-path checks for PHYTMO reference data."""
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory

from phase4_reference_data import candidates, normalized_person, optical_tracks


def run():
    infos = [
        SimpleNamespace(filename=f"optical {kind}/rigid_bodies/upper/A/A01EAH0_{series}{suffix}.csv")
        for kind, suffix in (("raw", ""), ("interp", "_interp"))
        for series in ("1", "2")
    ]
    assert [i.filename for i, _ in candidates(infos, "raw")] == [
        "optical raw/rigid_bodies/upper/A/A01EAH0_1.csv"
    ]
    assert [i.filename for i, _ in candidates(infos, "interp")] == [
        "optical interp/rigid_bodies/upper/A/A01EAH0_1_interp.csv"
    ]
    alias = SimpleNamespace(filename="optical raw/rigid_bodies/upper/A/A3EAH0_1.csv")
    assert [i.filename for i, _ in candidates(infos + [alias], "raw")][-1] == alias.filename
    assert normalized_person("A3") == "A03"
    unrelated = SimpleNamespace(filename="optical raw/rigid_bodies/upper/A/A01Calib.csv")
    assert [i.filename for i, _ in candidates(infos + [unrelated], "raw")] == [
        i.filename for i, _ in candidates(infos, "raw")
    ]
    with TemporaryDirectory() as directory:
        path = Path(directory) / "board.csv"
        path.write_text(
            "Format Version,1,Take Name,T,Total Frames in Take,2\n"
            ",\n"
            ",Type,Rigid Body,Rigid Body,Rigid Body,Rigid Body,Rigid Body,Rigid Body,Rigid Body\n"
            ",Name,thigh,thigh,thigh,thigh,thigh,thigh,thigh\n"
            ",ID,id,id,id,id,id,id,id\n"
            ",,Rotation,Rotation,Rotation,Rotation,Position,Position,Position\n"
            "Frame,Time (Seconds),X,Y,Z,W,X,Y,Z\n"
            "0,0,0,0,0,1,1,2,3\n"
            "1,0.01,,,,,,,,\n"
        )
        frames, times, masks, header = optical_tracks(path)
        assert frames.tolist() == [0, 1] and [round(x, 2) for x in times] == [0, 0.01]
        assert masks["thigh"].tolist() == [True, False]
        assert header["Total Frames in Take"] == "2"
    print("PHYTMO reference selection checks passed")


if __name__ == "__main__":
    run()
