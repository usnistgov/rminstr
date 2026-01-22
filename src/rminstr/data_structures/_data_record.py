"""
Contains tools for managing experimental collected during long measurements.

The classes in this module are:

* DataRecord
* ExistingRecord
* ActiveRecord

This module also contains statistical functions used to evaluate thermal
stability in the microcalorimeter.
"""

import queue
import collections
from dataclasses import dataclass, field
from collections.abc import Callable, Iterable
import datetime
import time
import pytz
import numpy as np
import scipy.stats as st
import pandas as pd
import typing
import socket
import shutil

# import warnings
# from typing import NewType
from os import listdir, rename
from os.path import isfile, join, dirname, getmtime
from pathlib import Path
from importlib.metadata import version as get_version
from rminstr.utilities.path import validate_path
# from typing import Union


try:
    from git import Repo, InvalidGitRepositoryError

except ImportError as e:
    print(
        'The module git was not found,'
        'please put it on the python path'
        "if you don't have this, run this in the anaconda prompt: "
        'conda install -c anaconda gitpython'
    )
    raise e

local_tz = pytz.timezone('US/Mountain')

# not expected to change very often

DEFAULT_REPO_PATH = Path(__file__).parents[3]
LOCAL_BACKUPS = Path.home() / 'rminstr'


Index = int
IndexArray = Iterable[Index]
DataArray = Iterable[float]


__all__ = [
    'DataRecord',
    'TimeSeries',
    'ExistingRecord',
    'ActiveRecord',
    'LegacyRecord',
    'kendall_p',
    'runs_statistic',
]


def full_row(index: int, times: DataArray, values: DataArray) -> bool:
    """
    Test if a row in the data record has missing data.

    Intended to be called by get_conditional_data.

    Parameters
    ----------
    index : int
        Index of data row. Does nothing, here because get_conditional_data
        needs it.

    times : DataArray
        Times associated with measured values. Does nothing, here because
        get_conditional_data needs it.

    values : DataArray
        A row of data.

    Returns
    -------
    bool
        False if there are any NaN's in values
    """
    return not np.any(np.isnan(values))


def runs_statistic(v: DataArray) -> float:
    """
    Determine whether the thermopile headings are stable.

    See NIST Tech Note 1374 for more details.

    Parameters
    ----------
    v : DataArray
        vector of voltage measurements

    Returns
    -------
    float
        Zscore based on number of "runs" (consecutive points with same trend)
        0 is the expected number of runs in random data, and small numbers mean
        long runs (not random)
    """
    n = len(v)
    mu_r = (2.0 * n - 1.0) / 3.0
    sigma_r = np.sqrt((16 * n - 29) / 90.0)

    # calculate runs

    d0 = v[0] - v[1]
    run_direction = np.sign(d0)
    r = 1.0

    if run_direction == 0:
        r = 0.0

    for i in range(n - 1):
        d = v[i] - v[i + 1]
        if np.sign(d) != run_direction:
            run_direction = np.sign(d)
            r = r + 1.0

    return (r - mu_r) / sigma_r


def kendall_p(v: DataArray) -> float:
    """
    Determine whether the thermopile headings are stable.

    See NIST Tech Note 1374 for more details.

    Parameters
    ----------
    v : DataArray
        vector of voltage measurements

    Returns
    -------
    float
        kendall_p: A number between 0 and 1. Small numbers (less than 0.25)
        show a decreasing trend, while large numbers (greater than 0.75)
        show an increasing trend
    """
    n = len(v)

    S = 0
    D = 0

    for i in range(n - 1):
        for j in range(i, n):
            S = S + np.sign(v[j] - v[i])
            D = D + (np.sign(v[j] - v[i]) ** 2)

    # ties
    unique_values = set(v)

    T = 0
    for value in unique_values:
        t = np.sum(v == value)
        T += t * (t - 1) * (2 * t + 5)

    Var_S = (n * (n - 1) * (2 * n + 5) - T) / 18.0

    Z_s = S / np.sqrt(Var_S)
    p = st.norm.cdf(Z_s)

    return p


@dataclass(order=True)
class update_queue_item:
    """Update queue item."""

    column: str = field(compare=False)
    value: any = field(compare=False)
    timestamp: float


class TimeSeries(typing.NamedTuple):
    """
    Class for oraganizing 1D timeseries data, output by DataRecords.

    NamedTuple like object. Can be indexed or iterated like a tuple where
    index 0 is the t attribute and index 1 is the values. Has additional
    functionality usefil for time series data.

    Attributes
    ----------
    t : np.ndarray
        Absolute time stamps in seconds of timeseries, from when data was
        taken.
    values: str
        Values of timeseries data.
    """

    t: np.ndarray
    values: np.ndarray

    def trel(
        self,
    ) -> np.ndarray:
        """Get the relative time of."""
        return self.t - self.t[0]


