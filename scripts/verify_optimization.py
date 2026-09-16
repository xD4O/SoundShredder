"""Compare optimized real-weight output to a saved run of upstream inference."""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from soundshredder.audio import STEMS, decode, read_json, resample  # noqa: E402
from soundshredder.engine import run_model  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_session", type=Path)
    args = parser.parse_args()
    folder = args.reference_session
    request = read_json(folder / "request.json")
    audio, rate = decode(folder / request["source"], folder / "work")
    started = time.monotonic()
    output = run_model(resample(audio, rate, 48000), "cuda", lambda _, message: print(message, flush=True))
    optimized_seconds = time.monotonic() - started
    errors = {}
    for name in STEMS:
        reference, _ = sf.read(folder / "work" / f"{name}.wav", dtype="float32", always_2d=True)
        actual = resample(output[name], 48000, rate, len(audio))
        errors[name] = float(np.max(np.abs(actual - reference)))
        np.testing.assert_allclose(actual, reference, atol=2e-6, rtol=1e-5)
    result = {
        "optimized_seconds": optimized_seconds,
        "reference_full_job_seconds": read_json(folder / "separation.json")["processing_seconds"],
        "maximum_absolute_error_by_stem": errors,
        "passed": True,
    }
    Path("artifacts/optimization-parity.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
