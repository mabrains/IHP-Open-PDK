#!/usr/bin/env python3
# ==========================================================================
# Copyright 2025 IHP PDK Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# SPDX-License-Identifier: Apache-2.0
# ==========================================================================

"""
Run IHP 130nm BiCMOS Open Source PDK - SG13G2 DRC Regression For Cells.

Usage:
    run_regression_cells.py (--help | -h)
    run_regression_cells.py [--cell=<cell>] [--run_dir=<run_dir_path>] [--mp=<num>]

Options:
    --help -h                 Show this help message.
    --cell=<cell>             Run regression for a specific cell only.
    --run_dir=<run_dir_path>  Output directory to store results [default: pwd].
    --mp=<num>                Number of threads for parallel DRC runs.
"""

import os
import shutil
import glob
import time
import logging
import traceback
import concurrent.futures
from datetime import datetime, timezone
from subprocess import check_call
from docopt import docopt
import pandas as pd
from pathlib import Path

# ==========================================================================
# Constants
# ==========================================================================
SUPPORTED_TC_EXT = "gds"
SUPPORTED_SW_EXT = "yaml"

# ==========================================================================
# Utility Functions
# ==========================================================================

def build_tests_dataframe(cells_dir, target_cell, cells):
    """
    Collect all DRC test cases from the provided cells directory.

    Parameters
    ----------
    cells_dir : str
        Path to the directory containing all cell folders and GDS files.
    target_cell : str or None
        If provided, only this cell will be included in the regression.
    cells : list[str]
        List of all detected cell directories.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing each cell name and its corresponding GDS file path.
    """
    tc_df = pd.DataFrame({"cell_name": cells})

    all_cells_layout = sorted(Path(cells_dir).rglob(f"*.{SUPPORTED_TC_EXT}"))

    # Map each cell to its GDS path
    cell_paths = {
        cell_name: next((path for path in all_cells_layout if cell_name in str(path)), None)
        for cell_name in tc_df["cell_name"]
    }

    tc_df["layout_path"] = tc_df["cell_name"].apply(lambda x: cell_paths[x])

    # Drop missing entries
    missing = tc_df[tc_df["layout_path"].isnull()]
    if not missing.empty:
        logging.warning(f"Missing GDS for: {missing['cell_name'].tolist()}")
        tc_df.drop(missing.index, inplace=True)

    # Filter by target cell if specified
    if target_cell:
        tc_df = tc_df[tc_df["cell_name"] == target_cell]

    if len(tc_df) == 0:
        logging.error("No valid test cases found after filtering.")
        exit(1)

    logging.info(f"Total cells to run: {len(tc_df)}")
    logging.info(f"Cells: {tc_df['cell_name'].tolist()}")

    tc_df["run_id"] = range(len(tc_df))
    return tc_df


def run_test_case(drc_dir, layout_path, run_dir, cell_name):
    """
    Run a single DRC test case.

    Parameters
    ----------
    drc_dir : str
        Directory where the DRC scripts (including run_drc.py) are located.
    layout_path : str
        Path to the GDS file of the cell to be checked.
    run_dir : str
        Directory where run results will be stored.
    cell_name : str
        Name of the top cell being tested.

    Returns
    -------
    str
        "Passed" or "Failed" depending on the DRC run results.
    """
    os.makedirs(os.path.join(run_dir, cell_name), exist_ok=True)
    layout_path_run = os.path.join(run_dir, cell_name, f"{cell_name}.gds")
    pattern_log = os.path.join(run_dir, cell_name, f"{cell_name}_drc.log")

    # Copy GDS into run directory
    shutil.copyfile(layout_path, layout_path_run)

    # Build DRC command
    call_str = (
        f"python3 {os.path.join(drc_dir, 'run_drc.py')} "
        f"--path={layout_path_run} --topcell={cell_name} "
        f"--run_dir={run_dir}/drc_run_{cell_name} --no_density"
        f"> {pattern_log} 2>&1"
    )

    try:
        check_call(call_str, shell=True)
    except Exception as e:
        logging.error(f"{cell_name} generated an exception: {e}")
        traceback.print_exc()
        return "Failed"

    # Analyze log results
    if os.path.isfile(pattern_log):
        with open(pattern_log, "r") as f:
            log_content = f.read()

        if "KLayout DRC Check Passed" in log_content:
            logging.info(f"✅ {cell_name} passed DRC.")
            return "Passed"
        else:
            logging.error(f"❌ {cell_name} failed DRC.")
            return "Failed"
    else:
        logging.error(f"No DRC log found for {cell_name}.")
        return "Failed"