class DataRecord:
    """
    The DataRecord class records experimental data from long measurements.

    There are two derived classes: ActiveRecord and ExistingRecord.
    ActiveRecord is intended to store data from experiments in progress.
    ExistingRecord is intended to read data files

    Comments:

    * A DataRecord object will keep track of an arbitrary number of scalar
      variables ("columns").

    * Data are stored in fixed-length deques, so that the ammount of
      memory required does not increase over time during long measurements.

    * Data and metadata are automatically written out at regular intervals
      so that if the measurement is interrupted, minimal data is lost. Data
      files are automatically named to avoid overwriting data.

    * Each measurement is associated with an auto-generated timestamp.
      The auto_generated timestamp can be overriden by calling self.update
      with the timestamp argument. Timestamps can also be disabled by
      initializing with auto_timestamps = False.

    * The [] operator is overloaded, and allows access to the most recent
      measurement

    """

    def __init__(
        self,
        columns: list[str],
        maxlen: int,
        output_dir: str,
        minlen: int,
        auto_timestamps: bool = True,
        sep: str = ',',
        repo_path: str = None,
    ):
        """
        Initialize a DataRecord object.

        Parameters
        ----------
        columns : list[str]
            Names of variables tracked by the DataRecord object.
            list of strings.

        maxlen : int
            Maximum length of the data record in samples.

        output_dir : str
            Directory where data are stored.

        minlen : int
            Minimum length of data record. Used to ensure recent history is
            available to measurement program.

        auto_timestamps : bool, optional
            If True, automatically assign timestamps to data points when
            update() is called. The default is True.

        sep : str, optional
            Delimiter for output CSV files. The default is ","

        repo_path: str, optional
            path to the git repository. If none, use default path.

        Returns
        -------
        None.
        """
        self.columns = columns
        """list[str]: List of colum names."""

        self.output_dir = output_dir
        """str: Directory where data are stored."""

        self.sep = sep
        """str: delimiter for output CSV files."""

        self.repo_path = None
        """str: path to git repository."""

        if repo_path is None:
            self.repo_path = DEFAULT_REPO_PATH

        else:
            self.repo_path = repo_path

        # init timer
        self.time_zero = None
        """float: Timestamp corresponding to the start of the experiment"""

        self.auto_timestamps = auto_timestamps
        """bool: If True, automatically assign timestamps to data points when
        update() is called."""

        # initialize data structures
        self.maxlen = maxlen
        """int: Maximum length of the data record in samples."""

        self.minlen = minlen
        """int: Minimum length of data record. Used to ensure recent history is
        available to measurement program."""

        self.current_index = 0
        """int: Index of current measurement."""

        # keep track of most recent entry so that getitem will work even if all
        # of the data was recently written to a file.
        self._most_recent_entry = {}

        self.timestamps = {}
        """dict[str, deque[float]]: Keys correspond to "columns" attribute.
        Each entry is a deque of timestamps associated with measurements."""

        self.counters = {}
        """dict[str, deque[int]]: Keys correspond to "columns" attribute.
        Each entry is a deque of indices associated with measurements."""

        self.record = {}
        """dict[str, deque[float]]: Keys correspond to "columns" attribute.
        Each entry is a deque of values associated with measurements."""

        # always have a column called "index"
        # print(self, columns, maxlen, output_dir, auto_timestamps, sep)

        self.indices = collections.deque(maxlen=maxlen)
        """deque[int]: contains indices of all measuerments"""

        for column in columns:
            self.record[column] = collections.deque(maxlen=maxlen)
            self.counters[column] = collections.deque(maxlen=maxlen)
            self._most_recent_entry[column] = None

            if self.auto_timestamps:
                self.timestamps[column] = collections.deque(maxlen=maxlen)

        # count how many output files have been written
        self.file_counter = 0
        """int: Counts the number of files that have been written."""

        # make sure the data record was initiallized correctly
        assert self.maxlen > 0

        self.update_queue = queue.PriorityQueue()

    def update(self, column: str, value: float, timestamp: float = None):
        """
        Record measurement data.

        Appends data to specified column, writes data to file when the record
        reaches a length of self.maxlen.

        Parameters
        ----------
        column : str
            Name of column to append data to.

        value : float
            data to append to column.

        timestamp : float, optional
            If None, use result of self.get_time(). Caution: when using this
            argument, the user is responsible for ensuring that these
            timestamps are ordered. The default is None.

        Returns
        -------
        None.
        """
        # first, ensure that d) len(indices) <= maxlen.
        # if len(indices) == maxlen, call output(), which will
        # write the contents of the record to a file and empty the recod
        if len(self.indices) == self.maxlen:
            self.output()

        if timestamp is None and self.auto_timestamps:
            timestamp = self.get_time()

        # This method should be the only place where record.append() is called
        # invariants: insure that
        # a) indices[-1] == current_index
        # b) counters[key] <= current_index for all key
        # c) len(counters[key]) <= len(indices)
        # d) len(indices) <= maxlen
        # e) indices[0] <= counters[key][0] for all key

        # Whenever you add a new value to a record,
        # first check to see if counters[key] == current_index
        # if yes, increment current_index, add current_index to indices,
        # If no, do not update current_index or indices
        #
        # In either case, after updating current_index and indicies (or not)
        # always add data to record[key], add current_index to counter[key]

        # now ensure
        # a) self.indices[-1] == self.current_index
        #
        # If this is the first data point, or the record was just cleared,
        # then indicies may be empty, so in that case a) is not True
        if len(self.indices) == 0:
            self.indices.append(self.current_index)

        # now ensure
        # b) counters[key] <= current_index for key
        # c) len(counters[key]) <= len(indices)
        # by advancing the current index if necessary
        elif (
            len(self.counters[column]) > 0
            and self.counters[column][-1] == self.current_index
        ):
            self.current_index += 1
            self.indices.append(self.current_index)

        self.counters[column].append(self.current_index)
        self.record[column].append(value)
        self._most_recent_entry[column] = value

        if self.auto_timestamps:
            self.timestamps[column].append(timestamp)

        # check invariants
        assert self.indices[-1] == self.current_index  # a)
        assert self.counters[column][-1] <= self.current_index  # b)
        assert len(self.counters[column]) <= len(self.indices)  # c)
        assert len(self.indices) <= self.maxlen  # d)

    def array_update(self, column: str, values: iter, timestamps: iter):
        """
        Update a data column with an array.

        Parameters
        ----------
        column : str
            Column to add to.
        values : iter
            Data values to add to.
        timestamps : iter
            Timestamps of values.

        Returns
        -------
        None.

        """
        for i in range(len(timestamps)):
            self.update(column, values[i], timestamp=timestamps[i])

    def output(self, write_recent_data: bool = False):
        """
        Manage length of the internal data structures.

        This version of output does not save data to a file. It only maintains
        the length of the record while also maintaining the invariants.

        Please overload this method if you want to actually save data.

        Parameters
        ----------
        write_recent_data : bool, optional
            If False, the most recent self.minlen samples are retained in the
            record and not written to file.

            If True, all data in the record are written to file, so that the
            record is empty after this method is called.

            The default is False.

        Returns
        -------
        None.
        """
        # This method should be the only place where record.pop() or
        # record.popleft() is called
        # invariants: insure that
        # a) indices[-1] == current_index
        # b) counters[key][-1] <= current_index for all key
        # c) len(counters[key][-1]) <= len(indices)
        # d) len(indices) < maxlen
        # e) indices[0] <= counters[key][0] for all key

        # determine how much of the record we want to keep
        record_length_after_write = None
        if write_recent_data is True:
            record_length_after_write = 0

        if write_recent_data is False:
            record_length_after_write = self.minlen

        keys = list(self.record.keys())

        while len(self.indices) > record_length_after_write:
            current_index = self.indices.popleft()
            # out_str = str(current_index)
            for key in keys:
                # assert current_index<=self.counters[key][0]
                if (
                    len(self.counters[key]) > 0
                    and current_index == self.counters[key][0]
                ):
                    self.counters[key].popleft()

                    if self.auto_timestamps:
                        # timestamp = self.timestamps[key].popleft()
                        self.timestamps[key].popleft()

                    # value = self.record[key].popleft()
                    self.record[key].popleft()

        # check invariants
        for key in keys:
            assert (
                len(self.indices) == 0 or self.indices[-1] == self.current_index
            )  # a)

            assert (
                len(self.counters[key]) == 0
                or self.counters[key][-1] <= self.current_index
            )  # b)

            assert len(self.counters[key]) <= len(self.indices)  # c)
            assert len(self.indices) <= self.maxlen  # d)

    def stage_update(self, column: str, values: np.ndarray, timestamps: np.ndarray):
        """
        Add a timeseries to the batch update queue.

        Parameters
        ----------
        column : str
            Name of column to append data to.

        values : np.ndarray
            list of values to append

        timestamps : float, optional
            Timestamps associated with values.

        Returns
        -------
        None.

        """
        for i, timestamp in enumerate(timestamps):
            new_item = update_queue_item(column, values[i], timestamp)
            self.update_queue.put(new_item)

    def batch_update(self):
        """
        Clear batch update queue.

        Returns
        -------
        None.
        """
        while True:
            try:
                item = self.update_queue.get(block=False)
                self.update(item.column, item.value, item.timestamp)
            except queue.Empty:
                break

    def __getitem__(self, key: str) -> float:
        """
        Retrieve most recent appended value of a given column.

        Parameters
        ----------
        key : str
            Column to retrieve value from.

        Returns
        -------
        float
            Most recent appended value.

        """
        retval = self._most_recent_entry[key]
        return retval

    def get_time_series(
        self,
        column: str,
        t_min: float = None,
        t_max: float = None,
        delta_t: float = None,
    ) -> tuple:
        """
        Make timeseries data for a given variable.

        Parameters
        ----------
        column : str
            the column that you want to convert to timeseries data

        t_min : float, optional
            Only return data that was measured later than this time.
            If None, use the earliest available time.
            The default is None.

        t_max : float, optional
            Only return data that was measured earlier than this time.
            If None, use the latest available time.
            The default is None.

        delta_t : float, optional
            If not None, resample data with time interval delta_t. The function
            does not interpolate, but rather uses the most recent past value.
            The default is None.

        Raises
        ------
        record_empty
            Raised if an index error occurs when self.timestamps[column][0]
            is accessed.

        Returns
        -------
        tuple[DataArray, DataArray]
            (times, values)

            times : numpy array of floats
                timestamps of samples

            values : numpy array of floats
                values from column
        """
        # Make working copies of all relevant data
        # Deques are optimized for reading/writing at the ends, rather than
        # random access. With copies, we can use pop() and not worry about
        # affecting the state of the record. Note that since we are making
        # shallow copies, the memory cost is low.

        times = self.timestamps[column].copy()
        values = self.record[column].copy()

        # determine if data is empy, if not, determine t_min and t_max
        data_exists = len(times) > 0 and len(values) > 0
        if data_exists:
            if t_min is None or t_min < times[0]:
                t_min = times[0]

            if t_max is None or t_max > times[-1]:
                t_max = times[-1]

        out_times = []
        out_values = []

        if delta_t is None:
            try:
                time_in_range = times[0] < t_max

            except IndexError as record_empty:
                print('Probably, the record is empty.')
                raise record_empty

            while data_exists and time_in_range:
                time = times.popleft()
                value = values.popleft()
                if time >= t_min and time <= t_max:
                    out_times.append(time)
                    out_values.append(value)

                data_exists = len(times) > 0 and len(values) > 0
                time_in_range = time < t_max

        if delta_t is not None:
            sample_time = t_min
            time = -float('inf')
            time_in_range = times[0] < t_max

            while data_exists and time_in_range:
                if time < sample_time:
                    time = times.popleft()
                    value = values.popleft()

                if time >= sample_time and time <= t_max:
                    out_times.append(sample_time)
                    out_values.append(value)
                    sample_time += delta_t

                data_exists = len(times) > 0 and len(values) > 0
                time_in_range = time < t_max

        out_times = np.array(out_times)
        out_values = np.array(out_values)

        return TimeSeries(out_times, out_values)

    def get_conditional_data(
        self, columns: list, condition: Callable[[Index, DataArray, DataArray], bool]
    ) -> tuple[IndexArray, DataArray, DataArray]:
        """
        Return the rows that satisfy a given condition.

        * Each row is evaluated independently
        * Missing values are populated with NaN

        Parameters
        ----------
        columns : list of str
            Specifies which colums to export.

        condition : Callable[[Index, DataArray, DataArray], bool]
            If True, append data to output.

        Returns
        -------
        tuple[IndexArray, DataArray, DataArray]
            (indicies, times, values)

            indices : numpy array of ints
                indices of the samples.

            times : dict of numpy arrays of floats
                timestamps of samples, indexed by column

            values : dict of numpy array of floats
                values from column, indexed by column
        """
        counters = {}
        record = {}

        if self.auto_timestamps:
            times = {}

        # Make working copies of all relevant data
        # Deques are optimized for reading/writing at the ends,rather than
        # random access. With copies, we can use pop() and not worry about
        # affecting the state of the record. Note that since we are making
        # shallow copies, the memory cost is low.

        indices = self.indices.copy()
        for column in columns:
            record[column] = self.record[column].copy()
            counters[column] = self.counters[column].copy()

            if self.auto_timestamps:
                times[column] = self.timestamps[column].copy()

        # initialize output
        out_index = []
        out_values = {}

        if self.auto_timestamps:
            out_times = {}

        for column in columns:
            out_values[column] = []

            if self.auto_timestamps:
                out_times[column] = []

        data_exists = True

        # temp variables that will be used to build output
        temp_index = 0
        temp_time_row = np.zeros(len(columns))
        temp_value_row = np.zeros(len(columns))

        while data_exists:
            if len(indices) > 0:
                temp_index = indices.popleft()

            else:
                data_exists = False
                continue

            for i, column in enumerate(columns):
                # missing data is nan
                temp_time_row[i] = float('nan')
                temp_value_row[i] = float('nan')

                if len(counters[column]) == 0:
                    continue

                # peek to see if index of column is up to date.
                counter = counters[column][0]
                assert counter >= temp_index

                if temp_index == counter:
                    if self.auto_timestamps:
                        time = times[column].popleft()

                    value = record[column].popleft()
                    counters[column].popleft()

                    temp_time_row[i] = time
                    temp_value_row[i] = value

                good = condition(temp_index, temp_time_row, temp_value_row)

                if not good:
                    continue

                # add data to output
                for i, column in enumerate(columns):
                    out_index.append(temp_index)
                    out_values[column].append(temp_value_row[i])

                    if self.auto_timestamps:
                        out_times[column].append(temp_time_row[i])

        out_index = np.array(out_index)
        for column in columns:
            out_values[column] = np.array(out_values[column])

            if self.auto_timestamps:
                out_times[column] = np.array(out_times[column])

        if not self.auto_timestamps:
            out_times = None

        return out_index, out_times, out_values


