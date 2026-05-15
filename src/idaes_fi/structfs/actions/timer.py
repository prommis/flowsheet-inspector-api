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
"""Timing action for flowsheet runner steps."""

import time

from pydantic import BaseModel, Field

from ..action_base import Action


class Timer(Action):
    """Simple step/run timer action."""

    class Report(BaseModel):
        """Report returned by report() method."""

        # {"step_name": <float time>, ..} for each step
        timings: dict[str, float] = Field(default={})
        run_time: float = -1.0

    def __init__(self, runner, **kwargs):
        """Constructor.

        Args:
            runner: Associated Runner object
            kwargs: Additional optional arguments for Action constructor

        Attributes:
            step_times: Dict with key step name and value a list of
                        timings for that step
            run_times: List of timings for a run (sequence of steps)
        """
        super().__init__(runner, **kwargs)
        self._step_order = runner.list_steps()
        # initialize all step times to -1
        self.step_times: dict[str, float] = {step: -1 for step in self._step_order}
        self.run_time: float = -1
        # initialize internal variables
        self._run_begin, self._step_begin = None, {}

    def before_step(self, step_name):
        """Record the start time for a step.

        Args:
            step_name: Name of the step about to run.
        """
        self._step_begin[step_name] = time.time()

    def after_step(self, step_name):
        """Record the elapsed time for a completed step.

        Args:
            step_name: Name of the step that just finished.
        """
        t1 = time.time()
        t0 = self._step_begin.get(step_name, None)
        if t0 is None:
            self.log.warning(f"Timer: step '{step_name}' end without begin")
        else:
            self._cur_step_times[step_name] = t1 - t0
            self._step_begin[step_name] = None

    def before_run(self):
        """Initialize timer state before a run starts."""
        self._run_begin = time.time()
        self._cur_step_times = {}
        self._step_begin = {}

    def after_run(self):
        """Finalize run timing data after a run completes."""
        t1 = time.time()

        # set run time
        if self._run_begin is None:
            self.log.warning("Timer: run end without begin")
            self.run_time = -1
        else:
            self.run_time = t1 - self._run_begin
            self._run_begin = None

        # set all step times
        self.step_times = {
            step: self._cur_step_times.get(step, -1) for step in self._step_order
        }

    def report(self) -> Report:
        """Report the timings.

        Returns:
            The report object
        """
        rpt = self.Report(timings=self.step_times, run_time=self.run_time)
        return rpt
