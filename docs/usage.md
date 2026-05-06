---
title: Flowsheet Inspector Library Usage
---
# Flowsheet Inspector Library Usage

The Flowsheet Inspector (FI) library is primarily a way to "wrap" the functions
used to build, set up, and solve a flowsheet so that these steps can be
controlled from outside the program, and also arbitrary "actions" can run before
and after each step or each sequence of steps. Built-in actions include
gathering information on variable state, creating a diagram, and running the
diagnostics, but this is extensible.

This section starts from the assumption that you have a FI-wrapped flowsheet and
describes how to run it and get back the information it collects during the
actions. For information on how to wrap the flowsheet, see the [API](api)
section.

## VSCode extension

You can load and run FI flowsheets with our VSCode extension. Please see the
[FI VSCode extension](https://github.com/prommis/flowsheet-inspector) for
details.

## Command-line (shell)

You can run a flowsheet from the command-line with `fi-run`.

### Usage

```{code} text
$ fi-run -h
usage: fi-run [-h] [--db DB] [--attr ATTR] [--last LAST] [-q] [-v] name

Run a flowsheet from the command-line.

positional arguments:
  name         Flowsheet file name or module name

options:
  -h, --help   show this help message and exit
  --db, -D DB  Alternate SQLite database file for results (default=~/home/dang/.idaes/reportdb.sqlite)
  --attr ATTR  Name of attribute in file/module containing structured flowsheet (e.g., 'FS'). This is only needed
               if there is more than one.
  --last LAST  Name of last step to run. Steps (in order): build, set_solver, initialize,
               set_operating_conditions, set_scaling, solve_initial, set_autoscaling, add_costing,
               initialize_costing, setup_optimization, solve_optimization
  -q, --quiet  Don't print extra info
  -v           increase verbosity
```

### Examples

To run the structured flowsheet in `excellent_flowsheet.py` in the current
directory:

```{code} shell
fi-run excellent_flowsheet.py
```

To run the structured flowsheet "fs1" in `multiple_flowsheets.py` in the current
directory, use the `--attr` flag to indicate the one you want.

```{code} shell
fi-run excellent_flowsheet.py --attr fs1
```

## Python API in a script

There are two basic ways to run structure flowsheets in a script.

The simplest and most obvious way is to import the structured flowsheet object
that was created in the module, and call `run_steps()` on that object.

```{code} python
from excellent_flowsheet import FS  # import flowsheet object
# ...
def main():
    FS.run_steps()
```

The second way is to call `run_flowsheet()`, which can run any module or path
(and is what the program `fi-run` calls internally).

```{code} python
def run_flowsheet(
    module_or_path: str, fs_attr: str = "", step_kw: dict[str, str] = None, **kwargs
) -> BaseFlowsheetRunner:
    """Run structfs-wrapper flowsheet found in a file or module.

    Args:
        module_or_path (str): Filesystem path or Python module path
        fs_attr: Used to select among multiple flowsheet wrappers in the same module.
                 If not given use the first one found, otherwise require a match.
        step_kw: Keywords sent to the `run_steps()` function, if applicable
        kwargs: Additional keyword arguments passed to fi_main, if applicable

    Returns:
        The flowsheet object that was run.

    Raises:
        ValueError, if no flowsheet is found, or no match to fs_attr
    """
```

## Python API in a Jupyter Notebook

Usage in Jupyter is the same as in a Python program. In this environment the
`fi_main` decorator may be handy. For a full example, see this
[example Jupyter notebook](usage_nb).
