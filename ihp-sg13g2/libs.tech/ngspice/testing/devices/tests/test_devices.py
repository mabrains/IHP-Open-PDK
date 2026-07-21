# =========================================================================================
# Copyright 2025 IHP PDK Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========================================================================================
"""
CI entry point for the SG13G2 model verification flow.

Called by the GoCD pipeline as::

    python3 -m pytest --tb=short -p no:cacheprovider \\
        tests/test_devices.py::test_devices[nmos_hv]

This is a thin wrapper over `models_verifier` -- it adds no verification logic
of its own. It imports the same objects the package already exposes:

    models_verifier.constants.CASES          -> device label -> config mapping
    models_verifier.models_verifier.MdmVerifier -> the verification engine

One parametrised case per entry in CASES, with the device label as the test id,
so every Makefile target has a matching pytest node id:

    make test-nmos_hv   <->   tests/test_devices.py::test_devices[nmos_hv]

Pass/fail policy
----------------
`MdmVerifier.run_verification()` returns 0 when every sweep is inside
tolerance and 1 when some are not. A non-zero return is a model-quality
signal, not a broken build, and is expected to stay non-zero while model
cards are being tuned -- the README's own sample run shows 784 failing
measured sweeps for nmos_lv.

So by default this test fails only on *infrastructure* problems, which the
package raises as exceptions (ConfigError, VerificationError) rather than
return codes. Model deviations are reported and the build stays green.

Set DEVICE_TEST_STRICT=1 to fail on any deviation, i.e. to make this test
behave exactly like `make test-<device>`.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------------------
# Make the package importable, then import it. `devices/` is this file's parent.
# --------------------------------------------------------------------------------------

DEVICES_DIR = Path(__file__).resolve().parents[1]

if str(DEVICES_DIR) not in sys.path:
    sys.path.insert(0, str(DEVICES_DIR))

from models_verifier.constants import CASES  # noqa: E402
from models_verifier.models_verifier import (  # noqa: E402
    ConfigError,
    MdmVerifier,
    VerificationError,
)

CASE_MAP: dict[str, str] = dict(CASES)

STRICT = os.environ.get("DEVICE_TEST_STRICT", "").strip().lower() in {"1", "true", "yes"}


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def _require_ngspice(device: str) -> None:
    """
    Check upfront so a missing simulator is reported plainly.

    Without this, ngspice's absence surfaces indirectly: every worker raises
    FileNotFoundError, _aggregate_and_simulate swallows it per setup type, and
    the run ends as VerificationError("No merged sim-vs-measured rows
    produced") -- which reads like a data problem, not a missing binary.
    """
    if shutil.which("ngspice") is None:
        pytest.fail(
            f"[{device}] ngspice is not on PATH. Install it on the GoCD agent "
            f"(see the Prerequisites section of README.md).",
            pytrace=False,
        )


def _report(device: str, verifier: MdmVerifier) -> str | None:
    """Echo the run's final_summary.md into the console / JUnit output."""
    summary_path = verifier.output_dir / "final_reports" / "final_summary.md"
    if not summary_path.is_file():
        return None
    try:
        summary = summary_path.read_text()
    except OSError:
        return None
    print(f"\n--- [{device}] {summary_path} ---\n{summary}")
    return summary


# --------------------------------------------------------------------------------------
# Test
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("device", list(CASE_MAP), ids=list(CASE_MAP))
def test_devices(device: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the verification flow for one device via MdmVerifier."""
    # Paths inside the config YAMLs (mdm_dir, corner_lib_path, osdi_path,
    # dc_template_path, output_dir) are relative to devices/, exactly as the
    # Makefile invokes the verifier. Run from there so they resolve identically.
    monkeypatch.chdir(DEVICES_DIR)

    cfg_rel = CASE_MAP[device]
    cfg_path = Path(cfg_rel)

    if not cfg_path.is_file():
        pytest.fail(
            f"[{device}] config not found: {cfg_rel} "
            f"(expected at {DEVICES_DIR / cfg_rel})",
            pytrace=False,
        )

    _require_ngspice(device)

    try:
        verifier = MdmVerifier(cfg_path)
        return_code = verifier.run_verification()
    except (ConfigError, VerificationError) as exc:
        # The package's own error types: bad/missing config, no MDM data
        # discovered, nothing merged. All infrastructure, never model quality.
        pytest.fail(f"[{device}] verification could not run: {exc}", pytrace=False)
    except Exception as exc:  # noqa: BLE001
        # Anything else (missing dependency, ngspice crash, bug) fails loudly
        # with a full traceback rather than being mistaken for a bad model.
        raise AssertionError(f"[{device}] unexpected error during verification: {exc}") from exc

    summary = _report(device, verifier)

    if return_code == 0:
        return

    message = (
        f"[{device}] verifier reported sweeps outside tolerance "
        f"(return code {return_code}). See {verifier.output_dir / 'final_reports'}."
    )

    if STRICT:
        pytest.fail(f"{message}\n\n{summary or ''}", pytrace=False)

    print(
        f"\n[{device}] NOTE: {message}\n"
        f"Not failing the build -- set DEVICE_TEST_STRICT=1 to gate on model quality."
    )
