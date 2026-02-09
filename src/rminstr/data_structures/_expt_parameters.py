"""ExptParameters module."""

import builtins
import pandas as pd
import numpy as np
from typing import Union
from os.path import basename
import math
import copy

__all__ = ['ExptParameters', 'ExptParametersReadError', 'get_config_as_dictionary', 'save_dictionary_as_config']


class ExptParametersReadError(Exception):
    """Exception raised for reading ExptParameters.

    Attributes:
        message -- explanation of the error

    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ExptParameters:
    r"""
    The ExptParameters class keeps track of experimental settings.

    Users specify two files used to describe how a program will run.

    * config_file: contains information that never changes over the duration of
      an experiment. ex. instrument GPIB addresses, VNA IFBW. See below for
      formatting information.

    * run_settings_file: a spreadsheet of values specifying measurements that
      occur sequentially.ex. frequencies, power levels Each row represents a
      measurement. Each column represents a variable.

    The ExptParameters object can be read like a dictionary. For example:

        params = ExptParameters("C:\examples\\", config.csv", "run.csv")
        print(params["VNA_IFBW"])

    These variables are read-only, so

        params["VNA_IFBW"] = 10

    does not work.


    For run settings, the ExptParameters object keeps track of the index of
    the current data point. So, params["Frequency"] will return a number,
    rather than a list. To get the next Frequency point, call params.advance().
    """

    def __init__(
        self,
        config_files: Union[str, list[str]],
        run_settings_file: str = None,
        initial_dict: dict = None,
        config_file_priority: list[int] = None,
        header: int = 0,
        columns: list[str] = None,
        column_types: list[str] = None,
    ):
        """
        Initialize an ExptParameters object.

        Parameters
        ----------
        config_files : Union[str, list[str]]
            If the value is a string, it is interpreted as the path to the
            config file.

            If as list of strings is given, each entry is interpreted as
            the path to a config file. Each config file is read in the order
            given in the list. If the same setting exists in multiple config
            files, use config_file_priority to determine which setting to use.

        run_settings_file : str
            Full path to run settings file

        initial_dict : dict
            A dictionary to use to initialize the config before adding additional csv files

        config_file_priority : list[int], optional
            Indicates the priority of the corresponding (by order) config
            file. Higher priority corresponds to lower numbers.If None,
            all files have equal priority. The default is None.

        header : int, optional
            Number of lines to discard when reading run_settings. The default
            is 0.

        columns : list[str], optional
            Names of columns in run settings file. The default is None.
            If None, first check config file. If that fails, check run file for
            column names

        column_types : list[str], optional
            Data types for columns in run settings. The default is None.
            If None, first check config file. If that fails, assume everything
            is a float.

        Returns
        -------
        None.

        """
        if config_file_priority is not None:
            print(
                "WARNING: The new version doesn't use config_file_priority, but it is not none coming in so it is being ignored"
            )

        if initial_dict is not None:
            self.config = dict(initial_dict)
        else:
            self.config = None

        self.add_config_files(config_files)
        """dict: Stores experiment configuration"""

        self.columns = columns
        """list[str]: the keys of run settings"""

        self.column_types = column_types
        """list[str]: the types of data stored in columns of run settings."""

        if self.columns is None and 'run_settings_columns' in self.config.keys():
            self.columns = self.config['run_settings_columns']['names']
            self.column_types = self.config['run_settings_columns']['types']

        self.index = None
        """int: Tracks progress through the steps given in run settings."""

        self.num_steps = None
        """int: number of rows in run settings file"""

        self.run_settings = None
        """dict[str, list]: stores run settings"""

        # I added this in because I want to use the config file reader without having to give it empty runsettings files
        if run_settings_file != None:  # noqa: E711
            self.load_run_settings(run_settings_file, header)

    def add_config_files(self, config_files):
        """
        Make a dictionary from config files

        Parameters
        ----------
        config_files : str or list(str)
            Path or a list of paths to the config files to load.

        Returns
        -------
        dict
            Dictionary of config files

        """
        data = []
        if self.config is None:
            self.config = {}

        if type(config_files) is not list:
            config_files = [config_files]

        for i in config_files:
            data.append(
                pd.read_csv(i, sep=',', comment='#').dropna(
                    how='all', ignore_index=True
                )
            )

        for h in range(0, len(data)):
            for i in range(0, len(data[h])):
                try:
                    df_slice = data[h].loc[i]
                    df_slice_keys = df_slice.loc[
                        (
                            (data[h].columns != 'comment')
                            & (data[h].columns != 'comments')
                        )
                        & (data[h].columns != 'value')
                        & (data[h].columns != 'type')
                    ]
                    value = df_slice.loc['value']
                    cast_type = df_slice.loc['type']

                    key_value_array = df_slice_keys.loc[df_slice_keys.index].to_numpy()
                    # non_nan_index = [math.isnan(key_value_array[i]) for i in range(0, len(key_value_array))]
                    non_nan_index = []
                    for i in range(0, len(key_value_array)):
                        try:
                            isnan = math.isnan(key_value_array[i])
                            non_nan_index.append(not isnan)
                        except TypeError:
                            non_nan_index.append(True)

                    # handles if there is a comment but no keys. If there are keys and no values it will not catch here
                    if any(non_nan_index):
                        if cast_type == 'bool':
                            value = bool(value.lower() == 'true')

                        # if the value is int and has scientific notation, casting to int
                        # fails. Casting to float first fixes
                        elif cast_type == 'int':
                            value = float(value)

                        try:
                            casted_value = getattr(builtins, cast_type)(value)

                        except AttributeError:  # maybe it's a numpy type
                            casted_value = getattr(np, cast_type)(value)

                        df_slice_keys_nonan = df_slice_keys.loc[
                            df_slice_keys.index[non_nan_index]
                        ]

                        j = -1

                        temp_dict = self.config

                        for j in range(0, len(df_slice_keys_nonan) - 1):
                            try:
                                temp_dict = temp_dict[
                                    df_slice_keys_nonan.loc[
                                        df_slice_keys_nonan.index[j]
                                    ]
                                ]
                            except KeyError:
                                temp_dict[
                                    df_slice_keys_nonan.loc[
                                        df_slice_keys_nonan.index[j]
                                    ]
                                ] = {}
                                temp_dict = temp_dict[
                                    df_slice_keys_nonan.loc[
                                        df_slice_keys_nonan.index[j]
                                    ]
                                ]

                        j = j + 1

                        try:
                            temp_dict[
                                df_slice_keys_nonan.loc[df_slice_keys_nonan.index[j]]
                            ]  # this will break the try statement if the key isnt in yet
                            if (
                                type(
                                    temp_dict[
                                        df_slice_keys_nonan.loc[
                                            df_slice_keys_nonan.index[j]
                                        ]
                                    ]
                                )
                                is not list
                            ):
                                temp_dict[
                                    df_slice_keys_nonan.loc[
                                        df_slice_keys_nonan.index[j]
                                    ]
                                ] = [
                                    temp_dict[
                                        df_slice_keys_nonan.loc[
                                            df_slice_keys_nonan.index[j]
                                        ]
                                    ]
                                ]

                            if type(
                                temp_dict[
                                    df_slice_keys_nonan.loc[
                                        df_slice_keys_nonan.index[j]
                                    ]
                                ][0]
                            ) != type(casted_value):
                                print(
                                    'WARNING: list with keys '
                                    + str(
                                        temp_dict[
                                            df_slice_keys_nonan.loc[
                                                df_slice_keys_nonan.index[j]
                                            ]
                                        ]
                                    )
                                    + " has mismatching types. It'll work, but beware"
                                )
                            temp_dict[
                                df_slice_keys_nonan.loc[df_slice_keys_nonan.index[j]]
                            ].append(casted_value)
                        except KeyError:
                            temp_dict[
                                df_slice_keys_nonan.loc[df_slice_keys_nonan.index[j]]
                            ] = casted_value

                    # if something fails, insert a message about where in the file it
                    # failed so its not a pain to debug the config file
                except Exception as e:
                    msg = f'\nExptParametersReadError occured @ {basename(config_files[i])} : \n{data[h].loc[i]} :\n'
                    msg += f'Caught Exception: {str(type(e).__name__)}: {e}'
                    raise ExptParametersReadError(msg) from e

    def load_run_settings(self, in_file, header: int = 0):
        """
        Load run settings.

        Parameters
        ----------
        in_file : str
            Full path to run file

        header : int, optional
            Number of lines to ignore at top of file. The default is 0.

        Raises
        ------
        ValueError
            If Run settings column is duplicated in config file.

        Returns
        -------
        None.

        """
        run_settings_df = pd.read_csv(in_file, skiprows=header, comment='#')
        self.num_steps = len(run_settings_df.index)

        # print("is columns None?", self.columns)
        if self.columns is None:
            self.columns = list(run_settings_df.columns)
            # print("here", self.columns)

        if self.column_types is None:
            self.column_types = ['float'] * len(self.columns)

        # check that none of the items in config are already columns
        # check that all of the expected columns are present
        self.run_settings = []
        for i in range(self.num_steps):
            new_dict = {}

            for j, column in enumerate(self.columns):
                new_dict[column] = run_settings_df[column][i]

                if i == 0:
                    # this check is necessary because we can access data with __getitem__
                    if column in self.config.keys():
                        raise ValueError(
                            'Run settings column name duplicated in config file.'
                        )

                    self.config[column] = None
                    # self.config.add_data(getattr(builtins, self.column_types[j])(run_settings_df[column][i]))

            self.run_settings.append(new_dict)

    def save_run_settings(self, file_name: str):
        """
        Save run settings to file as csv.

        Parameters
        ----------
        file_name : str
            Full path to file.

        Returns
        -------
        None.

        """
        df = pd.DataFrame(self.run_settings)
        df.to_csv(file_name, sep=',', index=False, columns=self.columns)

    def save_config(self, file_name: str, output_format='CSV'):
        """
        Save config to file as csv.

        Parameters
        ----------
        file_name : str
            Full path to file.

        output_format : str, optional
            The format of the file. Options are CSV. The default is CSV.

        Returns
        -------
        None.

        """

        # This will not perserve order of the original file, but instead will clump things together
        def get_keys_values(keys, config, max_length):
            if type(config) == dict:
                keys_temp = None
                values = None
                for i in config:
                    if keys is None:
                        keys_in = [i]
                    else:
                        keys_in = keys + [i]
                    keys_out, value_out, max_length_out = get_keys_values(
                        keys_in, config[i], max_length
                    )
                    if max_length_out > max_length:
                        max_length = max_length_out
                    if type(value_out) is not list:
                        value_out = [value_out]
                    if keys_temp is None:
                        keys_temp = keys_out
                        values = value_out
                    else:
                        keys_temp = keys_temp + keys_out
                        values = values + value_out

                return keys_temp, values, max_length
            elif type(config) == list:
                keys_temp = [keys] * len(config)
                values = []
                for i in range(0, len(config)):
                    values.append(config[i])
                return keys_temp, values, max_length
            else:
                return [keys], config, len(keys)

        config_copy = copy.deepcopy(self.config)
        if self.columns is not None:
            for i in range(0, len(self.columns)):
                config_copy.pop(self.columns[i])

        keys, values, max_length = get_keys_values(None, config_copy, 0)

        column_names = []
        for i in range(0, max_length):
            column_names.append('key_' + str(i))

        column_names.append('value')
        column_names.append('type')

        for i in range(0, len(keys)):
            keys[i] = (
                keys[i]
                + [float('nan')] * (max_length - len(keys[i]))
                + [str(values[i])]
                + [str(type(values[i]).__name__)]
            )

        df = pd.DataFrame(keys)
        df.to_csv(file_name, sep=',', index=False, header=column_names)

        # because dictionaries do not have guaranteed order
        # columns = []
        # data = {}
        # for i in range(self.max_keys):
        #     key_name = "key_" + str(i)
        #     data[key_name] = []
        #     columns.append(key_name)

        # columns.append("value")
        # data["value"] = []

        # columns.append("type")
        # data["type"] = []

        # for entry in entries:
        #     keys, values = entry
        #     # values can be either lists or scalars
        #     # if it is a list, but we want to put every value in a row.

        #     if type(values) is not list:
        #         values = [values]

        #     for value in values:
        #         # populate keys
        #         for i in range(self.max_keys):
        #             key_name = "key_" + str(i)
        #             key = float('nan')
        #             if i < len(keys):
        #                 key = keys[i]

        #             data[key_name].append(key)

        #         data["value"].append(value)
        #         data["type"].append(type(value).__name__)

        # df = pd.DataFrame(data)
        # df.to_csv(file_name, sep=",", index=False, columns=columns)

    def get_column(self, column):
        """
        Get a column from run_settings.

        Parameters
        ----------
        column : str
            column to return

        Returns
        -------
        None.

        """
        out = np.zeros(self.num_steps)
        for i in range(self.num_steps):
            out[i] = self.run_settings[i][column]

        return out

    def advance(self):
        """
        Advance to the next row in run file.

        Returns
        -------
        None.
        """
        if self.index is None:
            self.index = 0
        else:
            self.index += 1

        if not self.complete():
            for column in self.columns:
                self.config[column] = self.run_settings[self.index][column]

    def complete(self):
        """
        Test if run is complete.

        Returns true if advance() has been called enough times to completely
        iterate through the run settings file, so that no more rows are
        available.

        Returns
        -------
        bool
            True if complete

        """
        return self.index not in range(self.num_steps)

    def __getitem__(self, key):
        """Fetch the value of a setting."""
        return self.config[key]

    def keys(self):
        """Get keys."""
        return self.config.keys()


def get_config_as_dictionary(config_files):
    ep = ExptParameters(config_files)
    return ep.config

def save_dictionary_as_config(dictionary, path):
    ep = ExptParameters([], initial_dict = dictionary)
    ep.save_config(path)
    
