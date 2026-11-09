"""Small assertions for cache association, feature order, and host C parity."""
import tempfile
import subprocess
from pathlib import Path

import numpy as np

import realtime_pipeline as rp


def main():
    # Stable statistic-major contract used by the historical feature extractor.
    from harness import window_features
    x = np.array([[[1., 10., 100.], [3., 14., 108.]]])
    f = window_features(x)[0]
    assert np.allclose(f[:3], [2, 12, 104])
    assert np.allclose(f[3:6], [1, 2, 4])
    assert np.allclose(f[6:9], [1, 10, 100])
    assert np.allclose(f[9:12], [3, 14, 108])

    # Actual sample cache associations, including repetitions per manifest row.
    root = Path(__file__).resolve().parents[1] / "training-data"
    bags, y, subjects, exs, names = rp.load_cache(root, "Larm")
    assert len(bags) == len(names) == len(y)
    assert all(len(b) > 0 and b.shape[1] == 31 for b in bags)
    assert len(set(subjects)) == 30
    sample = Path(__file__).resolve().parents[1] / "data-sample"
    raw_bags, raw_y, raw_subs, raw_exs, raw_names = rp.extract_raw(sample, 16)
    cached = {Path(name).name: bag for name, bag in zip(names, bags)}
    for name, bag in zip(raw_names, raw_bags):
        assert Path(name).name in cached and np.array_equal(bag, cached[Path(name).name])

    # Create deterministic synthetic fits and compare the generated C probabilities
    # after repetition softmax/sigmoid pooling with sklearn's pipeline probabilities.
    rng = np.random.default_rng(0)
    X = rng.normal(size=(80, 31)); weights = np.ones(80)
    yq = (X[:, 0] + X[:, 1] > 0).astype(int)
    ye = np.where(X[:, 2] > .5, "EAH", np.where(X[:, 2] < -.5, "EFE", "SQZ"))
    qm, em = rp.fit_model(X, yq, weights), rp.fit_model(X, ye, weights)
    with tempfile.TemporaryDirectory() as d:
        header = Path(d) / "realtime_model.h"
        rp.export_c_header(header, qm.named_steps["standardscaler"].mean_,
                           qm.named_steps["standardscaler"].scale_, em, qm)
        rows = rng.normal(size=(3, 31))
        expected_e = em.predict_proba(rows).mean(axis=0)
        expected_q = qm.predict_proba(rows)[:, 1].mean()
        c = Path(d) / "check.c"
        c.write_text('#include <stdio.h>\n#include "realtime_model.h"\nint main(void){float x[31], p[8],q,qa=0,pa[8]={0};\n'
                     + ''.join(f'x[{i}]={v:.9g}f;\n' for i,v in enumerate(rows[0]))
                     + 'if(!rt_predict_rep(x,p,&q))return 2;qa+=q;for(int j=0;j<RT_N_EXERCISES;j++)pa[j]+=p[j];\n'
                     + ''.join(f'x[{i}]={v:.9g}f;\n' for i,v in enumerate(rows[1]))
                     + 'if(!rt_predict_rep(x,p,&q))return 2;qa+=q;for(int j=0;j<RT_N_EXERCISES;j++)pa[j]+=p[j];\n'
                     + ''.join(f'x[{i}]={v:.9g}f;\n' for i,v in enumerate(rows[2]))
                     + 'if(!rt_predict_rep(x,p,&q))return 2;qa+=q;for(int j=0;j<RT_N_EXERCISES;j++)pa[j]+=p[j];\n'
                     + 'printf("%.9g",qa/3); for(int j=0;j<RT_N_EXERCISES;j++)printf(" %.9g",pa[j]/3);\n'
                     + 'x[0]=NAN;if(rt_predict_rep(x,p,&q))return 3;return 0;}\n')
        exe = Path(d) / "check"
        subprocess.run(["cc", str(c), "-I", d, "-lm", "-o", str(exe)], check=True)
        got = np.fromstring(subprocess.check_output([str(exe)], text=True), sep=" ")
        assert np.allclose(got[0], expected_q, atol=2e-6)
        assert np.allclose(got[1:], expected_e, atol=2e-6)
    print("realtime pipeline assertions passed")


if __name__ == "__main__":
    main()
