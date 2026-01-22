"""Signal generator implementation of RS_SMA100B."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_ArmedSignalGenerator
from rminstr.instruments.communications import Instrument, InstrumentError


class ArmedSignalGenerator(Instrument, ABC_ArmedSignalGenerator):
    """
    Implementation the RS_SMA100B as an armed signal generator.

    Attributes
    ----------
    trigger_count : int
        Counts the number of times the instrument has been triggered.

    """

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize RS SMA100B as an armed signal generator.

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
        # open visa resource, and intitlize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)

        # open visa resource, and intialize as instrument
        Instrument.__init__(self, visa_resource)

        # initialize as signal generator
        ABC_ArmedSignalGenerator.__init__(self, log_path=log_path)
        Instrument.__init__(self, visa_resource)
        self.info_dict['model_number'] = 'SMA100B'
        self.info_dict['serial_number'] = 'Unknown'
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        self.default_settings = {
            'dBm': -100,
            'f_GHz': 0.01,
            'dBm_limit': 0,
            'source_on': False,
            'AM': False,
            'AM_ext_port': None,
            'AM_ext_sensitivity_percent_per_volt': None,
        }

        # initialize arm setttings
        self.arm_settings['list_mode'] = 'AUTO'
        self.arm_settings['trigger_source'] = 'SING'

        # trigger counter
        self.trigger_count = 0

    # %% Initial and Normal Setup
    def initial_setup(
        self, display: bool = True, list_file: str = '/var/user/list1.lsw', **kwargs
    ):
        """
        Initialize istrument.

        Parameters
        ----------
        display : bool, optional
            True, turns display on. False turns display off to improve
            performance. The default is True.

        list_file : str, optional
            Source list file. Shouldn't need to be changed. The default is '/var/user/list1.lsw'

        other_commands : list, optional
            list of strings, commands to be sent directly to machine.
            The default is None.

        Returns
        -------
        None.

        """
        super().initial_setup(display=display, list_file=list_file)
        source_initstr = "*RST; :SYST:LANG 'SCPI';"
        self.write(source_initstr)
        self.state = 'init'

        initial_settings = dict(self.default_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value
        self.setup(**initial_settings)

        self.state = 'init'
        self.list_file = list_file
        self.write('SOUR1:LIST:SEL ' + '"' + list_file + '"')
        if not display:
            self.write('SYSTem:DISPlay:UPDate OFF')
        # pass through some other command, if you want to modify

    def setup(
        self,
        dBm: float = None,
        f_GHz: float = None,
        dBm_limit: float = None,
        source_on: bool = None,
        AM: bool = None,
        AM_ext_port: int = None,
        AM_ext_sensitivity_percent_per_volt: float = None,
        pow_sweep_dBm: list[float] = None,
        freq_sweep_GHz: list[float] = None,
        time_sweep_micros: list[float] = None,
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
            Power limit setting in dBm. The default is None.

        source_on : bool, optional
            Turns source on when True, off when False. The default is None.

        AM : bool, optional
            Turns on the Amplitude Modulation. The default is None.

        AM_ext_port : int, optional
            What port to use for amplitude modulation. The default is None.

        AM_ext_sensitivity_percent_per_volt : float, optional
            Sensitivity of the amplitdue modulation in percent per volt. The default is None.

        pow_sweep_dBm: list[float], optional
            A list of power levels to sweep if using the signal generator to sweep.

        freq_sweep_GHz: list[float], optional
            A list of frequency levels to sweep if using the signal generator to sweep.

        time_sweep_micros: list[float], optional
            A list of durations to sweep with if using the signal generator to sweep.

        Returns
        -------
        None.

        """
        super().setup(
            dBm=dBm,
            f_GHz=f_GHz,
            dBm_limit=dBm_limit,
            source_on=source_on,
            AM=AM,
            AM_ext_port=AM_ext_port,
            AM_ext_sensitivity_percent_per_volt=AM_ext_sensitivity_percent_per_volt,
            pow_sweep_dBm=pow_sweep_dBm,
            freq_sweep_GHz=freq_sweep_GHz,
            time_sweep_micros=time_sweep_micros,
            **kwargs,
        )
        # set output limit
        if dBm_limit is not None:
            self.write('SOURce1:POWer:LIMit:AMPLitude ' + str(dBm_limit))
        if f_GHz is not None:
            self.write(':FREQ ' + str(f_GHz) + 'GHZ')
        if dBm is not None:
            self.write('POW ' + str(dBm))

        if source_on is not None:
            if source_on:
                self.write('OUTP On')
            else:
                self.write('OUTP Off')

        # amplitude modulation
        if AM is not None:
            if AM:
                self.write('SOURce1:AM1:STATe 1')
            else:
                self.write('SOURce1:AM1:STATe 0')

        if AM_ext_port is not None:
            self.write('SOURce1:AM1:SOURce EXT' + str(int(AM_ext_port)))

        if AM_ext_sensitivity_percent_per_volt is not None:
            self.write('SOURce1:AM1:DEPTh ' + str(AM_ext_sensitivity_percent_per_volt))

        # switch to the list file
        if any([pow_sweep_dBm, freq_sweep_GHz, time_sweep_micros]):
            self.write('SOUR1:LIST:SEL ' + '"' + self.list_file + '"')
        if pow_sweep_dBm is not None:
            msg = ' ' + str(pow_sweep_dBm[0]) + ' dBm'
            for p in pow_sweep_dBm[1:]:
                msg += ', ' + str(p) + ' dBm'
            self.write('SOUR1:LIST:POW' + msg)

        if freq_sweep_GHz is not None:
            msg = ' ' + str(freq_sweep_GHz[0]) + ' GHz'
            for p in freq_sweep_GHz[1:]:
                msg += ', ' + str(p) + ' GHz'
            self.write('SOUR1:LIST:FREQ' + msg)

        if time_sweep_micros is not None:
            self.write('SOUR1:LIST:DWEL:MODE LIST')
            msg = ' ' + str(time_sweep_micros[0])
            for p in time_sweep_micros[1:]:
                msg += ', ' + str(p)
            self.write('SOUR1:LIST:DWEL:LIST' + msg)

    # %% Arm/Trigger
    def arm(
        self, list_mode: str = 'AUTO', trigger_source: str = 'BUS', output: str = None
    ):
        """
        Arm the signal generator so that it starts when triggered.

        Parameters
        ----------
        list_mode : str, optional
            Either 'AUTO' or 'STEP'. 'AUTO' will have source step through sweep
            and dwell on each element for each time sweep value defined in
            setup. 'STEP' will have source step through the index when a trigger
            is received. The default is 'AUTO'.

        trigger_source : str, optional
            Either 'BUS' or 'EXT' trigger source for initiating/stepping through a
            sweep. The default is 'BUS'.

        output: float, optional
            Either 'off' or 'on'; additional arming option. Overrides the list_mode
            command if provided, and arms source to change the output status.
            The default is None.

        Returns
        -------
        None.

        """
        # standard triggering method
        super().arm()
        if output is None:
            self.write('OUTP1:STAT ON')
            self.write('SOUR1:LIST:SEL ' + '"' + self.list_file + '"')
            self.write('SOUR1:FREQ:MODE LIST')
            self.write('SOUR1:LIST:MODE ' + list_mode)
            self.write('SOUR1:LIST:TRIG:SOUR ' + trigger_source)
            self.write('SOUR1:LIST:RES')

        elif output == 'off':
            file = r'/var/user/list_off.lsw'
            self.write('SOUR1:LIST:SEL ' + '"' + file + '"')
            self.write('SOUR1:FREQ:MODE LIST')

    def trigger(self):
        """
        Trigger the signal generator.

        Returns
        -------
        None.

        """
        super().trigger()
        self.visa_resource.assert_trigger()
        self.trigger_count += 1

    def fetch_data(self):
        """
        Fetch data from the signal generator.

        This is a placeholder function.

        Returns
        -------
        None.

        """
        super().fetch_data()

    # %% State Model Checking

    def query_state(self) -> str:
        """
        Check the state of the machine according to state model.

        Returns
        -------
        str
            Current state of the instrument.

        """
        # if armed or triggered, intuit state
        if self.state == 'armed' or self.state == 'measuring':
            # if using step mode
            if self.arm_settings['list_mode'] == 'STEP':
                self.state = 'armed'

            else:
                # if list is running
                if bool(int(self.query('SOUR1:LIST:RUNN?'))):
                    self.state = 'measuring'
                else:
                    self.state = 'unarmed'

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
        pass

    def get_errors(self):
        """
        Get any errors present on the instrument as a string.

        Returns
        -------
        str
            Error string if one is there.

        """
        # TODO: Raise errors or print errors? check against Voltmeter for
        # consistancy.

        # read error bit from STB of signal generator
        return self.query('SYST:ERR?')

    def do_after_group_trigger(self):
        """
        Run post-trigger commands after an external trigger event.

        Returns
        -------
        None.

        """
        self.trigger_count += 1

    def get_sweep_index(self):
        """
        Get the current index of the sweep.

        Returns
        -------
        int
            Index of sweep.

        """
        return self.query('SOUR1:LIST:IND?')

    def get_frequency(self):
        """
        Get the frequency setpoint in GHz.

        Returns
        -------
        int
            Frequency setpoint.

        """
        return float(self.query('SOUR1:FREQ?')) / 1e9
