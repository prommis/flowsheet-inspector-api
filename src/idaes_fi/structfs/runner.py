#################################################################################
# Process Optimization and Modeling for Minerals Sustainability (PrOMMiS) Copyright (c) 2023-2026
#
# “Process Optimization and Modeling for Minerals Sustainability (PrOMMiS)” was produced under the DOE
# Process Optimization and Modeling for Minerals Sustainability (“PrOMMiS”) initiative, and is
# copyrighted by the software owners: The Regents of the University of California, through Lawrence
# Berkeley National Laboratory, National Technology & Engineering Solutions of Sandia, LLC through
# Sandia National Laboratories, Carnegie Mellon University, University of Notre Dame, and West
# Virginia University Research Corporation.
#
# NOTICE. This Software was developed under funding from the U.S. Department of Energy and the
# U.S. Government consequently retains certain rights. As such, the U.S. Government has been granted
# for itself and others acting on its behalf a paid-up, nonexclusive, irrevocable, worldwide license
# in the Software to reproduce, distribute copies to the public, prepare derivative works, and perform
# publicly and display publicly, and to permit other to do so.
#
#################################################################################
"""
Run functions in a module in a defined, named, sequence.
"""

import importlib
import logging
from pathlib import Path
import traceback
from typing import Callable, Optional, Tuple, Sequence, TypeVar

# third party
from pydantic import BaseModel

# package
from idaes.config import get_data_directory
from .action_base import Action
from .reportdb import ReportDB
from .common import ActionNames, Steps
from .. import gitutil

__author__ = "Dan Gunter (LBNL)"

_log = logging.getLogger(__name__)


class Step:
    """Step to run by the `Runner`."""

    SEP = "::"  # when printing out step::substep

    def __init__(self, name: str, func: Callable):
        """Constructor

        Args:
            name: Name of the step
            func: Function to call to execute the step
        """
        self.name: str = name
        self.func: Callable = func
        self.substeps: list[Tuple[str, Callable]] = []

    def add_substep(self, name: str, func: Callable):
        """Add a sub-step to this step.
        Substeps are run in the order given.

        Args:
            name: The name of substep
            func: Function to call to execute this substep
        """
        self.substeps.append((name, func))


# Python 3.9-compatible forward reference
ActionType = TypeVar("ActionType", bound="Action")  # pylint: disable=C0103


