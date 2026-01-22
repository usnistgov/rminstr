"""Anritsu MG3692A signal generator measurement functionality."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_SignalGenerator
from rminstr.instruments.communications import Instrument, InstrumentError


class SignalGenerator(Instrument, ABC_SignalGenerator):
    """Implementation of the Anritsu MG3692A as a signal generator."""

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize a signal generator object.

        Parameters
        ----------
        visa_address : str
            Visa address of instrument.

        resource_manager : visa.ResourceManager, optional
            Pyvisa resource manager for opening visa resources. The default is None.

        log_path : str, optional
            If provided, will log at the specified path. The default is None.

        Returns
        -------
        None.

        """
        # initialize as signal generator
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)
        Instrument.__init__(self, visa_resource)
        ABC_SignalGenerator.__init__(self, log_path=log_path)

        self.info_dict['model_number'] = 'Anritsu_MG3692A'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        self.default_setup_settings = {
            'dBm': -2,
            'f_GHz': 0.01,
            'dBm_limit': 0,
            'source_on': False,
        }

    # %% Initial and Normal Setup

    def initial_setup(self, **kwargs):
        """
        Set initial state of the machine.

        Parameters
        ----------
        other_commands : list, optional
            List of strings, commands to be sent directly to machine. The default is None.

        Returns
        -------
        None.
        """
        super().initial_setup(**kwargs)
        source_initstr = 'RF0; *RST;'
        self.write(source_initstr)
        self.state = 'init'

        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
        self.state = 'init'
        # pass through some other command, if you want to modify

    def setup(
        self,
        dBm: float = None,
        f_GHz: float = None,
        dBm_limit: float = None,
        source_on: bool = None,
        **kwargs,
    ):
        """
        Adjust settings on the machine.

        Parameters
        ----------
        dBm : float, optional
            Power level setting in dBm. The default is None.

        f_GHz : float, optional
            Frequency setting in GHz. The default is None.

        dBm_limit : float, optional
            Power level setting in dBm. The default is None.

        source_on : bool, optional
            Turns source on when True, off when False. The default is None.

        Returns
        -------
        None.

        """
        super().setup(
            dBm=dBm, f_GHz=f_GHz, dBm_limit=dBm_limit, source_on=source_on, **kwargs
        )
        if f_GHz is not None:
            self.write('CF1 {0:.2f} HZ'.format(f_GHz * 1e9))

        if dBm_limit is not None:
            self.dBm_limit = dBm_limit

        if dBm is not None:
            if self.dBm_limit < dBm:
                print(
                    'Tried to write a power of '
                    + str(dBm)
                    + ' with limit '
                    + str(self.dBm_limit)
                )
            else:
                self.write('L0 {} DM'.format(dBm))

        if source_on is not None:
            if source_on:
                self.write('RF1')

            else:
                self.write('RF0')

        # sg.write("PTG4") sets pulse to "triggered"
        # sg.write("OPT")
        # sg.write("PMD1 PTG1 PW 1 S IP")

    # %% State Model Checking
    def query_state(self):
        """
        Check the state of the machine.

        Returns
        -------
        str
            Current state of the instrument.

        """
        return self.state

    # %% Raise Errors

    def raise_errors(self):
        """
        Query the status of the instrument. If there are errors, raise them as Python errors.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        # read error bit from STB of signal generator
        err_str = self.get_errors()
        err_code = int(err_str.split(',')[0])
        if err_code != 0:
            raise InstrumentError(err_str)

    def get_errors(self):
        """
        Query the status of the instrument. If there are errors, returns the error message.

        Returns
        -------
        str
            Instruments error message

        """
        # read error bit from STB of signal generator
        return self.query('SYST:ERR?')

    # %% MetaData

    def get_frequency(self):
        """Get the frequency."""
        return float(self.query('OF1'))


if __name__ == '__main__':
    # from time import sleep
    sg = SignalGenerator('GPIB0::20::INSTR')
    print(sg.query_state())
    sg.initial_setup()
    print(sg.query_state())
