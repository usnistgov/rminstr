"""SMU source sweep implementation of K2450."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_SMUSourceSweep

# from rminstr.instruments.communications import TSPRunner, InstrumentError
from rminstr.instruments.communications import Instrument, InstrumentError
import numpy as np


def is_iter(x):
    """Check if x isiterable."""
    try:
        _ = iter(x)
    except TypeError:
        return False
    return True


# class SMUSourceSweep(TSPRunner, ABC_SMUSourceSweep):
class SMUSourceSweep(Instrument, ABC_SMUSourceSweep):
    """
    Implementation of a source sweeping smu on K2450.

    This is the implementation of the sourcesweep measurement functionality of
    for the K2450 using tsp scripts. This class inherits from the TSPRunner and
    _abc_smu_sourcesweep classes. This class also inherits some default behaviours
    from the abstract class. Relevant to the user, these are:

        1. Methods must follow the state model, can not be called from the wrong state or a warning is raised and nothing happens
        2. Settings are automatically stored in a local dictionary when set


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
        # TSPRunner.__init__(self, visa_resource)
        Instrument.__init__(self, visa_resource)

        # init SMU abstraction
        ABC_SMUSourceSweep.__init__(self, log_path=log_path)
        # self.load_script(
        #     'K2450_smu_general',
        #     'K2450_smu_general',
        #     ['main.tsp'])

        # info dict
        self.info_dict = {}
        self.info_dict['model_number'] = 'Keithley2450'

        self.info_dict['resource_name'] = self.visa_resource.resource_name
        # serial, firmware_version = self.get_machine_info()
        # self.info_dict['serial'] = serial
        # self.info_dict["serial_number"] = serial
        # self.info_dict['firmware_version'] = firmware_version
        # panel configurations check
        self.panel_configurations = ['rear', 'front']

        # KEITHLY Over Voltage settings
        self.overvoltages = np.array(
            [2, 5, 10, 20, 40, 60, 80, 100, 120, 140, 160, 180]
        )

        # default setup
        self.default_setup_settings = {
            'source': 'off',
            'source_level': 0,
            'source_range': 'auto',
            # 'source_ilimit': 106e-3,
            'measure_range': 'auto',
            'measure_autozero': True,
            'over_voltage_protection': 0,
            'measure_for_duration_or_count': 'count',
            'duration_per_level': 1,
            'count_per_level': 1,
            'nplc': 1,
            'source_readback': True,
            'source_delay': 'auto',
            'source_trigger_levels': 'auto',
            'buffer_size': 1e6,
            'buffer_fill_mode': 'fill_once',
            'initial_level_duration': -1,  # turns off the setting by default
        }

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
        commands = ['reset()eventlog.clear()', 'status.clear()']

        # send command to clean the SMU
        for c in commands:
            self.write(c)
        self.flush_readout()

        # checks
        if wiring not in self.wiring_configurations:
            raise InstrumentError('wiring configuration not recognized')
        if source_measure not in self.source_measure_configurations:
            raise InstrumentError('source_measure configuration not recognized')
        if panel not in self.panel_configurations:
            raise InstrumentError('panel configuration not recognized')

        # Chris Functions
        # SMU_Port1.write("*RST") # Reset
        # SMU_Port1.write(":SYST:PRES") # Set to factory default state
        # SMU_Port1.write(":SYST:AZER ON") # Auto zero measurements
        # SMU_Port1.write(":SOUR:CLE:AUTO OFF")
        # SMU_Port1.write(":SYST:BEEP:STAT 0") # Turn off beeper

        # # Terminal use
        # SMU_Port1.write("ROUT:TERM FRON") # Use front terminals
        # #SMU_Port1.write("ROUT:TERM REAR") # Use rear terminals

        # # Configure to measure both voltage and current
        # SMU_Port1.write(":SYST:RSEN ON") # Use four-wire voltage sensing
        # # SMU_Port1.write(":SYST:RSEN OFF") # use two-wire voltage sensing

        # SMU_Port1.write(":SENS:FUNC:OFF:ALL") # Turn off all measurements
        # SMU_Port1.write(":SENS:FUNC 'VOLT';:SENS:FUNC 'CURR'") # Set to measure both voltage and current

        # SMU_Port1.write(":SOUR:FUNC CURR") # Current source mode
        # SMU_Port1.write(":SOUR:CURR:MODE FIXED") # We want DC current
        # SMU_Port1.write(":SOUR:CURR:RANG {0}".format(SMU_RangeI)) # Set source current range
        # SMU_Port1.write(":SENS:VOLT:PROT:RSYN ON") # Set up synchronization between the current measurement range and current compliance value
        # SMU_Port1.write(":SENS:VOLT:PROT {0}".format(SMU_RangeV)) # Set the current range to the lowest range that is larger than our specified number
        # SMU_Port1.write(":SENS:VOLT:PROT:RSYN OFF")
        # SMU_Port1.write(":SENS:VOLT:PROT {0}".format(SMU_CompV)) # Set the current compliance
        # # Turn on SMUs
        # SMU_Port1.write(":SOUR:CURR:LEV {0}".format(SMU_SourceI)) # Set source current to test resistor (1 mA typical)
        # SMU_Port1.write(":OUTP ON")
        # sleep(SMU_SoakTime)
        # # Check compliances
        # ComplianceString1 = SMU_Port1.query(":SENS:VOLT:PROT:TRIP?")
        # # Take a measurement
        # DataString1 = SMU_Port1.query(":READ? ")
        # # Turn off the output
        # SMU_Port1.write(":SOUR:CURR:LEV 0")
        # SMU_Port1.write(":OUTP OFF")
        # # Parse data

        # Display commands will be nice to have later
        # Seems like no function will set for all functions

        # Brackets are unclear
        # [SENSe[1]]:CURRent:AVERage[:STATe] OFF Turn off averaging
        # [SENSe[1]]:CURRent:AZERo[:STATe] OFF or ON for auto zero
        # [SENSe[1]]:CURRent:DELay:USER1 0 for no trigger delay. Is this needed or no? Prob not. Defualt is 0 s so no need to set
        # [:SENSe[1]]:<function>:NPLCycles
        # [:SENSe[1]]:<function>:AVERage[:STATe] For averaging, default should be OFF so no need to do
        # :ROUTe:TERMinals <location> To Route front or back. Ex :ROUT:TERM REAR
        # [:SENSe[1]]:<function>:RSENse 0 or OFF (2 wire), 1 or ON for 4W Ex VOLT:RSEN ON or :SENSe:VOLTage:RSENse ON

        # Fetch
        # :FETCh? "<bufferName>", <bufferElements>
        # There are options for bufferelements like times and stuff so may need to check that
        # Might need TRACe:DATA? since it says to use this if count is >1

        # Measure. Set function before this. Buffer and elements are optional as is above. Same as read but also sends function with it
        # Same as read command
        # :MEASure: "<bufferName>", <bufferElements>
        # :FORMat:ASCii:PRECision for decimals, default is auto

        # OUTPut[1]:<function>:SMODe changes state of source when output is turned off. NORMal, HIIMpedance, ZERO, GAURd

        # :OUTPut[1][:STATe] the out 0 or OFF, 1 or ON EX :OUTP ON
        # Sources from settings from :SOURce[1]:FUNCtion[:MODE]

        # Range
        # [:SENSe[1]]:<function>:RANGe:AUTO OFF or 0, ON  or 1 for auto range
        # [:SENSe[1]]:<function>:RANGe:AUTO:LLIMit Auto wont go below this range. Will be next highest range from setpoint. Default V = 20 mV, current 10e-9 A
        # :SENS:CURR:RANG 10E-6 Number will be used to find largest range required for it
        # :SENS:VOLT:RANG 200e-3

        # assign source_measure settings
        if 'SV' in source_measure:
            self.assign('smu.source.func', 'smu.FUNC_DC_VOLTAGE')
        else:
            self.assign('smu.source.func', 'smu.FUNC_DC_VOLTAGE')
            self.assign('smu.source.func', 'smu.FUNC_DC_CURRENT')
        if 'MV' in source_measure:
            self.assign('smu.measure.func', 'smu.FUNC_DC_VOLTAGE')
        else:
            self.assign('smu.measure.func', 'smu.FUNC_DC_CURRENT')

        # assign rear panels
        if panel == 'rear':
            self.write('ROUT:TERM REAR')  # Use rear terminals
        elif panel == 'front':
            self.write('ROUT:TERM FRON')  # Use front terminals

        # assign wiring
        if '4W' in wiring:
            self.assign('smu.measure.sense', 'smu.SENSE_4WIRE')
        else:
            self.assign('smu.measure.sense', 'smu.SENSE_2WIRE')

        # iniitialize source/measure settings at zero, but keep the state sas
        self.state = 'init'
        self.setup(**self.default_setup_settings)
        self.state = 'init'

        # enable status byte commands
        # -- Clear the status byte
        # -- Map bit 0 of the Operation Event Register to set on the Measurement
        # -- LOG_info1 sets bit 0 high, LOG_info2 sets  bit0 low
        self.write('status.operation.setmap(0, trigger.LOG_INFO1, trigger.LOG_INFO2)')
        # -- Enable bit 0 to flow through to the status byte.
        self.write('status.operation.enable = 1')
        # -- Enable the Operational Summary Bit to set the Master Summary
        # -- Bit/RQS
        self.write('status.request_enable = status.OSB')

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
        if (
            source_trigger_levels != None and source_trigger_levels != 'auto'  # noqa: E711
        ) and not is_iter(source_trigger_levels):
            source_trigger_levels = [source_trigger_levels]

        # this section will default to the current settings on keyword arguments
        # that aren't explicitly stated. it assumes that the setup has been called
        # at least once before with ALL the seetings specified (this is done in the initial setup at the
        # smu's normal default settings)
        # copies the dictionairy of local variables to kwargs, otherwise
        # if kwargs = locals(), kwargs would changes throughout the function
        # newsettings = get_kwargs(**locals())
        # del newsettings['self']
        # defaults = False
        # for k in newsettings.keys():
        #     #update instance dictionairy if value commanded
        #     if newsettings[k] is not None:
        #         self.settings[k] = newsettings[k]

        # the smu will throw errors if limit and range settings disagree, and some settings
        # will check against the other settings of the SMU, potentially throwing warnings
        # with each other so the order these commands are sent matter, AND I think
        # its important that someone writing the script explicitly state what they
        # are, and understand what settings they are measuring with
        # including them as keyword arguments and a defined in the setup routine
        # turn source on off
        # set measure range
        # adjust current limit on source

        if source_ilimit is not None:
            self.assign('smu.source.ilimit.level', source_ilimit)

        if measure_range is not None:
            if measure_range == 'auto':
                self.write('smu.measure.autorange = smu.ON')
            else:
                self.write('smu.measure.autorange = smu.OFF')
                self.assign('smu.measure.range', measure_range)

        # set source range
        if source_range is not None:
            if source_range == 'auto':
                self.write('smu.source.autorange = smu.ON')
            else:
                self.write('smu.source.autorange = smu.OFF')
                self.assign('smu.source.range', source_range)

        if measure_autozero is not None:
            if measure_autozero:
                self.write('smu.measure.autozero.enable = smu.ON')
            else:
                self.write('smu.measure.autozero.enable = smu.OFF')

        # set over protection
        if over_voltage_protection is not None:
            # these are the SMU's over
            # find nears protection voltage
            idx = np.argmin(abs(over_voltage_protection - self.overvoltages))
            new_over = self.overvoltages[idx]
            # if the nearest over setting is lower, round up
            if new_over < over_voltage_protection:
                idx += 1
                if idx > len(self.overvoltages):
                    raise InstrumentError('No Voltage Protection Higher than range')
                new_over = self.overvoltages[idx]
            self.assign(
                'smu.source.protect.level', 'smu.PROTECT_' + str(new_over) + 'V'
            )

        # set source level
        if source_level is not None:
            self.assign('smu.source.level', source_level)

        # set power line cycle integration
        if nplc is not None:
            self.assign('smu.measure.nplc', nplc)

        # source_readback
        if source_readback is not None:
            if source_readback:
                self.write('smu.source.readback = smu.ON')
            else:
                self.write('smu.source.readback = smu.OFF')

        # source delay
        if source_delay is not None:
            if source_delay == 'auto':
                self.write('smu.source.autodelay = smu.ON')
            else:
                self.write('smu.source.autodelay = smu.OFF')
                self.assign('smu.source.delay', source_delay)

        # measuring for duration forces count to 1
        # measuring for count sets duration per_level to 0
        if self.setup_settings['measure_for_duration_or_count'] == 'count':
            self.assign('measure_for_duration_or_count', "'count'")
            if count_per_level is not None:
                self.assign('count_per_level', count_per_level)
        elif self.setup_settings['measure_for_duration_or_count'] == 'duration':
            self.assign('measure_for_duration_or_count', "'duration'")
            if duration_per_level is not None:
                if duration_per_level > 10000:
                    raise Exception('Max duration per level is 10000 s')
                self.assign('duration_per_level', duration_per_level)

        if initial_level_duration is not None:
            if initial_level_duration < 0:
                self.write('initial_level_duration = nil')
            else:
                self.assign('initial_level_duration', initial_level_duration)

        # set source levels for measurement
        if (
            self.setup_settings['source_trigger_levels'] == 'auto'
            and source_level is not None
        ):
            source_trigger_levels = [source_level]
        if source_trigger_levels is not None:
            levels_str = r'{'
            for i in range(len(source_trigger_levels) - 1):
                levels_str += str(source_trigger_levels[i]) + r','
            levels_str += str(source_trigger_levels[-1]) + r'}'
            self.assign('source_levels', levels_str)

        # turn source off or on
        if source is not None:
            if source == 'off':
                self.write('smu.source.output = smu.OFF')
            elif source == 'on':
                self.write('smu.source.output = smu.ON')

        if buffer_size is not None:
            self.assign('buffer_size', buffer_size)

        if buffer_fill_mode is not None:
            if buffer_fill_mode == 'fill_once':
                self.assign('buffer_fill_mode', 'buffer.FILL_ONCE')
            if buffer_fill_mode == 'continuous':
                self.assign('buffer_fill_mode', 'buffer.FILL_CONTINUOUS')

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
        # Legacy handling
        if trigger_mode is not None:
            trigger_source = trigger_mode

        super().arm(
            delay=delay, trigger_source=trigger_source, trigger_timeout=trigger_timeout
        )
        # TODO, not sure if the clear is necessary but I am debugging

        self.write('eventlog.clear()')
        self.write('trigger.clear()')
        self.write('trigger_mode = "' + trigger_source + '"')
        self.assign('trigger_timeout', trigger_timeout)
        self.assign('trigger_delay', delay)
        self.run_script('K2450_smu_general')
        # pass

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
        # pass

    def fetch_data(
        self, delete_buffer: bool = True, meas_start_time: float = None
    ) -> dict:
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
        super().fetch_data(delete_buffer=delete_buffer, meas_start_time=meas_start_time)
        data = self.read_buffer(deleteBuffer=delete_buffer)
        if 'SV' in self.initial_setup_settings['source_measure']:
            s_key = 'Voltage (V)'
        else:
            s_key = 'Current (A)'
        data[s_key] = data.pop('source')
        if 'MV' in self.initial_setup_settings['source_measure']:
            m_key = 'Voltage (V)'
        else:
            m_key = 'Current (A)'
        data[m_key] = data.pop('measure')

        data['timestamp'] = data['time']
        try:
            data['timestamp'] += self.arm_settings['delay']
        except KeyError:
            pass  # if not there, assume no ddefault of delay
        if meas_start_time is not None:
            data['time'] += meas_start_time
        return data

    def query_state(self):
        """
        Check the state of the machine according to state model.

        Returns
        -------
        state : str
            Current state of the instrument.

        """
        check_list = ['armed', 'measuring', 'data_available']
        if self.state in check_list:
            osb = self.get_output_bit(7)
            if self.state == 'armed' and osb and self.check_busy():
                self.state = 'measuring'
            if osb and not self.check_busy():
                self.state = 'data_available'
                self.write('status.clear()')
        return self.state

    def get_errors(self):
        """
        Not implemented.

        Returns
        -------
        None.

        """
        pass

    def get_machine_info(self):
        """
        Poll machine for serial and firmware version numbers.

        Returns serial, firmware

        Returns
        -------
        str
            Serial of SMU.

        str
            Firmware version of SMU.

        """
        serial = self.query('print(localnode.serialno)').replace('\n', '')
        firmware = self.query('print(localnode.version)').replace('\n', '')
        return serial, firmware

    def do_after_group_trigger(self):
        """
        Run post-trigger commands after an external trigger event.

        Returns
        -------
        None.

        """
        pass


# %% Testing
if __name__ == '__main__':
    # import matplotlib.pyplot as plt
    import time

    mysmu = SMUSourceSweep(
        'GPIB0::10::INSTR', default_behaviours=True, log_path='settings.log'
    )
    mysmu.initial_setup(wiring='4W', source_measure='SVMI', panel='rear')
    print(mysmu.query_state())
    mysmu.setup(
        source='off',
        source_level=0.5,
        source_range=10,
        source_ilimit=100e-3,
        measure_range=100 - 3,
        measure_autozero=True,
        over_voltage_protection=10,
        measure_for_duration_or_count='count',
        duration_per_level=2,
        count_per_level=1,
        nplc=2,
        source_readback=True,
        source_delay='auto',
        source_trigger_levels=[1, 2, 3],
        buffer_size=1e6,
        buffer_fill_mode='fill_once',
    )
    print(mysmu.query_state())
    for i in range(1):
        mysmu.arm()
        print(mysmu.query_state())
        outbit = []
        mysmu.trigger()
        print(mysmu.query_state())
        while mysmu.query_state() != 'data_available':
            time.sleep(0.001)
        print(mysmu.query_state())
        data = mysmu.fetch_data()
        print(mysmu.query_state())

    mysmu.setup(source='off')