class Runner:
    """Run a set of defined steps."""

    STEP_ANY = "-"

    def __init__(self, steps: Sequence[str], report_db: ReportDB = None):
        """Constructor.

        Args:
            steps: List of step names
            report_db: Report database to use (otherwise default one)
        """
        self._context = {}
        self._actions: dict[str, ActionType] = {}
        self._step_names = list(steps)
        self._steps: dict[str, Step] = {}
        self._failed = False
        self._actions_failed = {}
        self.reset()
        self._tags = ""  # for reporting
        self._report_db = report_db or self.get_default_report_db(create=True)

    @property
    def failed(self) -> bool:
        return bool(self._failed)

    @property
    def failed_actions(self) -> dict[str, str]:
        return self._actions_failed.copy()

    def get_defined_steps(self) -> list[str]:
        """Get list of defined step (names)."""
        return [name for name in self._step_names if self._steps.get(name, None)]

    def get_report_db(self) -> ReportDB:
        """Get current report database.

        Returns:
            ReportDB: Default report DB instance
        """
        return self._report_db

    def set_report_db(
        self,
        db: Optional[ReportDB] = None,
        dbfile: Optional[Path | str] = None,
        create: bool = True,
    ) -> ReportDB:
        """Set a new value for the report database.

        Args:
            db: New report database
            dbfile: Path to reportdb file.
            create: Create report database if it does not exist.

        Returns:
            ReportDB: Previous report database

        Raises:
            ValueError: If neither argument is provided
        """
        if db is None:
            # Get ReportDB from path
            if dbfile is None:
                raise ValueError("Either a `db` or `dbfile` argument is required")
            # get a ReportDB instance, creating DB if necessary and allowed
            do_create = False
            dbfile = Path(dbfile)
            if not dbfile.exists():
                if create:
                    do_create = True
                else:
                    raise ValueError(
                        f"Database file `{dbfile}` does not exist and `create` flag is False"
                    )
            db = ReportDB(dbfile)
            if do_create:
                db.create()

        assert isinstance(db, ReportDB)
        prev, self._report_db = self._report_db, db

        prev_tgt = prev.get_target()
        if prev_tgt:
            self._report_db.set_target(**prev_tgt)

        return prev

    @classmethod
    def get_default_report_db(cls, create=False) -> ReportDB:
        """Get the default report database.

        Args:
            create (bool, optional): If true, create it if not found. Defaults to False.

        Raises:
            ValueError: If create is False and the database is not found

        Returns:
            ReportDB: Default report DB instance
        """
        # get IDAES home directory
        data_dir, _, _ = get_data_directory()
        data_path = Path(data_dir)

        # set reportdb to be a file in that directory
        report_db_path = data_path / "reportdb.sqlite"

        # set `db` to a new ReportDB instance
        if report_db_path.exists():
            # if it exists, just open it
            db = ReportDB(report_db_path)
        elif not create:
            raise ValueError(f"Report database not found at path: {report_db_path}")
        else:
            # if it doesn't exist, create tables
            db = ReportDB(report_db_path)
            db.create()

        return db

    def __getitem__(self, key):
        """Look for key in `context`"""
        return self._context[key]

    def __getattr__(self, key):
        """For attributes not in the class, look to see if they
        match attributes on the context and if so return that value.
        """
        if key and key[0] == "_":
            raise AttributeError(key)
        if hasattr(self._context, key):
            return getattr(self._context, key)
        raise AttributeError(
            f"Runner object has no attribute '{key}' and "
            f"'{key}' is not an attribute of the context object"
        )

    def add_step(self, name: str, func: Callable):
        """Add a step.

        Steps are executed by calling `func(context)`,
        where `context` is a dict (or dict-like) object
        that is used to pass state between steps.

        Args:
            name: Add a step to be executed
            func: Function to execute for the step.

        Raises:
            KeyError: _description_
        """
        step_name = self.normalize_name(name)

        if step_name not in self._step_names:
            steppenlist = ", ".join(self._step_names)
            raise KeyError(f"Unknown step: {step_name} not in: {steppenlist}")
        self._steps[step_name] = Step(step_name, func)

    def add_substep(self, base_name, name, func):
        """Add a substep for a given step.

        Substeps are all executed, in the order added,
        immediately after their base step is executed.

        Args:
            base_name: Step name
            name: Substep name
            func: Function to execute

        Raises:
            KeyError: Base step or substep is not found
            ValueError: Base step does not have any substeps
        """
        substep_name = self.normalize_name(name)
        base_step_name = self.normalize_name(base_name)
        if base_step_name not in self._step_names:
            raise KeyError(
                f"Unknown base step {base_step_name} for substep {substep_name}"
            )
        try:
            step = self._steps[base_step_name]
        except KeyError:
            raise ValueError(
                f"Empty base step {base_step_name} for substep {substep_name}"
            )
        step.add_substep(substep_name, func)

    def run_step(self, name):
        """Syntactic sugar for calling `run_steps` for a single step."""
        self.run_steps(first=name, last=name)

    def run_steps(
        self,
        first: str = "",
        last: str = "",
        after: str = "",
        before: str = "",
        closest_step=False,
        save_report=True,
    ):
        """Run steps from `first`/`after` to step `last`/`before`.

           Specify only one of the first/after and last/before pairs.

           Use the special value `STEP_ANY` to mean the first or last defined step.

        Args:
            first: First step to run (include)
            after: Run first defined step after this one (exclude)
            last: Last step to run (include)
            before: Run last defined step before this one (exclude)
            closest_step: If True, and step given is empty, that's ok since we will run the closest step;
                          If False, require that the specified steps be non-empty (default)
            save_report: If true save report in report database, if False don't do this

        Raises:
            KeyError: Unknown or undefined step given
            ValueError: Steps out of order or both first/after or before/last given
        """
        if first and after:
            raise ValueError("Cannot specify both 'after' and 'first'")
        if last and before:
            raise ValueError("Cannot specify both 'before' and 'last'")
        if not self._steps:
            return  # nothing to do, no steps defined
        args = (
            first or after,
            last or before,
            (bool(first) or not bool(after), bool(last) or not bool(before)),
            closest_step,
        )
        self._run_steps(*args)
        if save_report:
            self._save_report()

    def _run_steps(
        self, first: str, last: str, endpoints: tuple[bool, bool], closest: bool
    ):
        names = (self.normalize_name(first), self.normalize_name(last))

        # Try to complete the report target, from value of 'module'
        tgt = self.get_report_target()
        if "module" in tgt:
            tgt_changed = False
            try:
                modname = tgt["module"]
                if modname:
                    mod = importlib.import_module(modname)
                else:
                    mod = None
            except ImportError as err:
                _log.error(f"Cannot import module {modname}")
                mod = None
            if mod:
                p = None
                if mod.__name__ == "__main__":
                    # if in VSCode, use special attr
                    nb_path = getattr(mod, "__vsc_ipynb_file__")
                    if nb_path:
                        p = Path(nb_path)
                        # clear any existing values
                        tgt.update({"filename": "", "filedir": ""})
                else:
                    try:
                        p = Path(mod.__file__)
                    except AttributeError as err:
                        _log.warning(f"Cannot set file for module '{mod}': {err}")
                if p is not None:
                    if not tgt.get("filename", "") and not tgt.get("filedir", ""):
                        tgt["filename"] = p.name
                        tgt["filedir"] = str(p.parent.absolute())
                        tgt_changed = True
                    if not tgt.get("hash", ""):
                        repo_hash = gitutil.git_head_hash(p)
                        if repo_hash is not None:
                            tgt["hash"] = repo_hash
                            tgt_changed = True
            if tgt_changed:
                _log.debug(f"setting report target: {tgt}")
                self.set_report_target(**tgt)

        self._last_run_steps = []

        # get indexes of first/last step
        _log.warning(
            f"get indexes of first step '{names[0]}' and last step '{names[1]}' "
            f"in steps {self._step_names}"
        )
        step_range = [-1, -1]
        for i, step_name in enumerate(names):
            if step_name == self.STEP_ANY:  # meaning first or last defined
                # this will always find a step as long as there is at least one,
                # which we checked before calling this function
                idx = self._find_step(reverse=i == 1)
            else:
                try:
                    idx = self._step_names.index(step_name)
                except ValueError:
                    raise KeyError(f"Unknown step: {step_name}")
                if step_name not in self._steps:
                    if closest:
                        _log.warning(
                            f"Step {step_name} is empty, will run closest step"
                        )
                    else:
                        raise KeyError(f"Empty step: {step_name}")
            step_range[i] = idx

        # check that first comes before last
        if step_range[0] > step_range[1]:
            raise ValueError(
                "Steps out of order: {names[0]}={step_range[0]} > {names[1]}={step_range[1]}"
            )

        # Start with success, my friend
        self._failed = False

        # execute overall before-run action
        for action_name, action in self._actions.items():
            try:
                action.before_run()
            except Exception as err:
                _log.error(
                    f"{action_name} failed in 'before_run' (no other actions will be run)"
                )
                where = action_name + ".after_run"
                self._failed = (where, err)
                self._actions_failed[where] = err
                break  # one failure => all failure

        # run each (defined) step (if before did not fail)
        if self._failed:
            _log.error("Failures occurred in actions before run, skipping all steps")
        else:
            for i in range(step_range[0], step_range[1] + 1):
                # check whether to skip endpoints in range
                if (i == step_range[0] and not endpoints[0]) or (
                    i == step_range[1] and not endpoints[1]
                ):
                    continue
                # get the step associated with the index
                step = self._steps.get(self._step_names[i], None)
                # if the step is defined, run it
                if step:
                    step.func(self._context)
                    self._last_run_steps.append(step.name)
                if self._failed:
                    _log.error(f"Step failed: {self._failed[0]}")
                    break  # stop

        # execute overall after-run action
        if self._failed:
            _log.error("Run failed")
        else:
            for action_name, action in self._actions.items():
                try:
                    action.after_run()
                except Exception as err:
                    _log.error(f"{action_name} failed in 'after_run'")
                    if self._failed:
                        _log.error("Multiple failures: only first will be reported")
                    else:
                        where = action_name + ".after_run"
                        self._failed = (where, err)
                        self._actions_failed[where] = err
                    continue  # allow all after_run actions, only record first failure

    def _save_report(self):
        rpt = self.report()
        _log.debug("Adding report to DB")

        # get solver result (even if we failed!)
        try:
            # try to extract from report
            actions = rpt["actions"]
            solver_results_list = actions[ActionNames.SOLVER_RESULTS]["results"]
            last_result = solver_results_list[-1]
            solver_result = last_result["solver"]["Status"]
        except KeyError:
            # if that doesn't work, just set to an empty string
            solver_result = ""

        # get run result
        if self._failed:
            run_result = False
            # get exception as string XXX: maybe get trace?
            e = self._failed[1]
            tb = e.__traceback__
            tb_text = "".join(traceback.format_tb(tb))
            run_error = f"{e.__class__.__name__}: {e}\nTraceback:\n{tb_text}"
        else:
            run_result = True
            run_error = ""

        self._report_db.add_report(
            rpt,
            tags=self._tags,
            solver_status=solver_result,
            run_status=run_result,
            run_exc=run_error,
        )

    def set_report_target(self, **target_kw):
        """Set target for report generation.

        See reportdb.TARGET_COLUMNS for possible keys, also allow 'tags'.
        """
        self._tags = target_kw.pop("tags", "")  # I'm gonna pop some tags..
        _log.debug(f"Set report target to: {target_kw}")
        self._report_db.set_target(**target_kw)

    def get_report_target(self) -> dict:
        return self._report_db.get_target()

    def reset(self):
        """Reset runner internal state, especially the context."""
        self._context = {}
        self._last_run_steps = []
        self._failed = False
        self._actions_failed = {}

    def list_steps(self, all_steps=False) -> list[str]:
        """Get list of [runnable] steps."""
        result = []
        for n in self._step_names:
            if all_steps or (n in self._steps):
                result.append(n)
        return result

    def add_action(self, name: str, action_class: type, *args, **kwargs) -> object:
        """Add a named action.

        Args:
            name: Arbitrary name for the action, used to get/remove it
            action_class: Subclass of Action to use
            args: Positional arguments passed to `action_class` constructor
            kwargs: Keyword arguments passed to `action_class` constructor
        """
        obj = action_class(self, *args, **kwargs)
        self._actions[name] = obj
        return obj

    def get_action(self, name: str) -> ActionType:
        """Get an action object.

        Args:
            name: Name of action (as provided to `add_action`)

        Returns:
            ActionType: Action object

        Raises:
            KeyError: If action name does not match any known action
        """
        return self._actions[name]

    def remove_action(self, name: str):
        """Remove an action object.

        Args:
            name: Name of action (as provided to `add_action`)

        Raises:
            KeyError: If action name does not match any known action
        """
        del self._actions[name]

    def _find_step(self, reverse=False):
        start_step, end_step, incr = (
            (0, len(self._step_names), 1),
            (len(self._step_names) - 1, -1, -1),
        )[reverse]
        for i in range(start_step, end_step, incr):
            if self._step_names[i] in self._steps:
                return i
        return -1

    @classmethod
    def normalize_name(cls, s: Optional[str]) -> str:
        """Normalize a step name.
        Args:
            s: Step name

        Returns:
            normalized name
        """
        return cls.STEP_ANY if not s else s.lower()

    def _step_begin(self, name: str):
        for action in self._actions.values():
            action.before_step(name)

    def _substep_begin(self, base: str, name: str):
        for action in self._actions.values():
            action.before_substep(base, name)

    def _step_end(self, name: str):
        for action in self._actions.values():
            action.after_step(name)

    def _substep_end(self, base: str, name: str):
        for action in self._actions.values():
            action.after_substep(base, name)

    def _step_failed(self, name: str, err: Exception):
        for action in self._actions.values():
            action.step_failed(name, err)

    def step(self, name: str):
        """Decorator function for creating a new step.

        Args:
            name: Step name

        Returns:
            Decorator function.
        """

        def step_decorator(func):

            def wrapper(*args, **kwargs):
                self._step_begin(name)
                ok, run_err = True, None
                try:
                    result = func(*args, **kwargs)
                except Exception as err:
                    ok, result, run_err = False, None, err
                if ok:
                    self._step_end(name)
                else:
                    self._failed = (name, run_err)
                    self._step_failed(name, run_err)
                return result

            self.add_step(name, wrapper)

            return wrapper

        return step_decorator

    def substep(self, base: str, name: str):
        """Decorator function for creating a new substep.

        Substeps are not run directly, and must have an already
        existing base step as their parent.

        Args:
            base: Base step name
            name: Substep name

        Returns:
            Decorator function.
        """

        def step_decorator(func):

            def wrapper(*args, **kwargs):
                self._substep_begin(base, name)
                ok, run_err = True, None
                try:
                    result = func(*args, **kwargs)
                except Exception as err:
                    ok, result, run_err = False, None, err
                if ok:
                    self._substep_end(base, name)
                else:
                    self._failed = (base + "." + name, run_err)
                return result

            self.add_substep(base, name, wrapper)

            return wrapper

        return step_decorator

    def report(self) -> dict[str, dict]:
        """Compile reports of each action into a combined report

        Returns:
            dict: Mapping with two key-value pairs:
                    - `actions`: Keys are names given to actions during `add_action()`, values are the
                      reports returned by that action, in Python dictionary form.
                    - `last_run`: List of steps (names, as strings) in previous run
        """
        # create a mapping of actions to report dicts
        action_reports = {}
        for name, action in self._actions.items():
            rpt = action.report()
            rpt_dict = rpt.model_dump() if isinstance(rpt, BaseModel) else rpt
            action_reports[name] = rpt_dict
        # return actions and other metadata as a report
        return {"actions": action_reports, "last_run": self._last_run_steps.copy()}
