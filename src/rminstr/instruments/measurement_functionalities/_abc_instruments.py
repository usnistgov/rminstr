# -*- coding: utf-8 -*-
"""
Abstract definitions of measurement functionalities.

Each class represents an abstraction of a measurement functionality.
Instruments which inherit a functionality are assumed to be interchangeable.
Their implementations should use the same syntax, and follow the same state
model.

"""

import abc
from rminstr.instruments.measurement_functionalities.state_models import (
    SetupOnly,
    Triggerable,
)


class ABC_Ammeter(Triggerable, abc.ABC):
    """
    Abstraction of a ammeter as a state machine.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': ['display'],
        'setup': ['nplc', 'i_range', 'num_readings', 'timer', 'measure_autozero'],
        'arm': ['delay', 'trigger_source'],
        'trigger': ['instruments'],
        'fetch_data': ['time_column_name', 'i_column_name', 'meas_start_time'],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        Triggerable.__init__(self, log_path=log_path)


class ABC_DCSubPowerMeter(Triggerable, abc.ABC):
    """
    Abstraction of a DC Substituted Power Meter as a state machine.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': ['sensor_type', 'panel', 'initial_source'],
        'setup': [
            'resistance_setpoint',
            'k_p',
            'k_i',
            'n_filter',
            'duration',
            'source_ubound',
            'source_lbound',
            'source',
            'source_level',
            'source_range',
            'source_ilimit',
            'measure_range',
            'measure_autozero',
            'over_voltage_protection',
            'nplc',
            'source_readback',
            'source_delay',
            'buffer_size',
            'buffer_fill_mode',
            'v0_cal',
            'vm_cal',
            'i0_cal',
            'im_cal',
            'trigger_var',
            'max_source_diff',
        ],
        'arm': ['delay', 'trigger_source', 'trigger_timeout', 'trigger_out'],
        'trigger': ['instruments'],
        'fetch_data': ['delete_buffer', 'meas_start_time', 'stop_measurement'],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        Triggerable.__init__(self, log_path=log_path)

    def close(self):
        """Close a dcsub power meter safely, should turn off the source."""
        self.setup(source_level=0)
        super().close()


class ABC_SignalGenerator(SetupOnly, abc.ABC):
    """
    Abstraction of a signal generator as a SetupOnly state machine.

    The class tracks state of instrument, and automatically stores settings
    when initialized and when setup is called.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': ['display', 'port'],
        'setup': [
            'f_GHz',
            'dBm',
            'source_on',
            'port',
            'AM',
            'AM_ext_port',
            'AM_ext_sensitivity_percent_per_volt',
            'AM_installed',
            'dBm_limit',
        ],
        'arm': [],
        'trigger': [],
        'fetch_data': [],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        SetupOnly.__init__(self, log_path=log_path)

    # most signal generators should close out this way
    def close(self):
        """Turn of a SignalGenerator on close."""
        self.state = 'unarmed'
        self.setup(source_on=False)
        super().close()


class ABC_ArmedSignalGenerator(Triggerable, abc.ABC):
    """
    Abstraction of an signal generator as a Triggerable state machine.

    The class tracks state of instrument, and automatically stores settings
    when initialized and when setup is called.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': ['display', 'list_file'],
        'setup': [
            'dBm',
            'f_GHz',
            'dBm_limit',
            'source_on',
            'AM',
            'AM_ext_port',
            'AM_ext_sensitivity_percent_per_volt',
            'pow_sweep_dBm',
            'freq_sweep_GHz',
            'time_sweep_micros',
        ],
        'arm': ['list_mode', 'trigger_source', 'output'],
        'trigger': [],
        'fetch_data': [],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        Triggerable.__init__(self, log_path=log_path)


class ABC_SMUSourceSweep(Triggerable, abc.ABC):
    """
    Abstraction of an SMU that can sweep between a list of source values.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.

    Attributes
    ----------
    wiring_congfigurations: tuple(str)
        Possible wiring options expected of an SMU. Use these as naming conventions for establishing
        the wiring setup on initializtion

    source_measure_configurations: tuple(str)
        Possible source-measure configurations, use these as naming conventions for establishing
        the source-measure configurations on initialization
    """

    acceptable_args = {
        'initial_setup': ['wiring', 'source_measure', 'panel'],
        'setup': [
            'source',
            'source_level',
            'source_range',
            'source_ilimit',
            'measure_range',
            'measure_autozero',
            'over_voltage_protection',
            'measure_for_duration_or_count',
            'duration_per_level',
            'initial_level_duration',
            'count_per_level',
            'nplc',
            'source_readback',
            'source_delay',
            'source_trigger_levels',
            'buffer_size',
            'buffer_fill_mode',
        ],
        'arm': ['delay', 'trigger_source', 'trigger_timeout', 'trigger_mode'],
        'trigger': ['delay', 'trigger_source', 'trigger_timeout', 'trigger_mode'],
        'fetch_data': ['delete_buffer', 'meas_start_time'],
    }

    def __init__(self, log_path: str = None):
        self.wiring_configurations = ('2W', '4W')
        self.source_measure_configurations = ('SVMV', 'SVMI', 'SIMI', 'SIMV')
        Triggerable.__init__(self, log_path=log_path)


