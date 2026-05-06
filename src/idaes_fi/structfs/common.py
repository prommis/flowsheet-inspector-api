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
Common constants and functions
"""

from collections import OrderedDict
from enum import Enum
import importlib
from pathlib import Path
import os
import sys

DEFAULT_SOLVER_NAME = "ipopt"

#: Special key used to embed a flowsheet runner instance in a result dict
RESULT_FLOWSHEET_KEY = "__fi"


class ActionNames(Enum):
    SOLVER_OUTPUT = "solver_output"
    SOLVER_RESULTS = "solver_results"
    DIAGNOSTICS = "diagnostics"
    MODEL_VARIABLES = "model_variables"
    MERMAID_DIAGRAM = "mermaid_diagram"
    STREAM_TABLE = "stream_table"
    DOF = "degrees_of_freedom"
    TIMINGS = "timings"


class Steps:
    """Names of steps so that editor autocomplete, etc., will help
    to avoid typos.
    """

    build = "build"
    set_solver = "set_solver"
    initialize = "initialize"
    set_operating_conditions = "set_operating_conditions"
    set_scaling = "set_scaling"
    solve_initial = "solve_initial"
    set_autoscaling = "set_autoscaling"
    add_costing = "add_costing"
    initialize_costing = "initialize_costing"
    setup_optimization = "setup_optimization"
    solve_optimization = "solve_optimization"

    index = (
        build,
        set_solver,
        initialize,
        set_operating_conditions,
        set_scaling,
        solve_initial,
        set_autoscaling,
        add_costing,
        initialize_costing,
        setup_optimization,
        solve_optimization,
    )

    @classmethod
    def __len__(cls):
        return len(cls.index)


def load_module(module_or_path: str | Path):
    """
    Load a module - supports both module names and file paths.

    Args:
        module_or_path: Can be either:
            - Module name: "idaes.models.flash_flowsheet"
            - File path: "/Users/user/Downloads/my_flowsheet.py"
    Returns:
        module: The loaded Python module object.

    Note:
        For file paths, this function sets up a pseudo-package structure to
        support relative imports (e.g., 'from ..sibling import something').
    """
    # Check if input is a file path
    if (
        isinstance(module_or_path, Path)
        or module_or_path.endswith(".py")
        or os.path.isfile(module_or_path)
    ):
        # This is a file path
        file_path = Path(module_or_path).absolute()
        # file_path = os.path.abspath(module_or_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get directory structure for package simulation
        dir_path = str(file_path.parent)  # e.g., /Users/user/workspace/subdir
        parent_dir = os.path.dirname(dir_path)  # e.g., /Users/user/workspace
        package_name = os.path.basename(dir_path)  # e.g., "subdir"
        module_basename = file_path.stem
        full_module_name = f"{package_name}.{module_basename}"  # e.g., "subdir.test"

        # Add both current directory and parent directory to sys.path
        # Current dir is needed for same-directory imports (import hda_ideal_VLE)
        # Parent dir is needed for sibling package imports
        if dir_path not in sys.path:
            sys.path.insert(0, dir_path)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        # Create module spec with submodule_search_locations for package support
        spec = importlib.util.spec_from_file_location(
            full_module_name, file_path, submodule_search_locations=[dir_path]
        )

        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {file_path}")

        # Create the module object from spec
        module = importlib.util.module_from_spec(spec)

        # KEY: Set __package__ so relative imports know the package context
        module.__package__ = package_name

        # Register in sys.modules so other imports can find it
        sys.modules[full_module_name] = module

        # Execute the module code (this actually loads the content)
        spec.loader.exec_module(module)
        return module
    else:
        if module_or_path.startswith("."):
            raise ValueError("Relative module names not allowed!!")
        # This is a module name, use the original logic
        return importlib.import_module(module_or_path)
