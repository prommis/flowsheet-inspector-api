#################################################################################
# The Institute for the Design of Advanced Energy Systems Integrated Platform
# Framework (IDAES IP) was produced under the DOE Institute for the
# Design of Advanced Energy Systems (IDAES).
#
# Copyright (c) 2018-2026 by the software owners: The Regents of the
# University of California, through Lawrence Berkeley National Laboratory,
# National Technology & Engineering Solutions of Sandia, LLC, Carnegie Mellon
# University, West Virginia University Research Corporation, et al.
# All rights reserved.  Please see the files COPYRIGHT.md and LICENSE.md
# for full copyright and license information.
#################################################################################
"""
Git utility code
"""

from pathlib import Path
import subprocess


def git_repo_root(file_path: str) -> Path | None:
    """Return the root directory of the Git repo containing file_path.

    Args:
        file_path: File of interest

    Returns:
        Directory, or None if there was an error from the Git command
    """
    path = Path(file_path).resolve()

    try:
        root = subprocess.check_output(
            ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return None

    return Path(root)


def git_head_hash(file_path: str | Path) -> str | None:
    """Return current commit hash for the Git repo containing file_path.

    Args:
        file_path: File of interest

    Returns:
        Hash, or None if there was an error from the Git command
    """
    path = Path(file_path).resolve()

    try:
        hash = subprocess.check_output(
            ["git", "-C", str(path.parent), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        hash = None

    return hash


if __name__ == "__main__":
    import sys

    file = sys.argv[1]

    print("repo root:", git_repo_root(file))
    print("head hash:", git_head_hash(file))