class ExistingRecord(DataRecord):
    """
    ExistingRecord is derived from DataRecord.

    An ExistingRecord object reads files created by ActiveRecord.
    """

    def __init__(
        self,
        file_path: str,
        output_dir: str = None,
        maxlen: int = None,
        minlen: int = None,
    ):
        """
        Initialize ExistingRecord object.

        Parameters
        ----------
        file_path : str
            Full path to metadata file.

        output_dir : str, optional
            Directory where data is stored. If None, determine from metadata
            file. The default is None.

        maxlen : int, optional
            Maximum length of record. If None, infer from metadata file.
            The default is None.

        minlen : int, optional
            Minimum length of record. If None, set to maxlen.
            The default is None.

        Returns
        -------
        None.

        """
        columns = []
        self.time_zero = None
        self.auto_timestamps = None
        self.maxlen = None
        self.current_file = None
        self.metadata = {}
        self.metadata_filepath = dirname(file_path)

        with open(file_path) as f:
            lines = f.readlines()
            for line in lines:
                # I added an expunge for the extra commas that excel will add if you save.
                # The added part is strip. I also moved the \n removal to the very top; if you need that in your config file
                # I can find something else, or you can do \\nn as a workaround
                line = line.replace('\n', '')
                split_line = line.strip(',').split(',')
                key = split_line[0]
                value = ','.join(split_line[1::])
                self.metadata[key] = value
            self.file_counter = int(self.metadata['file_counter'])
            self.time_zero = float(self.metadata['time_zero'])

            column_number = int(self.metadata['column_number'])
            for i in range(column_number):
                columns.append(self.metadata['column_' + str(i)])

            self.files = []
            for i in range(self.file_counter):
                self.files.append(self.metadata['file_' + str(i)])

            if output_dir is None:
                output_dir = self.metadata['output_dir']

            if maxlen is None:
                maxlen = int(self.metadata['maxlen'])

            if minlen is None:
                minlen = maxlen

        DataRecord.__init__(self, columns, maxlen, output_dir, minlen)

        self.file_index = 0
        self.file = open(
            validate_path(
                self.output_dir + self.files[0],
                check_dirs=self.metadata_filepath,
                accept_duplicates=True,
            )
        )
        self.read_header()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.file.close()

    def read_header(self):
        """
        Read the header of the current file and enumerate columns.

        Returns
        -------
        None.
        """
        line = self.file.readline()
        self.header = {}
        for i, column_name in enumerate(line.split(self.sep)):
            new_name = column_name.replace('\n', '')
            self.header[new_name] = i

    def read_next_line(self) -> bool:
        """
        Read one line of data from the input file, and adds it to record.

        Returns
        -------
        bool
            True if the line was successfully read.
        """
        new_line = self.file.readline()

        if not new_line:
            self.file_index += 1

            if self.file_index == len(self.files):
                return False

            else:
                self.file.close()
                self.file = open(
                    validate_path(
                        self.output_dir + self.files[self.file_index],
                        check_dirs=self.metadata_filepath,
                        accept_duplicates=True,
                    )
                )
                self.read_header()
                new_line = self.file.readline()

        values = []
        for x in new_line.split(self.sep):
            try:
                values.append(float(x))

            except ValueError:
                assigned = False
                if x.lower() == 'false':
                    values.append(False)
                    assigned = True

                if x.lower() == 'true':
                    values.append(True)
                    assigned = True

                if not assigned:
                    values.append(x)

        for column in self.columns:
            value = values[self.header[column]]
            timestamp = values[self.header[column + '_timestamp']]

            if type(value) is float and np.isnan(value):
                continue

            if self.auto_timestamps:
                self.update(column, value, timestamp)

            else:
                self.update(column, value)

        return True

    def batch_read(self, columns_list: list[str] = None) -> dict[str, tuple]:
        """
        Read the entirety of DataRecord at once.

        The output is a in a dictionary of tupled timeseries. This method uses
        pandas as backend for reading and parsing files. So, it has no effect
        on the state of the object.

        Parameters
        ----------
        columns_list : list[str], optional
            either None (returns every column in record) or list of strings of
            columns to return. The default is None.

        Returns
        -------
        dict[str, tuple]
            {column: (timestamp,value)}
        """
        # use all columns if none specified
        if columns_list is None:
            columns_list = self.columns

        # init output dictionary of list of np.arrays 0=time,1=values
        ts = {}
        for c in columns_list:
            ts[c] = [np.array([], float), np.array([], float)]

        for f in self.files:
            df = pd.read_csv(
                validate_path(
                    self.metadata['output_dir'] + f,
                    check_dirs=self.metadata_filepath,
                    accept_duplicates=True,
                )
            )
            # drop NaN rows and for each columns and append to ts

            for c in columns_list:
                ts_c = df[[c, c + '_timestamp']].dropna()
                ts[c][0] = np.append(ts[c][0], ts_c[c + '_timestamp'].to_numpy())

                ts[c][1] = np.append(ts[c][1], ts_c[c].to_numpy())

        # convert to dictionary of tuples for consistency with rest of
        # datarecord
        for c in columns_list:
            ts[c] = TimeSeries(ts[c][0], ts[c][1])

        return ts


