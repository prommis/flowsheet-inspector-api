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
"""Stream table action."""

from idaes.core.util.tables import create_stream_table_ui
from pydantic import BaseModel
from pyomo.network import Arc

from ..action_base import Action
from ..fsrunner import BaseFlowsheetRunner


class StreamTable(Action):
    """Action to generate a stream table from the current model."""

    class Report(BaseModel):
        """Stream table, where each row is a variable and each column is a stream."""

        index: list[str]  # name of each row, i.e. the stream name
        units: list[str]  # units for each row
        columns: list[str]  # column header: <stream-name-1>, <stream-name-2>, ...
        #: rows, where each value is a tuple of the value and fixed/free/parameter/expression
        data: list[list[tuple[float, str]]]

    def __init__(self, runner, **kwargs):
        assert isinstance(runner, BaseFlowsheetRunner)  # makes no sense otherwise
        super().__init__(runner, **kwargs)
        self._stream_table = {}

    def after_run(self):
        """Build stream table after the run."""
        # get streams
        streams = {}
        for component in self._runner.model.component_objects(Arc, descend_into=True):
            streams[component.getname()] = component

        # create stream table using existing utility function
        df = create_stream_table_ui(streams)
        dd = df.to_dict(orient="split")

        # move units column to its own list
        dd["columns"] = dd["columns"][1:]  # delete first column of header
        dd["units"] = [str(r[0]) for r in dd["data"]]  # copy Units obj, convert to str
        dd["data"] = [r[1:] for r in dd["data"]]  # delete 1st column of data

        self._stream_table = dd

    def report(self) -> Report:
        if self._stream_table:
            report = self.Report(**self._stream_table)
        else:
            report = self.Report(index=[], units=[], columns=[], data=[])
        return report