class ABC_VoltageGenerator(SetupOnly, abc.ABC):
    """
    Abstraction of a voltage generator as a state machine.

    A voltage generator just outputs voltage. It does not measure anything.
    More complex behaviors should be modeled by another functionality.

    The class tracks state of instrument, and automatically stores settings
    when initialized and when setup is called.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': [],
        'setup': ['v_range', 'source_level'],
        'arm': [],
        'trigger': [],
        'fetch_data': [],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        SetupOnly.__init__(self, log_path=log_path)

    def close(self):
        """Turn off a VoltageGenerator on close."""
        self.setup(source_level=0)
        super().close()


# This is Triggerable since the LS155 is weird,
# And the Lakeshore 155 needs to use the wait_for_data_available command to make sure
# Python waits for the commands to finish before continuing
class ABC_CurrentGenerator(Triggerable, abc.ABC):
    """
    Abstraction of a current generator as a state machine.

    A current generator just outputs current. It does not measure anything.

    The class tracks state of instrument, and automatically stores settings
    when initialized and when setup is called.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': ['panel'],
        'setup': [
            'panel',
            'i_range',
            'i_limit',
            'over_voltage_protection',
            'current_level',
            'source',
            'other_commands',
        ],
        'arm': [],
        'trigger': [],
        'fetch_data': [],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        Triggerable.__init__(self, log_path=log_path)

    def close(self):
        """Turn off a current-generator on close."""
        self.setup(source=False)
        super().close()


class ABC_Voltmeter(Triggerable, abc.ABC):
    """
    Abstraction of a Voltmeter measurement functionality.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': ['display'],
        'setup': [
            'nplc',
            'v_range',
            'num_readings',
            'timer',
            'autozero',
            'extout_mode',
            'extout_polarity',
            'channel',
            'zero_now',
        ],
        'arm': ['delay', 'trigger_source'],
        'trigger': ['instruments'],
        'fetch_data': ['time_column_name', 'v_column_name', 'meas_start_time'],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        Triggerable.__init__(self, log_path=log_path)


class ABC_TemperatureController(SetupOnly, abc.ABC):
    """
    Abstraction of a temperature controller.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': [],
        'setup': [
            'loop',
            'loop_enabled',
            'loop_on_powerup',
            'loop_input',
            'heater_range',
            'mode',
            'setpoint',
            'setpoint_units',
            'sensor_input',
            'sensor_type',
            'sensor_units',
            'sensor_coefficient',
            'sensor_excitation',
            'sensor_range',
            'P',
            'I',
            'D',
            'assign_curve',
            'sensor_units',
        ],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        SetupOnly.__init__(self, log_path=log_path)


class ABC_EnvironmentLogger(Triggerable, abc.ABC):
    """
    Abstraction of an environment temperature/humidity logger.

    An environment logger records ambient humidity and temperature, and has
    fetchable data.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': [],
        'setup': ['temp_unit', 'channel'],
        'arm': [],
        'trigger': [],
        'fetch_data': [
            'since',
            'until',
            'verbose_download',
            'verbose_parse',
            'chunk_size',
        ],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        Triggerable.__init__(self, log_path=log_path)


class ABC_RFPowerMeter(Triggerable, abc.ABC):
    """
    Abstraction of an rf powermeter measurement functionality.

    Parameters
    ----------
    log_path : str, optional
        Path to save log of arguments passed to state model methods. No log if
        none saved. The default is None.
    """

    acceptable_args = {
        'initial_setup': [],
        'setup': [
            'read_units',
            'integration_time',
            'average_state',
            'zero_once',
            'trig_delay',
            'meas_freq_MHz',
            'cal_factor_percent',
            'read_range',
            'resolution',
            'averages',
            'zero_cal',
        ],
        'arm': ['delay', 'trigger_source'],
        'trigger': [],
        'fetch_data': ['p_column_name', 'v_column_name'],
    }

    def __init__(self, log_path: str = None):
        # inherit state model
        Triggerable.__init__(self, log_path=log_path)


class VNAParamError(ValueError):
    """Error raised when bad VNA parameters are passed."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ABC_VNA(Triggerable, abc.ABC):
    """
    Abstraction of a Vector Network Analyzer (VNA) measurement functionality.
    """

    acceptable_args = {
        'initial_setup': [],
        'setup': [
            'flist_GHz',
            'fstart_GHz',
            'fstop_GHz',
            'npoints',
            'sweep_type',
            'params',
            'power_dBm',
            'IFBW',
            'average',
        ],
        'arm': [],
        'trigger': [],
        'fetch_data': [],
    }

    valid_first = ['a', 'b', 'S']

    def __init__(self, log_path: str = None):
        Triggerable.__init__(self, log_path=log_path)

    def w2p_params(self, vna_port1: int, vna_port2: int) -> list[str]:
        """
        Generate 2-port wave parameter strings.

        Parameters
        ----------
        port1 : int
            VNA port number connected to device port 1.
        port2 : int
            VNA port number connected to device port 2..

        Returns
        -------
        list[str]
            List of parameters.

        """
        p1 = str(vna_port1)
        p2 = str(vna_port2)
        return [
            'a' + p1 + p1,
            'b' + p1 + p1,
            'a' + p2 + p1,
            'b' + p2 + p1,
            'a' + p1 + p2,
            'b' + p1 + p2,
            'a' + p2 + p2,
            'b' + p2 + p2,
        ]

    def validate_param(self, param: str):
        """Check a VNA parameter matches expectations."""
        if param[0] not in ABC_VNA.valid_first:
            raise VNAParamError(
                'Expected one of '
                + str(ABC_VNA.valid_first)
                + ' as first char for'
                + param
            )


# set up all for api
_loc = locals()
__all__ = [k for k, v in _loc.items() if 'ABC_' in k]