class LegacyRecord(DataRecord):
    """
    LegacyRecord is derived from DataRecord.

    Similar to ExistingRecord, it reads data from csv files.
    Unlike ExistingRecord, it can read any csv, not just ones written by
    an ActiveRecord object.
    """

    def __init__(
        self,
        data_file_path: str,
        output_dir: str,
        maxlen: int,
        minlen: int,
        missing_data: str = '',
        sep: str = ',',
    ):
        """
        Initialize ExistingRecord object.

        Parameters
        ----------
        data_file_path : str
            Path to first data file relative to output_dir.
            The data columns are inferred from this file's header

        output_dir : str
            Working directory.

        maxlen : int
            Maximum length of record.

        minlen : int
            Minimum length of record.

        missing_data : str, optional
            string that represents missing data in input file
            The default is ''.

        sep : str, optional
            delimeter in input files
            The default is ','.

        Returns
        -------
        None.

        """
        self.missing_data = missing_data
        self.sep = sep
        self.output_dir = output_dir
        self.time_zero = None
        self.current_file = None
        self.missing = missing_data
        self.metadata = {}
        self.file_counter = 0
        self.time_zero = None

        self.files = []
        self.add_file(data_file_path)

        self.file_index = 0
        self.file = open(self.output_dir + self.files[0])
        columns = self.read_header(data_file_path)
        column_number = len(columns)
        self.metadata['column_number'] = column_number

        DataRecord.__init__(
            self, columns, maxlen, output_dir, minlen, auto_timestamps=False
        )

    def read_header(self, data_file_path: str) -> list[str]:
        """
        Read header.

        Parameters
        ----------
        data_file_path : str
            full path to data file

        Returns
        -------
        list[str]
            List of column names.
        """
        line = self.file.readline()
        self.header = {}

        for i, column_name in enumerate(line.split(self.sep)):
            new_name = column_name.replace('\n', '')
            self.header[new_name] = i

        return list(self.header.keys())

    def add_file(self, file_name: str):
        """
        Append in_file.

        Parameters
        ----------
        file_name : str
            Full path to data

        Returns
        -------
        None.

        """
        self.metadata['file_' + str(self.file_counter)] = file_name
        self.files.append(file_name)
        self.file_counter += 1
        self.metadata['file_counter'] = str(self.file_counter)

    def read_next_line(self) -> bool:
        """
        Read one line of data from the input file, and adds it to record.

        Returns
        -------
        bool
            True if the line was successfully read.

        """
        new_line = self.file.readline()

        if not new_line:
            self.file_index += 1

            if self.file_index == len(self.files):
                return False

            else:
                self.file.close()
                self.file = open(self.output_dir + self.files[self.file_index])
                self.read_header()
                new_line = self.file.readline()

        values = []

        for x in new_line.split(self.sep):
            try:
                values.append(float(x))

            except ValueError:
                assigned = False
                if x == 'False':
                    values.append(False)
                    assigned = True

                if x == 'True':
                    values.append(True)
                    assigned = True

                if not assigned:
                    values.append(x)

        for column in self.columns:
            value = values[self.header[column]]
            if value == self.missing:
                continue

            if self.auto_timestamps:
                timestamp = values[self.header[column + '_timestamp']]
                self.update(column, value, timestamp)

            else:
                self.update(column, value)

        return True