def run_all_test_cases(tc_df, drc_dir, run_dir, num_workers):
    """
    Execute DRC runs for all cells concurrently.

    Parameters
    ----------
    tc_df : pd.DataFrame
        Test cases DataFrame containing cell names and paths.
    drc_dir : str
        Directory where DRC scripts are stored.
    run_dir : str
        Directory for saving run results.
    num_workers : int
        Number of threads for parallel execution.

    Returns
    -------
    pd.DataFrame
        DataFrame with DRC results for each cell.
    """
    tc_df["cell_status"] = "Pending"

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_run_id = {
            executor.submit(run_test_case, drc_dir, row["layout_path"], run_dir, row["cell_name"]): row["run_id"]
            for _, row in tc_df.iterrows()
        }

        for future in concurrent.futures.as_completed(future_to_run_id):
            run_id = future_to_run_id[future]
            try:
                status = future.result()
                tc_df.loc[tc_df["run_id"] == run_id, "cell_status"] = status
            except Exception as exc:
                logging.error(f"Run {run_id} raised an exception: {exc}")
                tc_df.loc[tc_df["run_id"] == run_id, "cell_status"] = "exception"

    return tc_df


def run_regression(drc_dir, cells_dir, output_path, target_cell, cpu_count, cells):
    """
    Run full DRC regression flow for SG13G2 standard and primitive cells.

    Parameters
    ----------
    drc_dir : str
        Path to the DRC runset directory containing `run_drc.py`.
    cells_dir : str
        Path to the cells testcases directory.
    output_path : str
        Path to store regression results.
    target_cell : str or None
        If provided, only this cell is tested.
    cpu_count : int
        Number of threads for running test cases.
    cells : list
        List of all detected cell folders.

    Returns
    -------
    bool
        True if all DRC runs passed, False otherwise.
    """
    tc_df = build_tests_dataframe(cells_dir, target_cell, cells)
    results_df = run_all_test_cases(tc_df, drc_dir, output_path, cpu_count)
    results_df.drop_duplicates(inplace=True)
    results_df.drop("run_id", inplace=True, axis=1)

    results_path = os.path.join(output_path, "all_test_cases_results.csv")
    results_df.to_csv(results_path, index=False)
    logging.info(f"📄 Saved results to: {results_path}")

    failing = results_df[results_df["cell_status"] != "Passed"]
    if len(failing) > 0:
        logging.error("Some test cases failed DRC.")
        logging.error(f"Failing cells: {failing['cell_name'].tolist()}")
        return False
    else:
        logging.info("🎉 All DRC testcases passed successfully.")
        return True


def main(drc_dir, cells_dir, output_path, target_cell, cells):
    """
    Entry point for the DRC regression workflow.

    Parameters
    ----------
    drc_dir : str
        Directory containing DRC run scripts.
    cells_dir : str
        Directory containing all cell GDS testcases.
    output_path : str
        Directory to store run results.
    target_cell : str or None
        Specific cell to run, or None for all.
    cells : list[str]
        List of available cells.
    """
    cpu_count = os.cpu_count() if args["--mp"] is None else int(args["--mp"])

    logging.info(f"Run folder: {output_path}")
    logging.info(f"Target cell: {target_cell if target_cell else 'All'}")

    start = time.time()
    success = run_regression(drc_dir, cells_dir, output_path, target_cell, cpu_count, cells)
    logging.info(f"Total execution time: {time.time() - start:.2f}s")

    if not success:
        exit(1)


# ==========================================================================
# Script Entry Point
# ==========================================================================
if __name__ == "__main__":
    args = docopt(__doc__, version="DRC Regression: 0.1")

    run_name = datetime.now(timezone.utc).strftime("drc_cells_%Y_%m_%d_%H_%M_%S")
    run_dir = args["--run_dir"]
    output_path = os.path.abspath(run_dir if run_dir not in ["pwd", "", None] else os.getcwd())
    output_path = os.path.join(output_path, run_name)
    os.makedirs(output_path, exist_ok=True)

    testing_dir = os.path.dirname(os.path.abspath(__file__))
    drc_dir = os.path.dirname(testing_dir)

    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(os.path.join(output_path, f"{run_name}.log")),
            logging.StreamHandler(),
        ],
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%d-%b-%Y %H:%M:%S",
    )

    # Pandas display setup
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)

    # Load available cells
    cells_dir = os.path.join(testing_dir, "testcases", "sg13g2_cells")
    if not os.path.isdir(cells_dir):
        logging.error(f"Cells directory not found: {cells_dir}")
        exit(1)

    # Support multiple subdirectories (stdcell and pr)
    subdirs = ["sg13g2_pr", "sg13g2_stdcell", "sg13g2_io", "sg13g2_sram"]
    all_cells = []
    for sub in subdirs:
        sub_path = os.path.join(cells_dir, sub)
        if os.path.isdir(sub_path):
            all_cells.extend([cell.name for cell in os.scandir(sub_path) if cell.is_dir()])

    if len(all_cells) == 0:
        logging.error("No cells found in testcases directory.")
        exit(1)

    target_cell = args["--cell"]
    if target_cell and target_cell not in all_cells:
        logging.error(f"Selected cell '{target_cell}' not found. Available cells: {all_cells}")
        exit(1)

    main(drc_dir, cells_dir, output_path, target_cell, all_cells)
