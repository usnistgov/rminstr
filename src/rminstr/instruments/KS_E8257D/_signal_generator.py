"""Signal generator implementation of KS_E8257D."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_SignalGenerator
from rminstr.instruments.communications import Instrument, InstrumentError


class SignalGenerator(Instrument, ABC_SignalGenerator):
    """Signal generator implementation of KS_E8257D."""

    def __init__(
        self,
        visa_resource: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize KS_E8257D as a signal generator.

        Parameters
        ----------
        visa_resource : visa.Resource
            visa resource for the instrument.

        resource_manager : visa.ResourceManager, optional
            Pyvisa resource manager for opening visa resources. The default is None.

        log_path : str, optional
            If provided, will log at the specified path. The default is None.

        Returns
        -------
        None.

        """
        # open visa resource, and intitlize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_resource)

        # open visa resource, and intialize as instrument
        Instrument.__init__(self, visa_resource)

        # initialize as signal generator
        ABC_SignalGenerator.__init__(self, log_path=log_path)
        Instrument.__init__(self, visa_resource)
        self.info_dict = {}
        self.info_dict['model_number'] = 'KS_E8257D'
        self.info_dict['serial_number'] = 'Unknown'
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        # 15 is the minimum limit
        self.default_settings = {
            'f_GHz': 1,
            'dBm': -20,
            'source_on': False,
            'AM': False,
            'AM_ext_port': 1,
            'AM_ext_sensitivity_percent_per_volt': 0,
            'AM_installed': False,
        }

        self.trigger_count = 0

    # %% Initial and Normal Setup
    def initial_setup(self, **kwargs):
        """
        Initialize instrument.

        Parameters
        ----------
        **kwargs : list, optional
            List of strings, commands to be sent directly to machine.
            The default is None.

        Returns
        -------
        None.

        """
        super().initial_setup(**kwargs)
        self.write('*RST')

        # CW. Maybe move to setup with options
        self.write('FREQ:MODE CW')

        self.setup(**self.default_settings)
        self.setup(**kwargs)
        self.query('*OPC?')

    def setup(
        self,
        dBm: float = None,
        f_GHz: float = None,
        source_on: bool = None,
        AM: bool = None,
        AM_ext_port: int = None,
        AM_ext_sensitivity_percent_per_volt: float = None,
        AM_installed: bool = True,
        **kwargs,
    ):
        """
        Adjust settings on the machine.

        Parameters
        ----------
        dBm : float, optional
            Power setting in dBm. The default is None.

        f_GHz : float, optional
            Frequency setting in GHz. The default is None.

        source_on : bool, optional
            Turns source on when True, off when False. The default is None.

        port : int, optional
            Determines which port is used for the commands. The default is None.

        AM : bool, optional
            Turns on or off the Amplitude Modulation. The default is None.

        AM_ext_port : int, optional
            What port to use for Amplitude Modulation. The default is None.

        AM_ext_sensitivity_percent_per_volt : float, optional
            Sensitivity of the Amplitude Modulation in percent per volt. The default is None.

        other_commands : list, optional
            List of other command not covered by keyword arguments. Written directly to instrument. The default is None.

        Returns
        -------
        None.

        """
        super().setup(dBm=dBm, f_GHz=f_GHz, source_on=source_on)
        if dBm is not None:
            # This is what was here before and I assume it works. Direct comparison uses the uncommented one.
            # If there are issues, uncomment and comment the other one and let me know -Zenn
            # self.write('POW '+str(dBm)+'DBM')
            self.write('POW:LEV ' + str(dBm) + 'dbm')

        if f_GHz is not None:
            self.write('FREQ ' + str(f_GHz) + 'GHZ')

        if source_on is not None:
            if source_on:
                self.write('OUTP:STAT ON')
            else:
                self.write('OUTP:STAT OFF')

        if AM_installed:
            if AM is not None:
                if AM:
                    self.write(':AM:STATE ON')
                else:
                    self.write(':AM:STATE OFF')

            if AM_ext_port is not None:
                if AM:
                    self.write(':AM1:SOURCE EXT' + str(AM_ext_port))

            if AM_ext_sensitivity_percent_per_volt is not None:
                self.write(':AM1 ' + str(AM_ext_sensitivity_percent_per_volt))

        self.query('*OPC?')

    # %% State Model Checking

    def query_state(self) -> str:
        """
        Check the state.

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
            Will raise the error in the instrument as a python error if present.

        Returns
        -------
        None.

        """
        # read error bit from STB of signal generator
        err_str = self.get_errors()
        err_code = int(err_str.split(',')[0])
        if err_code != 0:
            raise InstrumentError(err_str)
        pass

    def get_errors(self):
        """
        Query the status of the instrument. If there are errors, returns the error message.

        Returns
        -------
        str
            Instruments error message.

        """
        # TODO: Raise errors or print errors? check against Voltmeter for
        # consistancy.

        # read error bit from STB of signal generator
        return self.query('SYST:ERR?')

    def fetch_data(self):
        """Do nothing, this class collects no data."""
        pass

    def get_frequency(self):
        """Return the frequency in GHz."""
        return float(self.query('FREQ?')) * 1e-9


if __name__ == '__main__':
    # from time import sleep
    rm = visa.ResourceManager()
    sg = SignalGenerator('GPIB0::19::INSTR', resource_manager=rm)
    from instruments.communications.interface import GPIB

    intf = GPIB('GPIB0::INTFC', resource_manager=rm)
    print(sg.query_state())
    sg.initial_setup()
    sg.raise_errors()
    print(sg.query_state())
    sg.raise_errors()
    sg.setup(AM=False, AM_ext_port=1, AM_ext_sensitivity_percent_per_volt=10)
    sg.raise_errors()
