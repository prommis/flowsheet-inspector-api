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
Unit model report extraction action
"""

# stdlib
from enum import Enum

# IDAES and Pyomo
from idaes.core.util.units_of_measurement import report_quantity
from idaes.core.util.model_statistics import (
    number_activated_blocks,
    number_activated_constraints,
    number_variables,
    degrees_of_freedom,
)
from idaes.core.base.unit_model import UnitModelBlockData
from pyomo.network import Arc
from idaes.core.util.exceptions import ConfigurationError

# Pydantic
from pydantic import BaseModel, Field

# package
from ..action_base import Action


class ModelType(str, Enum):
    unit = "unit"
    flowsheet = "flowsheet"


class PerfReport(BaseModel):
    """Report for UnitModelReport"""

    model_type: ModelType
    performance: dict = Field(default={})
    stream_table: dict = Field(default={})
    dof: dict = Field(default={})
    time_point: float = 0.0


class ComponentReports(BaseModel):
    reports: dict[str, PerfReport] = Field(default={})


class UnitModelReport(Action):
    """Extract report from unit model.

    The 'Report' in the name of this class refers to the `report()` method you
    call on the IDAES unit model, not to the Report class or `report()` method
    in this class.

    The resulting report is structured as a set of `reports` (in the unit model
    method sense), one for each component in the overall model that implements
    the reporting interface. Below is an example from the simplest
    flowsheet with one Flash unit, with one step (`step1`) and one unit (`fs.flash`).
    ```
    {
        "step_reports": {
            "step1": {
                "reports": {
                    "fs.flash": {
                        "model_type": "unit",
                        "performance": {
                            "vars": {
                                "Heat Duty": {
                                    "value": 0.0,
                                    "units": "watt",
                                    "fixed": false,
                                    "bounds": [
                                        null,
                                        null
                                    ]
                                },
                                "Pressure Change": {
                                    "value": 0.0,
                                    "units": "pascal",
                                    "fixed": false,
                                    "bounds": [
                                        null,
                                        null
                                    ]
                                }
                            }
                        },
                        "stream_table": {
                            "Units": {
                                "flow_mol": "mole / second",
                                "mole_frac_comp benzene": "dimensionless",
                                "mole_frac_comp toluene": "dimensionless",
                                "temperature": "kelvin",
                                "pressure": "pascal"
                            },
                            "Inlet": {
                                "flow_mol": 1.0,
                                "mole_frac_comp benzene": 0.5,
                                "mole_frac_comp toluene": 0.5,
                                "temperature": 298.15,
                                "pressure": 101325.0
                            },
                            "Vapor Outlet": {
                                "flow_mol": 0.5,
                                "mole_frac_comp benzene": 0.5,
                                "mole_frac_comp toluene": 0.5,
                                "temperature": 298.15,
                                "pressure": 101325.0
                            },
                            "Liquid Outlet": {
                                "flow_mol": 0.5,
                                "mole_frac_comp benzene": 0.5,
                                "mole_frac_comp toluene": 0.5,
                                "temperature": 298.15,
                                "pressure": 101325.0
                            }
                        },
                        "dof": {
                            "dof_stat": 7,
                            "num_variables": 48,
                            "num_act_constraints": 41,
                            "num_act_blocks": 5
                        },
                        "time_point": 0.0
                    }
                }
            }
        },
        "last_step": "step1"
    }
    ```


    """

    class Report(BaseModel):
        # report for each step; the report for the run is just the last one
        step_reports: dict[str, ComponentReports] = Field(default={})
        last_step: str = ""

    def __init__(self, *args, **kwargs):
        """Constructor.

        Args:
            args:  Passed to superclass
            kwargs: Passed to superclass, except:
               - 'allow_empty_performance': If True, include units with
                                            no performance data (but
                                            possibly stream tables).
        """
        if "allow_empty_performance" in kwargs:
            self._allow_empty_perf = bool(kwargs["allow_empty_performance"])
            del kwargs["allow_empty_performance"]
        else:
            self._allow_empty_perf = False
        super().__init__(*args, **kwargs)
        self._dof = True  # XXX: allow user to control
        self._rpt = self.Report()

    def after_step(self, name: str):
        """Get all the component reports in the model, after each step."""
        self._rpt.step_reports[name] = self._get_component_reports()
        self._rpt.last_step = name  # make it easy to find last report

    def _get_component_reports(self) -> dict[str, ComponentReports]:
        m, r = self._runner.model, ComponentReports()
        for comp in m.component_objects():
            comp_name = comp.name
            # print(f"{comp_name} ({type(comp_name)})")
            if not comp_name in r and self._has_report(comp):
                rpt = self._get_report(comp)
                if rpt is not None:
                    r.reports[comp_name] = rpt
        return r

    @staticmethod
    def _has_report(comp: object):
        return isinstance(comp, UnitModelBlockData) and hasattr(
            comp, "_get_performance_contents"
        )

    def _get_report(self, comp):
        time_point = 0.0

        is_fs = hasattr(comp, "is_flowsheet") and comp.is_flowsheet
        rpt = PerfReport(
            model_type="flowsheet" if is_fs else "unit", time_point=time_point
        )

        # Get DoF and model stats
        if self._dof:
            rpt.dof = dict(
                dof_stat=degrees_of_freedom(comp),
                num_variables=number_variables(comp),
                num_act_constraints=number_activated_constraints(comp),
                num_act_blocks=number_activated_blocks(comp),
            )

        # Get performance variables
        performance = comp._get_performance_contents(time_point=time_point)
        if performance is None or performance == {}:
            self.log.debug(
                f"Empty performance contents for {rpt.model_type.value} model {comp}"
            )
            if not self._allow_empty_perf:
                self.log.debug(f"Skipping {comp} due to empty performance data")
                return None  # stop!
        else:
            # reformat variable values
            for section in ("vars",):
                try:
                    performance_section = performance[section]
                except KeyError:
                    self.log.error(f"Missing 'vars' section in model report for {comp}")
                    continue
                for k, v in performance_section.items():
                    # serialize pyomo value objects as dicts
                    if hasattr(v, "value"):
                        performance[section][k] = {
                            "value": report_quantity(v).m,
                            "units": str(report_quantity(v).u),
                            "fixed": v.fixed,
                            "bounds": v.bounds,
                        }
                    # leave other objects alone
            rpt.performance = performance

        # Get stream table
        try:
            stream_table = comp._get_stream_table_contents(time_point=time_point)
            stream_dict = stream_table.to_dict()
            stream_dict["Units"] = {k: str(v) for k, v in stream_dict["Units"].items()}
        except (AttributeError, ConfigurationError):
            stream_dict = {}
        rpt.stream_table = stream_dict

        return rpt

    def report(self) -> Report:
        """Report containing unit model or flowsheet report values after each step."""
        return self._rpt
