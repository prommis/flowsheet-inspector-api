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
"""Degrees-of-freedom checking action."""

from collections.abc import Callable
from typing import Optional, Union

from idaes.core.base.unit_model import ProcessBlockData
from idaes.core.util.model_statistics import degrees_of_freedom
from pydantic import BaseModel, Field
from pyomo.network.port import ScalarPort

from ..action_base import Action
from ..fsrunner import BaseFlowsheetRunner

# Hold degrees of freedom for one BaseFlowsheetRunner 'step'
# {key=component: value=dof}
UnitDofType = dict[str, int]


class UnitDofChecker(Action):
    """Check degrees of freedom on unit models.

    After a (caller-named) step or steps, check the degrees
    of freedom on each unit model by the method of
    fixing the inlet, applying the `degrees_of_freedom()` function,
    and unfixing the inlet again. The calculated values are
    saved and passed to an optional caller-provided function.

    At the end of a run, the degrees of freedom for the entire
    model are checked, saved, and passed to an optional function.
    """

    class Report(BaseModel):
        """Report on degrees of freedom in a model."""

        steps: dict[str, UnitDofType] = Field(
            default={},
            description="Degrees of freedom for each named step",
            examples=[{"build": 2, "set_operating_conditions": 1, "solve": 1}],
        )
        model: int = Field(
            default=0, description="Degrees of freedom for the entire model"
        )

    def __init__(
        self,
        runner: BaseFlowsheetRunner,
        flowsheet: str,
        steps: Union[str, list[str]],
        step_func: Optional[Callable[[str, UnitDofType], None]] = None,
        run_func: Optional[Callable[[dict[str, UnitDofType], int], None]] = None,
        **kwargs,
    ):
        """Constructor.

        Args:
            runner: Associated Runner object (provided by `add_action`)
            flowsheet: Variable name for flowsheet, e.g. "fs"
            steps: Step or steps at which to run the checking action
            step_func: Function to call with calculated DoF values for one step.
                  Takes name of step and dictionary with per-unit degrees of freedom
                  (see `UnitDofType` alias).
            run_func: Function to call with calculated DoF values for each step, as well
                  as overall model DoF.
            kwargs: Additional optional arguments for Action constructor

        Raises:
            ValueError: if `steps` list is empty, or no callback functions provided
        """
        super().__init__(runner, **kwargs)
        if hasattr(steps, "lower"):  # string-like
            self._steps = {steps}
        else:  # assume it is list-like
            if len(steps) == 0:
                raise ValueError("At least one step name must be provided")
            self._steps = set(steps)
        self._steps_dof: dict[str, UnitDofType] = {}
        self._model_dof = 0
        self._step_func, self._run_func = step_func, run_func
        self._fs = flowsheet

    def after_step(self, step_name: str):
        """Compute unit and model degrees of freedom after a step.

        Args:
            step_name: Name of the step that just completed.
        """
        step_name = self._runner.normalize_name(step_name)
        if step_name not in self._steps:
            self.log.debug(f"Do not check DoF for step: {step_name}")
            return

        try:
            fs = self._get_flowsheet()
        except AttributeError:
            self.log.error(
                f"Could not access flowsheet: attribute '{self._fs}' not found."
            )
            return

        model_dof = degrees_of_freedom(self._get_flowsheet())
        units_dof = {self._fs: model_dof}
        for unit in fs.component_objects(descend_into=True):
            if self._is_unit_model(unit):
                units_dof[unit.name] = self._get_dof(unit)
        self._steps_dof[step_name] = units_dof  # save
        if self._step_func:
            self._step_func(step_name, units_dof)

    def after_run(self):
        """Actions performed after a run."""
        fs = self._get_flowsheet()
        model_dof = degrees_of_freedom(fs)
        self._model_dof = model_dof
        if self._run_func:
            self._run_func(self._steps_dof, model_dof)

    def _get_flowsheet(self):
        m = self._runner.model
        if self._fs:
            return getattr(m, self._fs)
        return m

    @staticmethod
    def _is_unit_model(block):
        return isinstance(block, ProcessBlockData)

    def get_dof(self) -> dict[str, UnitDofType]:
        """Get degrees of freedom

        Returns:
            dict[str, UnitDofType]: Mapping of step name to per-unit DoF when
               the step completed.
        """
        return self._steps_dof.copy()

    def get_dof_model(self) -> int:
        """Get degrees of freedom for the model.

        Returns:
            int: Last calculated DoF for the model.
        """
        return self._model_dof

    def steps(self, only_with_data: bool = False) -> list[str]:
        """Get list of steps for which unit degrees of freedom are calculated.

        Args:
            only_with_data: If True, do not return steps with no data

        Returns:
            list of step names
        """
        if only_with_data:
            return [s for s in self._steps if s in self._steps_dof]
        return list(self._steps)

    def report(self) -> Report:
        """Machine-readable report of degrees of freedom.

        Returns:
            Report object
        """
        return self.Report(steps=self.get_dof(), model=self.get_dof_model())

    @staticmethod
    def _get_dof(block, fix_inlets: bool = True):
        if fix_inlets:
            inlets = [
                c
                for c in block.component_objects(descend_into=False)
                if isinstance(c, ScalarPort)
                and (c.name.endswith("inlet") or c.name.endswith("recycle"))
            ]
            free_me = []
            for inlet in inlets:
                if not inlet.is_fixed():
                    inlet.fix()
                    free_me.append(inlet)

        dof = degrees_of_freedom(block)

        if fix_inlets:
            for inlet in free_me:
                inlet.free()

        return dof