class ActiveRecord(DataRecord):
    """
    ActiveRecord is derived from DataRecord.

    An ActiveRecord stores and continually saves experimental data from
    measurements in progress.

    Additional Comments about of ActiveRecord:

    * Data files are automatically written. When the data is written to
      a file, it is automatically converted to a CSV format, where each
      column is a variable, each row is a measurement, and the rows are
      strictly time-ordered. It is not necessary to have the same number
      of entries for each column. Missing data is automatically populated
      with NaN.

    * A specified number of recent samples (self.minlen) are kept in memory
      for flow control. These samples can be written to a file and deleted
      from memory by calling self.output with write_recent_data = True.

    """

    def __init__(
        self,
        columns: list[str],
        maxlen: int,
        output_dir: str,
        minlen: str = 0,
        auto_timestamps: bool = True,
        sep: str = ',',
        meas_name: str = None,
        instruments: dict = None,
        stage_everything: bool = False,
    ):
        r"""
        Initialize an ActiveRecord object.

        Parameters
        ----------
        columns : list[str]
            Names of variables that will be recorded.

        maxlen : int
            Maximum number of samples to retain in memory.

        output_dir : str
            Directory where output data is written. Ends in "\\".

        minlen : str, optional
           Number of samples to be retained in memory after writing data to a
           file. The default is 0.

        auto_timestamps : bool, optional
            If True, maintain a list of timestamps for each column.The default
            is True.

        sep : str, optional
            Delimeter in output file. The default is ",".

        meas_name : str, optional
            If specified, output files will be named meas_name_x_y.csv,
            where x is a number (1,2,3,...) that is appended if neccessary
            to avoid overwriting existing data, and y is the index of the
            data file.

            If not specied (None): the meas_name will default to the date
            in YYYYMMDD format.

            The default is None.

        instruments: dict, optional
            dictionary w/ columns as keys and instruments as values. Each
            instrument is expected to have an info_dict attribute. If not None,
            will connect those column keys to instrument vaues in the metadata.

            The default is None.

        stage_everything : bool, optional
            If True, the setitem method adds updates to the update queue rather
            than directly updating the record. This behavior can be used to
            ensure updates are time-ordered in the output file. If True,
            batch_update must be called to update the record.

            The default is False.

        Returns
        -------
        None.
        """
        output_dir = Path(output_dir)
        if not output_dir.is_dir():
            raise FileNotFoundError('output_dir does not exist')
        output_dir = str(output_dir) + '/'

        # print("in ActiveRecord constructor")
        DataRecord.__init__(
            self, columns, maxlen, output_dir, minlen, auto_timestamps, sep
        )

        # initialze

        self.local_backups = None
        self.session_str = None
        self.metadata = {}
        self.init_metadata(meas_name)
        if instruments is not None:
            self.add_instruments(instruments)
        self.output_metadata()

        # automatically determine when time=0 is, and store relative timestamps
        self.time_zero = None
        self.init_timer()
        self.auto_timestamps = auto_timestamps

        # initialize data structures
        self.minlen = minlen

        # count how many output files have been written
        self.file_counter = 0

        # make sure the data record was initiallized correctly
        assert self.minlen >= 0
        assert self.maxlen > self.minlen

        self.stage_everything = stage_everything
        self.metadata_file_name = self.session_str + '_metadata.csv'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.output(write_recent_data=True)
        self.clean_backups()

    def output(self, write_recent_data: bool = False):
        """
        Write data to a file. Also writes metadata.

        Parameters
        ----------
        write_recent_data : bool, optional
            If False, the most recent self.minlen samples are retained in the
            record and not written to file.

            If True, all data in the record are written to file, so that the
            record is empty after this method is called.

            The default is False.

        Returns
        -------
        None.
        """
        # This method should be the only place where record.pop() or
        # record.popleft() is called
        # invariants: insure that
        # a) indices[-1] == current_index
        # b) counters[key][-1] <= current_index for all key
        # c) len(counters[key][-1]) <= len(indices)
        # d) len(indices) < maxlen
        # e) indices[0] <= counters[key][0] for all key

        # determine how much of the record we want to keep
        record_length_after_write = None
        if write_recent_data is True:
            record_length_after_write = 0

        if write_recent_data is False:
            record_length_after_write = self.minlen

        # name output file
        # maintain list of data files in metadata
        file_name = self.add_file()
        full_file_name = self.output_dir + file_name

        # determine header string
        sep = self.sep
        keys = list(self.record.keys())
        header_str = 'index'

        for key in keys:
            if self.auto_timestamps:
                header_str += sep + key + sep + key + '_timestamp'
            else:
                header_str += sep + key

        header_str += '\n'

        # write file
        file_available = True
        try:
            with open(full_file_name, 'w') as f:
                pass
        except Exception as e:
            file_available = False
            self.local_backups.mkdir(parents=True, exist_ok=True)
            self.metadata['local backups'] = self.local_backups
            new_full_file_name = str(self.local_backups / file_name)
            print('Couldnt open file at ', full_file_name, ' caught: \n', e)
            print('Saving to local backup instead at : \n', self.local_backups)
            full_file_name = new_full_file_name
        with open(full_file_name, 'w') as f:
            f.write(header_str)
            while len(self.indices) > record_length_after_write:
                current_index = self.indices.popleft()
                out_str = str(current_index)

                for key in keys:
                    # assert len(self.counters[key])>0 and
                    # current_index<=self.counters[key][0]

                    if (
                        len(self.counters[key]) > 0
                        and current_index == self.counters[key][0]
                    ):
                        self.counters[key].popleft()

                        if self.auto_timestamps:
                            timestamp = self.timestamps[key].popleft()

                        value = self.record[key].popleft()

                    else:
                        timestamp = float('nan')
                        value = float('nan')

                    if self.auto_timestamps:
                        out_str += sep + str(value) + sep + str(timestamp)

                    else:
                        out_str += sep + str(value)

                out_str += '\n'
                f.write(out_str)

        self.output_metadata(use_backup=not file_available)

    def get_time(self):
        """
        Get relative time.

        Returns
        -------
        float
            current relative time
        """
        return time.time() - self.time_zero

    def init_timer(self, time_zero: float = None):
        """
        Set time = 0 for relative timestamps.

        Parameters
        ----------
        time_zero : float, optional
            Timestamp of time = 0. If None, use result of time.time().
            The default is None.

        Returns
        -------
        None.
        """
        if time_zero is None:
            self.time_zero = time.time()

        else:
            self.time_zero = time_zero

        self.metadata['time_zero'] = self.time_zero

    def init_metadata(self, meas_name: str = None):
        """
        Populate self.metadata with the default metadata.

        Parameters
        ----------
        meas_name : str, optional
                If specified, output files will be named meas_name_x_y.csv,
                where x is a number (1,2,3,...) that is appended if neccessary
                to avoid overwriting existing data, and y is the index of the
                data file.

                If not specied (None): the meas_name will default to the date
                in YYYYMMDD format.

                The default is None

        Returns
        -------
        None.
        """
        self.metadata['local host'] = socket.gethostname()
        # initialize session string
        base_str = None
        if isinstance(meas_name, str):
            base_str = meas_name

        else:
            file_write_time = datetime.datetime.fromtimestamp(time.time(), tz=local_tz)
            date_str = file_write_time.strftime('%Y%m%d')
            base_str = date_str

        output_dir = self.output_dir
        file_list = [f for f in listdir(output_dir) if isfile(join(output_dir, f))]

        file_counter = 0
        session_str = base_str  # +"_"+str(file_counter)

        while session_str + '_metadata.csv' in file_list:
            session_str = base_str + '_' + str(file_counter)
            file_counter += 1

        self.session_str = session_str
        backup_attempts = 0
        while True:
            self.local_backups = LOCAL_BACKUPS / (
                self.session_str + '_' + str(backup_attempts)
            )
            if self.local_backups.is_dir():
                backup_attempts += 1
            else:
                break

        self.local_backups.mkdir(parents=True, exist_ok=False)

        # intialize metadata
        # check if working with source code:
        if (DEFAULT_REPO_PATH / 'pyproject.toml').is_file():
            try:
                repo = Repo(DEFAULT_REPO_PATH)
                version = repo.working_tree_dir
                branch = repo.active_branch.name
                commit_hexsha = next(repo.iter_commits()).hexsha
                self.metadata['repo_dir'] = version
                self.metadata['branch'] = branch
                self.metadata['commit hexsha'] = commit_hexsha
            except Exception as e:
                print('Failed to read git Info due to : \n')
                print(e)
                self.metadata['repo_dir'] = 'N/A'
                self.metadata['branch'] = 'N/A'
                self.metadata['commit hexsha'] = 'N/A'
        self.metadata['version'] = get_version('rminstr')
        self.metadata['output_dir'] = output_dir
        # initialize as empty
        self.metadata['local backups'] = self.local_backups
        self.metadata['file_counter'] = self.file_counter
        self.metadata['output_dir'] = self.output_dir
        self.metadata['maxlen'] = self.maxlen

        self.metadata['column_number'] = len(self.columns)
        for i, column in enumerate(self.columns):
            self.metadata['column_' + str(i)] = column

    # TODO: different experiments/programs keep track of this data in different
    # ways. This will cause problems later.
    def add_instruments(self, instr: dict):
        """
        Add instruments to metadata.

        Parameters
        ----------
        instruments :dict
            dictionairy containing instruments with info_dict attribute
            expected to be a dictionairy with columns as keys, and instruments
            as values. Each instrument is expected to have 'info_dict' as an
            attribute. If a 'range' is not in info dict, it will not be saved.

        """
        for col in instr:
            assert col in self.columns
            try:
                self.metadata[col + '_model'] = instr[col].info_dict['model']
            except KeyError:
                self.metadata[col + '_model'] = instr[col].info_dict['model_number']
            try:
                self.metadata[col + '_serial'] = instr[col].info_dict['serial']
            except KeyError:
                self.metadata[col + '_serial'] = instr[col].info_dict['serial_number']
            for key in instr[col].info_dict:
                if key != 'model' and key != 'serial':
                    self.metadata[col + '_' + key] = instr[col].info_dict[key]
        self.output_metadata()

    def add_file(self):
        """
        Increments file counter and maintains metadata.

        Determines name of next output file and adds the file to self.metadata
        with key "file_x", where x is the current value of file_counter.

        Returns
        -------
        file_name : str
            name of next output file.

        """
        file_name = self.session_str + '_' + str(self.file_counter) + '.csv'
        self.metadata['file_' + str(self.file_counter)] = file_name
        self.file_counter += 1
        self.metadata['file_counter'] = str(self.file_counter)
        return file_name

    def output_metadata(self, use_backup: bool = False):
        """
        Write metadata to a file.

        Parameters
        ----------
        use_backup : bool, optional
            If True, saves to local backup (~/rminstr/self.session_str).
            The default is False.

        Returns
        -------
        None.

        """
        print('writing metadata')
        backup_file_path = self.local_backups / (self.session_str + '_metadata.csv')
        if use_backup:
            file_path = backup_file_path
        else:
            file_path = self.output_dir + self.session_str + '_metadata.csv'

        try:
            with open(file_path, 'w') as outfile:
                for item in self.metadata.items():
                    key, value = item
                    outfile.write(key + ',' + str(value) + '\n')

        except PermissionError as e:
            print('Warning: Could not write metadata, caught: \n', e)

    def check_missing_files(self) -> list[Path]:
        """
        Check if any files are missing from the target directory.

        Returns
        -------
        list[Path]
            List of paths expected to be in target directory.

        """
        missing = []
        for i in range(self.file_counter):
            file = Path(self.output_dir) / (self.session_str + '_' + str(i) + '.csv')
            if not file.is_file():
                missing.append(str(file.resolve()))
        return missing

    def clean_backups(self):
        """
        Clean up backups at the end of an experiment.

        Combines the backup directory with the target directory.
        If it cant, adds a noe to the metadata that this step failed, which
        will notify users trying to read data with this flag down the road.

        Returns
        -------
        None.

        """

        if self.local_backups.is_dir():
            for file in listdir(self.local_backups):
                if (
                    not (Path(self.output_dir) / file).is_file()
                    and 'metadata' not in file
                ):
                    try:
                        shutil.copy(
                            self.local_backups / file, Path(self.output_dir) / file
                        )
                    except Exception as e:
                        print('Couldnt copy backups to target, caught :\n', e)
                        print('Manually merge backup directory with target.')
                        return

            # look for the newest metadata file
            backup_metadata = self.local_backups / self.metadata_file_name
            if backup_metadata.is_file():
                target_metadata = Path(self.output_dir) / self.metadata_file_name
                backup_mtime = getmtime(backup_metadata)
                target_mtime = getmtime(target_metadata)
                if backup_mtime > target_mtime:
                    # rename old metadata
                    cnt = 0
                    while True:
                        newname = Path(self.output_dir) / (
                            self.metadata_file_name.replace(
                                '.csv', '_OUTDATED_' + str(cnt) + '.csv'
                            )
                        )
                        if newname.is_file():
                            cnt += 1
                        else:
                            break
                    rename(target_metadata, newname)
                    shutil.copy(backup_metadata, target_metadata)

    def __setitem__(self, key: str, value: float):
        """
        Call self.update with default timestamp.

        Parameters
        ----------
        key : str
            column to be updated.
        value : float
            new data to append.

        Returns
        -------
        None.

        """
        if self.stage_everything:
            self.update(key, value)

        else:
            self.stage_update(key, [value], [self.get_time()])
