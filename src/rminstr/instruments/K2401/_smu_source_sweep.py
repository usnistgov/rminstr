
import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_SMUSourceSweep
from rminstr.instruments.communications import Instrument, InstrumentError, get_bit
import numpy as np


def is_iter(x):
    """Check if x isiterable."""
    try:
        _ = iter(x)
    except TypeError:
        return False
    return True


class SMUSourceSweep(Instrument, ABC_SMUSourceSweep):
    """
    Implementation of a source sweeping smu on K2401.


    Attributes
    ----------
    panel_configurations : list
        Possible panel connections for the SMU.

    overvoltages : list
        List of over voltage protection values that can be commanded to the SMU.

    """

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize source sweep smu.

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
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)
        Instrument.__init__(self, visa_resource)

        # init SMU abstraction
        ABC_SMUSourceSweep.__init__(self, log_path=log_path)

        # info dict
        self.info_dict = {}
        self.info_dict['model_number'] = 'Keithley2401'

        self.info_dict['resource_name'] = self.visa_resource.resource_name
        # serial, firmware_version = self.get_machine_info()
        # self.info_dict['serial'] = serial
        # self.info_dict["serial_number"] = serial
        # self.info_dict['firmware_version'] = firmware_version
        # panel configurations check
        self.panel_configurations = ['rear', 'front']

        # default setup
        self.default_setup_settings = {
            'source': 'off',
            'source_level': 0,
            # 'source_ilimit': 106e-3,
            'measure_range': 'auto',
            'over_voltage_protection': 0,
            'nplc': 1,

            'source_delay': 'auto',
        }

        # things it needs to keep track of
        # these are used to formulate SCIP commands based on if
        # voltage or current is being source or measured.
        self.source_as: str | None = None # 'VOLT' or 'CURR'
        self.measure_as: str | None = None # 'VOLT' or 'CURR'

    def initial_setup(
        self,
        wiring: str = None,
        source_measure: str = None,
        panel: str = None,
        **kwargs,
    ):
        """
        Initialize K2450 as a source sweep smu.

        Initialization method for the K2450. Passed key word arguments are stored
        in a local dictionary.

        Parameters
        ----------
        wiring : str, optional
            Either '4W' or '2W'. The default is None.

        source_measure : str, optional
            Sets up what is being sourced/measured using a naming convention. 'SVMI' set it to
            source volts and measure current; 'SIMV' sets it to source current and measure
            voltage. The default is None.

        panel : str, optional
            Either 'rear' or 'front'. The default is None.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        super().initial_setup(wiring=wiring, source_measure=source_measure, panel=panel)

        self.write('*RST;*CLS')
        self.write(':STATus:QUEue:CLEar')
        
        # wiring and source measure configurations
        if wiring not in self.wiring_configurations:
            raise InstrumentError('wiring configuration not recognized')
        if source_measure not in self.source_measure_configurations:
            raise InstrumentError('source_measure configuration not recognized')
        if panel not in self.panel_configurations:
            raise InstrumentError('panel configuration not recognized')

        # assign wiring
        if '4W' in wiring:
            pass
        else:
            raise NotImplementedError('Only 2 Wire Configuration is supported.')

        # assign source_measure settings
        if 'SV' in source_measure:
            self.source_as = 'VOLT'
            self.write(':SOURce:VOLT:MODE FIX')
            self.write(':SOURce:FUNC VOLT')
        else:
            self.source_as = 'CURR'
            self.write(':SOURce:CURR:MODE FIX')
            self.write(':SOURce:FUNC CURR')
        # measure mode
        if 'MV' in source_measure:
            self.measure_as = 'VOLT'
            self.write(':SENSe:FUNCtion:ON "VOLT","CURR"')
        else:
            self.measure_as = 'CURR'
            self.write(':SENSe:FUNCtion:ON "CURR","VOLT"')

    

        # # assign rear panels
        if panel == 'rear':
            self.write(':ROUTe:TERMinals REAR')
        elif panel == 'front':
            self.write(':ROUTe:TERMinals FRONt')
            # assign source_measure settings
        # assign wiring

        # leave source on after taking a measurement
        self.write(':SOURce:CLEar:AUTO 0')


        # these bits (machine is in idle and readings are available) will be used to 
        # check if machine is in data available state
        # have the OSB bit of the STB set high if instrument is in idle (bit 10 of the operation event register)
        self.write(f':stat:oper:enab {2**10}')
        # have the MSB set high if a reading is available
        self.write(f':stat:meas:enab {2**6}')

        # iniitialize source/measure settings at zero, but keep the state sas
        self.state = 'init'
        self.setup(**self.default_setup_settings)
        self.state = 'init'


    # PLEASE READ BEFORE CHANGING::
    # I made the default keyword arguments function a little differently here
    # In order to avoid sending more commands to the SMU then are asked to,
    # and to avoid hacing to resend commands to avoid overwriting the settings
    # you want with the default keyword argument,
    # the setup is run once in the initial_setup to establish safe default settings,
    # and then if  .setup() is run again and a setting is left as NONE, it is not commanded
    # the default settings are stored as a class instance variable

    def setup(
        self,
        source: str = None,
        source_level: float = None,
        source_range: float = None,
        source_ilimit: float = None,
        measure_range: float = None,
        measure_autozero: bool = None,
        over_voltage_protection: float = None,
        measure_for_duration_or_count: str = None,
        duration_per_level: float = None,
        initial_level_duration: float = None,
        count_per_level: int = None,
        nplc: float = None,
        source_readback: bool = None,
        source_delay: float = None,
        source_trigger_levels: list = None,
        buffer_size: float = None,
        buffer_fill_mode: str = None,
        **kwargs,
    ):
        """
        Change the SMU settings.

        Source and current values are in units of Volts or Amps, depending on the
        configuration of the SMU

        Parameters
        ----------
        source : str, optional
            Whether or not the source is on. Either 'off' or 'on'. The default is None.

        source_level : float, optional
            Value to set the source to. This will not turn on or off the source. The default is None.

        source_range : float, str, optional
            Range of the source, in units dependent on your source settings.
            If 'auto', smu will set range automatically. The default is None.

        source_ilimit : float, optional
            Hardware current limiter setting on the source output. The default is None.

        measure_range : float, optional
            Measurment range in units dependent on the measure settings.
            If 'auto' smu will set range automatically. The default is None.

        measure_autozero : bool, optional
            If True, measurements will autozero between each reading. If False,
            the SMU will only autozero once immediately after being triggered. The default is None.

        over_voltage_protection : float, optional
            Sets the voltage protector on the SMU. See overvoltages attribute for list of possible values.
            The method will round up to the nearest possible value. The default is None.

        measure_for_duration_or_count : str, optional
            Either 'count' or 'duration'. Sets the source sweep to be given each source level as set number of measurements
            or measure for a set amount of time. The default is None.

        duration_per_level : float, optional
            How long to measure each sweep value for if measurements are set to duration. The default is None.

        initial_level_duration : float, optional
            If set, will change the initial duration for source sweep value if measurements are set to duration.
            Set to negative value to turn off this setting, and use duration _per_level for every source value.

        count_per_level : int, optional
            How many measurements to take if measurements are set to count. The default is None.

        nplc : float, optional
            How long to integrate measurements for in power line cycles (about 1/60 seconds). The default is None.

        source_readback : bool, optional
            If true, the SMU will measure the source value it gives. This
            will approximatley double the measurement time per sample. Otherwise it will report
            the nominal setpoint value. The default is None.

        source_delay : float or str, optional
            Time to wait before taking a measurement after changing source level. if 'auto' SMU will
            automatically set delay. The default is None.

        source_trigger_levels : iter, optional
            Source levels to sweep through on trigger. If 'auto' the SMU will measure at
            whatever the current source level is at. The default is None.

        buffer_size : float, optional
            Number of readings to allocate for in the memory buffer. The default is None.

        buffer_fill_mode : str, optional
            Either 'fill_once' or 'continuous'. Determines how the SMU handles taking more readings
            than allocated for by buffer_size. The default is 'fill_once'.
            'fill_once' will fill the buffer then stop, 'continuous' will overwrite previous readings.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        super().setup(
            source=source,
            source_level=source_level,
            source_range=source_range,
            source_ilimit=source_ilimit,
            measure_range=measure_range,
            measure_autozero=measure_autozero,
            over_voltage_protection=over_voltage_protection,
            measure_for_duration_or_count=measure_for_duration_or_count,
            duration_per_level=duration_per_level,
            initial_level_duration=initial_level_duration,
            count_per_level=count_per_level,
            nplc=nplc,
            source_readback=source_readback,
            source_delay=source_delay,
            source_trigger_levels=source_trigger_levels,
            buffer_size=buffer_size,
            buffer_fill_mode=buffer_fill_mode,
            **kwargs,
        )
        # This does not work as intended. To test: source_trigger_levels = 5 will give back source_trigger_levels = 5. -Zenn
        # I put updated one below but leaving this here incase I break something
        # if not any([source_trigger_levels != c for c in [None, is_iter(source_trigger_levels), 'auto']]):
        #     source_trigger_levels = [source_trigger_levels]

        # cast to list if not an iterable, None, or 'auto'
        if source_trigger_levels is not None:
            raise NotImplementedError("source_trigger_levels not implemented.")

        if source_ilimit is not None:
            raise NotImplementedError("source_ilimit not implemented.")

        if measure_range is not None:
            if measure_range == 'auto':
                self.write(f':SENSe:{self.measure_as}:RANGe:AUTO {1}')
            else:
                raise NotImplementedError('Only "auto" supported for "measure_range".')

        # set source range
        if source_range is not None:
            raise NotImplementedError('Source ranging not implemented. Always auto.')

        if measure_autozero is not None:
            raise NotImplementedError("Autozero settings not implemented.")

        # set over protection
        if over_voltage_protection is not None:
            self.write(f':SOURce:VOLTage:PROTection {over_voltage_protection }')

        # set source level
        if source_level is not None:
            self.write(f':SOURce:{self.source_as} {source_level}')

        # set power line cycle integration
        if nplc is not None:
            if nplc > 10: 
                raise InstrumentError('nplc out of range')
            if nplc < 0.1: 
                raise InstrumentError('nplc out of range.')
            self.write(f'CURRent:NPLCycles {nplc}')
            self.write(f'VOLT:NPLCycles {nplc}')


        # source_readback
        if source_readback is not None:
            raise NotImplementedError()

        # source delay
        if source_delay is not None:
            if source_delay == 'auto':
                self.write(':SOURce:DELay:AUTO 1')
            else:
                self.write(':SOURce:DELay:AUTO 0')
                self.write(f':SOURce:DELay {source_delay}')

        # measuring for duration forces count to 1
        # measuring for count sets duration per_level to 0

        try:
            measure_for_duration_or_count = self.setup_settings['measure_for_duration_or_count'] 
        except KeyError:
            measure_for_duration_or_count = None
        
        if measure_for_duration_or_count == 'count':
            raise NotImplementedError()


        elif measure_for_duration_or_count == 'duration':
            raise NotImplementedError()
            # if duration_per_level is not None:
            #     if duration_per_level > 10000:
            #         raise Exception('Max duration per level is 10000 s')
            #     self.assign('duration_per_level', duration_per_level)

        if initial_level_duration is not None:
            raise NotImplementedError()
            # if initial_level_duration < 0:
            #     self.write('initial_level_duration = nil')
            # else:
            #     self.assign('initial_level_duration', initial_level_duration)

        # set source levels for measurement
        if source_trigger_levels is not None:
            raise NotImplementedError()
            # measure_for_duration_or_count
            # if (
            #     self.setup_settings['source_trigger_levels'] == 'auto'
            #     and source_level is not None
            # ):
            #     source_trigger_levels = [source_level]
            # if source_trigger_levels is not None:
            #     raise NotImplementedError()
            #     levels_str = r'{'
            #     for i in range(len(source_trigger_levels) - 1):
            #         levels_str += str(source_trigger_levels[i]) + r','
            #     levels_str += str(source_trigger_levels[-1]) + r'}'
            #     self.assign('source_levels', levels_str)

        # turn source off or on
        if source is not None:
            if source == 'off':
                self.write(':OUTPut 0')
            elif source == 'on':
                self.write(':OUTPut 1')

        if buffer_size is not None:
            raise NotImplementedError()

        if buffer_fill_mode is not None:
            raise NotImplementedError()


    def arm(
        self,
        delay: float = 0,
        trigger_source: str = 'bus',
        trigger_timeout: float = 1e5,
        trigger_mode: str = None,
    ):
        """
        Arm the SMU.

        Returns
        -------
        None.

        """

        super().arm(
            # delay=delay, trigger_source=trigger_source, trigger_timeout=trigger_timeout
        )
        # clear reading and trigger bugger, arm and ini to wait for trigger,
        # then send an OPC so that OPC? returns 1 when it is done.
        self.write(':TRAC:CLE')
        self.write(':TRIGger:CLEar')
        self.write(':ARM:SOURce BUS')
        # smu.raise_errors()
        self.write(':INIT')
        # self.write('*OPC')


    def trigger(self):
        """
        Trigger the SMU.

        Returns
        -------
        None.

        """
        super().trigger()
        self.visa_resource.assert_trigger()
        self.meas_start_time = self.get_relative_time()
        self.state = 'measuring'
        # pass

    def fetch_data(
        self
    ) -> dict[np.ndarray]:
        """
        Fetch data from the buffer.

        Parameters
        ----------
        delete_buffer : bool, optional
            If True, deallocates the buffer from the SMU's memory. The default is False.

        meas_start_time : float, optional
            If provided, will be used as timestamp for time of trigger. The default is None.

        Returns
        -------
        dict
            Dictionary of measurements. Columns are automatically named based on how the
            instrument was initalized.

        """
        super().fetch_data()
        data = self.query('DATA?').splitlines()
        volts = []
        current = []
        time = []
        status = []
        for line in data:
            sline = line.split(',')
            volts.append(float(sline[0]))
            current.append(float(sline[1]))
            time.append(float(sline[3]))
            status.append(float(sline[4]))


        data = {
            'timestamp': np.array(time),
            'Voltage (V)': np.array(volts),
            'Current (A)': np.array(current),
        }

        data['timestamp'] = data['timestamp'] - data['timestamp'][0] + self.meas_start_time
        return data


    def query_state(self):
        """
        Check the state of the machine according to state model.

        Returns
        -------
        state : str
            Current state of the instrument.

        """
        if self.state == 'measuring':
            stb= self.visa_resource.read_stb()
            osb_high = get_bit(stb,2**7)
            msb_high = get_bit(stb, 2**0)
            if osb_high and msb_high:
                self.state = 'data_available'
        return self.state

    def get_errors(self) -> str:
        """
        Get any error messages on the device.

        Returns
        -------
        errors : str
            Error message on device
        """
        msg = self.query(':SYSTem:ERRor:ALL?')
        return msg


    def raise_errors(self):
        errors = self.get_errors()
        if errors[0] == '0':
            return
        else:
            raise InstrumentError(errors)

    def do_after_group_trigger(self):
        """
        Run post-trigger commands after an external trigger event.

        Returns
        -------
        None.

        """
        self.state = 'measuring'
        self.write('*OPC')
        self.meas_start_time = self.get_relative_time()
        pass

    
    def close(self):
        self.write(':OUTPut 0')
        super().close()

if __name__ =='__main__':
    smu = SMUSourceSweep('GPIB0::3::INSTR')

    # print(smu.query_state())
    smu.raise_errors()
    smu.initial_setup(wiring = '4W', source_measure = 'SIMV', panel = 'front')
    # print(smu.query_state())
    smu.raise_errors()
    smu.setup(source_level = 1e-6, source = 'on', nplc = 10)
    # print(smu.query_state())
    smu.raise_errors()
    for i in range(10):
        smu.arm()
        # print(smu.query_state())
        smu.trigger()
        # print(smu.query_state())
        smu.wait_until_data_available(timeout = 10)
        smu.raise_errors()
        print(smu.query_state())
        smu.raise_errors()
        data = smu.fetch_data()
        print(data)
        smu.raise_errors()