"""Signal generator implementation of KS_PNA."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_SignalGenerator
from rminstr.instruments.communications import Instrument, InstrumentError


class SignalGenerator(Instrument, ABC_SignalGenerator):
    """
    Signal geneator implementation of KS_PNA.

    Attributes
    ----------
    visa_resource : visa.Resource
        Pyvisa resource for the instrument.

    """

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize KS_PNA as a signal generator.

        Parameters
        ----------
        visa_address : str
            Visa address of instrument.

        resource_manager : visa.ResourceManager, optional
            Pyvisa resource manager for opening visa resources. The Default is None.

        log_path : str, optional
            If provided, will log at the specified path. The default is None.

        Returns
        -------
        None.

        """
        raise SystemError(
            'This is untested code and should not be used; exiting. The doc strings here are also a mess'
        )

        # open visa resource, and intitlize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)

        # open visa resource, and intialize as instrument
        Instrument.__init__(self, visa_resource)

        # initialize as signal generator
        ABC_SignalGenerator.__init__(self, log_path=log_path)
        # Instrument.__init__(self, visa_resource)
        self.info_dict['model_number'] = 'KSPNA'
        self.info_dict['serial_number'] = 'Unknown'
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        self.default_settings = {
            'f_GHz': 0.01,
            'dBm': -30,
            'source_on': False,
            'port': 1,
        }

        # initialize arm setttings
        self.arm_settings['list_mode'] = 'AUTO'
        self.arm_settings['trigger_source'] = 'SING'

    # Initial and Normal Setup

    def initial_setup(self, display: bool = True, port: int = 1, **kwargs):
        """
        Initialize instrument.

        Parameters
        ----------
        display : bool, optional
            True, turns display on. False turns display off to improve
            performance.

        other_commands : list, optional
            list of strings, commands to be sent directly to machine.
            The default is None.

        Returns
        -------
        None.

        """
        super().initial_setup(display=display, port=port)

        self.write('ABORT;INITiate:CONTinuous OFF')
        self.write('FORM ASC,0')
        self.write('DISPlay:WINDow1:STATE ON')
        self.write('CALCulate:PARameter:DEL:ALL')

        astr = "'a" + str(port) + '_' + str(port) + "'"
        Rstr = 'R' + str(port) + ',' + str(port)
        bstr = "'b" + str(port) + '_' + str(port) + "'"
        if port == 1:
            Lstr = 'A' + ',' + str(port)
        elif port == 2:
            Lstr = 'B' + ',' + str(port)
        elif port == 3:
            Lstr = 'C' + ',' + str(port)

        self.write('CALCulate:PARameter:DEFine ' + astr + ',' + Rstr)
        self.write('DISPlay:WINDow1:TRACe1:FEED ' + astr)
        self.write('CALCulate:PARameter:DEFine ' + bstr + ',' + Lstr)
        self.write('DISPlay:WINDow1:TRACe2:FEED ' + bstr)

        # Configure VNA source
        # Source.write("SOURce:POWer{0}:MODE ON".format(VNA_Port)) # turn the VNA's RF source on
        self.write(
            'SOURce:POWer{0}:MODE OFF'.format(port)
        )  # turn the VNA's RF source off
        self.write('SENS:SWE:TYPE CW')
        self.write('SENS:SWE:POIN 3')
        self.write(
            'INITiate:CONTinuous ON'
        )  # Turning the source on and off apparently only works when data acquisition is running, so we need continious triggering
        self.write(
            'TRIGger[:SEQuence]:SOURce IMMediate'
        )  # We also need to start triggering
        # Source.write('SOUR:POW {0}'.format(VNA_Power))
        # Source.write('SENS:BWID {0}'.format(VNA_IFBW))
        # time.sleep(2) # wait for the VNA to process commands

        self.set_state('init')
        self.setup(**self.default_settings)
        self.set_state('init')

        if not display:
            self.write('SYSTem:DISPlay:UPDate ON')
        else:
            self.write('SYSTem:DISPlay:UPDate OFF')

        self.query('*OPC?')

    def setup(
        self,
        f_GHz: float = None,
        dBm: float = None,
        source_on: bool = None,
        port: int = 1,
        **kwargs,
    ):
        """
        Adjust settings on the machine.

        Parameters
        ----------
        f_GHz : float, optional
            Frequency setting in GHz. The default is None.

        dBm : float, optional,
            Power to set the source at in dBm. The default is None.

        source_on : bool, optional
            Turns source on when True, off when False. The default is None.

        port : int, optional
            Determines which port is used for the commands. Default is 1

        other_commands : list, optional
            List of other command not covered by keyword arguments. Written directly to instrument. The default is None.

        Returns
        -------
        None.

        """
        # set output limit
        if f_GHz is not None:
            self.write('SOUR:FREQ:CW ' + str(f_GHz * 1e9))

        if dBm is not None:
            self.write('SOUR:POW {0}'.format(dBm))

        if source_on is not None:
            if source_on:
                self.write(
                    'SOURce:POWer{0}:STATe ON'.format(port)
                )  # turn the source off (ZVA67)
            else:
                self.write(
                    'SOURce:POWer{0}:STATe OFF'.format(port)
                )  # turn the source off (ZVA67)

        self.query('*OPC?')

    def query_state(self) -> str:
        """
        Check the state.

        Returns
        -------
        str
            Current state of the instrument.

        """
        # if armed or triggered, intuit state
        if self.state == 'armed' or self.state == 'measuring':
            # if using step mode
            if self.arm_settings['list_mode'] == 'STEP':
                self = 'armed'

            else:
                # if list is running
                if bool(int(self.query('SOUR1:LIST:RUNN?'))):
                    self = 'measuring'
                else:
                    self = 'unarmed'

        return self.state

    def raise_errors(self):
        """
        Query the status of the instrument. If there are errors, raise them as Python errors.

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
            Instruments error message
        """
        # read error bit from STB of signal generator
        return self.query('SYST:ERR?')

    def get_frequency(self):
        """Get frequency."""
        return self.query('SENS:FREQ?')
