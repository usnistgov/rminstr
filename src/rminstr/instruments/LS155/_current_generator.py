"""Lakeshore 155 source generator."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_CurrentGenerator
from rminstr.instruments.communications import Instrument, get_bit, InstrumentError


class CurrentGenerator(Instrument, ABC_CurrentGenerator):
    """Implementation the LS155 as a current generator."""

    def __init__(
        self,
        GPIB_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize a LS155 for the current generator.

        Parameters
        ----------
        visa_resource : visa.Resource
            Visa resource for the instrument.

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

        visa_resource = resource_manager.open_resource(GPIB_address)
        Instrument.__init__(self, visa_resource)
        ABC_CurrentGenerator.__init__(self, log_path=log_path)

        self.info_dict['model_number'] = 'Lakeshore_155'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        self.default_setup_settings = {
            'panel': 'REAR',
            'i_range': 1e-6,
            'i_limit': 0,
            'over_voltage_protection': 1,
            'current_level': 0,
            'source': True,
        }

    def initial_setup(self, panel: str = None, **kwargs):
        """
        Set initial state of the machine.

        Parameters
        ----------
        panel : str, optional
            The panel to use (REAR or FRONT). The default is None.

        other_commands : list, optional
            list of strings, commands to be sent directly to machine. The default is None.

        Returns
        -------
        None.
        """
        super().initial_setup(panel=panel, **kwargs)
        self.write('*RST')
        self.write('*ESE 1')
        self.write('*OPC')
        self.write('*CLS')
        self.write('INIT:CONT 0')
        self.write('SOUR:FUNC:MODE CURR')
        self.write('SOUR:FUNC DC')
        self.write('SOUR:CURR 0')
        self.write('OUTP:STAT 0')
        self.state = 'init'

        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        if panel is not None:
            initial_settings['panel'] = panel

        self.setup(**initial_settings)
        self.state = 'init'
        # pass through some other command, if you want to modify

    def setup(
        self,
        panel: str = None,
        i_range: float = None,
        i_limit: float = None,
        over_voltage_protection: float = None,
        current_level: float = None,
        source: bool = None,
        other_commands: list = None,
        **kwargs,
    ):
        """
        Adjust settings on the machine.

        Parameters
        ----------
        panel : str, optional
            The panel to use (REAR or FRONT). The default is None.

        current : float, optional
            The current to output. The default is None.

        i_range : float, optional
            The range for the current output. The default is None.

        i_limit : float, optional
            Maximum current the sourec will output. The default is None.

        over_voltage_protection : float, optional
            Maximum voltage the source will output. The default is None.

        current_level : float, optional
            The current amplitude to source in A. The default is None.

        source : bool, optional
            Turns source on when True, off when False. The default is True.

        other_commands : list, optional
            List of other command not covered by keyword arguments. Written directly to instrument. The default is None.

        Returns
        -------
        None.

        """
        super().setup(
            panel=panel,
            i_range=i_range,
            i_limit=i_limit,
            over_voltage_protection=over_voltage_protection,
            current_level=current_level,
            source=source,
            other_commands=other_commands,
            **kwargs,
        )

        if panel is not None:
            self.write('ROUT:TERM ' + panel)

        if i_range is not None:
            if i_range > 0:
                self.write('SOUR:CURR:RANG ' + str(i_range))
            else:
                self.write('SOUR:CURR:RANG:AUTO 1')

        if i_limit is not None:
            self.write('SOUR:CURR:LIM ' + str(i_limit))

        if over_voltage_protection is not None:
            self.write('SOUR:CURR:PROT ' + str(over_voltage_protection))

        if current_level is not None:
            self.write('SOUR:CURR ' + str(current_level))

        if source is not None:
            self.output_on_trigger = str(int(source))

        if other_commands is not None:
            for oc in other_commands:
                self.write(oc)

    def arm(self):
        """
        Arms the instrument.

        Returns
        -------
        None.

        """
        super().arm()
        self.write('*CLS')

    # I have gotten a warning where it triggers while in 'data_avail'. Should be fixed
    def trigger(self):
        """
        Set the output of the source on.

        Returns
        -------
        None.

        """
        super().trigger()
        self.write('OUTP:STAT ' + self.output_on_trigger)
        self.write('*OPC')

    def fetch_data(self):
        """
        Fetch the data. This does nothing execpt state model stuff.

        Returns
        -------
        None.

        """
        super().fetch_data()

    def query_state(self):
        """
        Check the state of the machine according to state model.

        Returns
        -------
        str
            Current state of the instrument.

        """
        stb = self.read_stb()

        if get_bit(stb, 32) and (self.state == 'armed' or self.state == 'measuring'):
            self.state = 'data_available'

        return self.state

    def raise_errors(self):
        """
        Query the status of the instrument. If there are errors, raise them as Python errors.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument returns an error message or state.

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
        # read error bit from STB of signal generator
        return self.query('SYST:ERR:ALL?')


if __name__ == '__main__':
    # from time import sleep
    # sg = ('GPIB0::20::INSTR')
    # print(sg.query_state())
    print('No Main')
    # sg.initial_setup()
    # print(sg.query_state())
