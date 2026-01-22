# -*- coding: utf-8 -*-
"""Class for utilizing a K2450 as a DC substituted power meter."""

import time
import numpy as np
import pyvisa as visa
from rminstr.instruments.communications import TSPRunner, InstrumentError
from rminstr.instruments.measurement_functionalities import ABC_DCSubPowerMeter
from rminstr.instruments.communications import do_after_group_trigger
from typing import Union


class DCSubPowerMeter(ABC_DCSubPowerMeter, TSPRunner):
    """
    Control the K2450 behaving as a DC substituted power meter.

    Attributes
    ----------
    sensor_types : str,
        Type of sensors that are supported in the code (currently only "platinum_thinfilm").

    panel_configurations : list
        Possible panel connections for the SMU ('rear' or 'front').

    overvoltages : list
        list of over voltage protection values that can be commanded to the SMU.

    """

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize the DC substituted power meter.

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
        # open visa resource, and intialize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)
        TSPRunner.__init__(self, visa_resource)

        # init SMU abstraction
        ABC_DCSubPowerMeter.__init__(self, log_path=log_path)
        # upload relevent scripts to the SMU
        self.load_script(
            'K2450_dc_sub_power_meter',
            'K2450_dc_sub_power_meter',
            ['functions.tsp', 'stb_triggers.tsp', 'main.tsp'],
        )

        # used for timestamps
        self.meas_start_time = 0

        # add new sensor types here as support is added for them
        self.sensor_types = ['platinum_thinfilm', 'thermistor']

        # wiring configurations allowed
        self.panel_configurations = ['rear', 'front']

        # over_voltages for voltage protection
        self.overvoltages = np.array(
            [2, 5, 10, 20, 40, 60, 80, 100, 120, 140, 160, 180]
        )

        # info dict
        self.info_dict['model_number'] = 'Keithley2450'
        self.info_dict['serial_number'] = 'Unknown'
        self.info_dict['resource_name'] = self.visa_resource.resource_name
        # serial, firmware_version = self.get_machine_info()
        # self.info_dict['serial'] = serial
        # self.info_dict['firmware_version'] = firmware_version

        # default setup
        self.default_setup_settings = {
            'resistance_setpoint': None,
            'k_p': 0,
            'k_i': 0,
            'n_filter': 1,
            'duration': 0,
            'source_lbound': 0,
            'source_ubound': 0,
            'source': 'off',
            'source_level': 0,
            'source_range': 'auto',
            'source_ilimit': 106e-3,
            'measure_range': 'auto',
            'measure_autozero': True,
            'over_voltage_protection': 0,
            'nplc': 1,
            'source_readback': True,
            'source_delay': 'auto',
            'buffer_size': 1e6,
            'buffer_fill_mode': 'fill_once',
            'v0_cal': 0,
            'vm_cal': 1,
            'i0_cal': 0,
            'im_cal': 1,
            'trigger_var': 0,
            'max_source_diff': 0.001,
        }

        self.fetch_data = self._wrap_fetch_data(self.fetch_data)

    def initial_setup(
        self,
        sensor_type: str = None,
        panel: str = None,
        initial_source: float = 0,
        **kwargs,
    ):
        """
        Set initial setup of K2450 as a DC substituted power meter.

        Passed key word arguments are stored
        in a local dictionary. Determines the sensor type, panel, and other
        commands that are setup before an experiment begins or to reset the instrument;
        it places the instrument into a known safe state.

        Parameters
        ----------
        sensor_type: str,optional
            Type of sensor being controlled. Must be
            'platinum_thinfilm' or 'thermistor'.

        panel : str, optional
            Either 'rear' or 'front'. The default is None.

        initial_source : float, optional
            The feedback loop will be initialized to source this value (Volts
            for thinfilms and  Amps for thermistors).

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        super().initial_setup(
            sensor_type=sensor_type,
            panel=panel,
            initial_source=initial_source,
            **kwargs,
        )
        commands = ['reset()eventlog.clear()', 'status.clear()']
        for c in commands:
            self.write(c)
        self.flush_readout()

        if sensor_type in self.sensor_types:
            self.write('sensor_type = "' + sensor_type + '"')
        else:
            raise InstrumentError('Sensor type not recognized. See self.sensor_types')

        if panel not in self.panel_configurations:
            raise InstrumentError('panel configuration not recognized')
            # assign rear panels
        if panel == 'rear':
            self.write('smu.terminals = smu.TERMINALS_REAR')
        elif panel == 'front':
            self.write('smu.terminals = smu.TERMINALS_FRONT')
        # assign wiring
        if sensor_type == 'platinum_thinfilm':
            self.assign('smu.measure.sense', 'smu.SENSE_4WIRE')
            self.assign('smu.source.func', 'smu.FUNC_DC_VOLTAGE')
            self.assign('smu.measure.func', 'smu.FUNC_DC_CURRENT')
        elif sensor_type == 'thermistor':
            self.assign('smu.measure.sense', 'smu.SENSE_4WIRE')
            self.assign('smu.measure.func', 'smu.FUNC_DC_VOLTAGE')
            self.assign('smu.source.func', 'smu.FUNC_DC_CURRENT')
            self.assign('smu.measure.sense', 'smu.SENSE_4WIRE')
            self.write('linearized = false')
            #  Seemed to be going into 2 wire  mode depending on start up conditions
        else:
            raise Exception(' Sensor type not Supported')

        # initialize source/measure settings at zero,
        # but keep the state as init
        self.state = 'init'

        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
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

        # intialize counters for controller
        self.assign('errSum', initial_source)
        self.assign('meanV', 0)
        self.assign('meanR', 0)
        self.assign('stdR', 0)

    def setup(
        self,
        resistance_setpoint: float = None,
        k_p: float = None,
        k_i: float = None,
        n_filter: float = None,
        duration: float = None,
        source_ubound: float = None,
        source_lbound: float = None,
        source: Union[str, bool] = None,
        source_level: float = None,
        source_range: float = None,
        source_ilimit: float = None,
        measure_range: float = None,
        measure_autozero: bool = None,
        over_voltage_protection: float = None,
        nplc: float = None,
        source_readback: bool = None,
        source_delay: float = None,
        buffer_size: float = None,
        buffer_fill_mode: str = None,
        v0_cal: float = None,
        vm_cal: float = None,
        i0_cal: float = None,
        im_cal: float = None,
        trigger_var: float = None,
        max_source_diff: float = None,
        **kwargs,
    ):
        """
        Change the settings of the K2450.

        Source and current values are in units of Volts or Amps, depending on the
        configuration of the SMU

        Parameters
        ----------
        resistance_setpoint : float, optional
            The setpoint resistance.

        k_p : float, optional
            The proportional gain on linear controller.

        k_i : float, optional
            The intergral gain on linear controller.

        n_filter : int, optional
            The window sample size for the rolling average filtering. 0 Turns filter off, window size can be 1-100 samples.

        duration : float, optional
            How long to hold control loop for.

        source_ubound : float, optional
            Software upper limit on sourced value.

        source_lbound : float, optional
            Software lower limit on sourced value.

        source : Union[str, bool], optional
            Whether or not to turn the source on or off. Either 'off'/'on' or True/False.

        source_level : float, optional
            Value to set the source to.

        source_range : Union[float, str], optional
            If 'auto', smu will set range automatically.

        source_ilimit : float, optional
            Current limiter setting on the source output.

        measure_range : float, optional
            Measurment range. If 'auto' smu will set range automatically.

        measure_autozero : bool, optional
            If true, measurements will autozero between each reading. If false,
            the SMU will only autozero once immediatley after being triggered.

        over_voltage_protection : float, optional
            Sets the voltage protector on the SMU. See overvoltages attribute for list of possible values.
            The method will round up to the neares possible value.

        nplc : float, optional
            How long to integrate measurements for in power line cycles (about 1/60 seconds).

        source_readback : bool, optional
            If true, the SMU will measure the source value it gives, Otherwise it will return the nominal value.
            This will approximatley double the measurement time per sample.

        source_delay : Union[float, str], optional
            Time to wait before taking a measurement after changing source level. if 'auto' SMU will
            automatically set delay.

        buffer_size : float, optional
            Number of readings to allocated memory for the buffer.

        buffer_fill_mode : str, optional
            Either 'fill_once' or 'continuous'. Determines how the SMU handles taking more readings
            than allocated for by buffer_size. The default is 'fill_once'.
            'fill_once' will fill the buffer then stop, 'continuous' will overwrite previous readings.

        v0_cal : float, optional
            Calibrated Voltage offset (V). The default is None.

        vm_cal : float, optional
            Calibrated voltage slope correction (V/V). The default is None.

        i0_cal : float, optional
            Calibrated current offset correction (A). The default is None.

        im_cal : float, optional
            Calibrated current slope correction (A/A). The default is None.

        trigger_var : float, optional
            Threshhold for source value to send trigger pulses when compared
            against square of finite difference of the source. Set to zero to
            turn off output trigger pulses. The default is None.

        max_source_diff : float
            Maximum change in source value during the feedback loop. Doesn't apply
            to thinfilms. Only used for thermistors to handle noe-linearity on the
            IV curve.

        other_commands : list[str]
            any other commands are passed through to the SMU automatically.

        **kwargs
            Catches any commands that aren't recognized.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        super().setup(
            resistance_setpoint=resistance_setpoint,
            k_p=k_p,
            k_i=k_i,
            n_filter=n_filter,
            duration=duration,
            source_ubound=source_ubound,
            source_lbound=source_lbound,
            source=source,
            source_level=source_level,
            source_range=source_range,
            source_ilimit=source_ilimit,
            measure_range=measure_range,
            measure_autozero=measure_autozero,
            over_voltage_protection=over_voltage_protection,
            nplc=nplc,
            source_readback=source_readback,
            source_delay=source_delay,
            buffer_size=buffer_size,
            buffer_fill_mode=buffer_fill_mode,
            v0_cal=v0_cal,
            vm_cal=vm_cal,
            i0_cal=i0_cal,
            im_cal=im_cal,
            trigger_var=trigger_var,
            max_source_diff=max_source_diff,
            **kwargs,
        )
        if resistance_setpoint is not None:
            self.assign('resistance_setpoint', resistance_setpoint)
        if duration is not None:
            self.assign('duration', duration)

        if k_p is not None:
            self.assign('k_p', k_p)

        if k_i is not None:
            self.assign('k_i', k_i)

        if n_filter is not None:
            self.assign('n_filter', n_filter)
            if n_filter < 1:
                raise Exception('n_filter strictly >= 1')

        if source_ubound is not None:
            self.assign('source_ubound', source_ubound)

        if source_lbound is not None:
            self.assign('source_lbound', source_lbound)

        if (
            source_ilimit is not None
            and self.initial_setup_settings['sensor_type'] != 'thermistor'
        ):
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

        # turn source off or on. Works with booleans or str 'off' 'on'
        if source is not None:
            if type(source) is str:
                if source == 'off':
                    self.write('smu.source.output = smu.OFF')
                elif source == 'on':
                    self.write('smu.source.output = smu.ON')
            if type(source) is bool:
                if not source:
                    self.write('smu.source.output = smu.OFF')
                else:
                    self.write('smu.source.output = smu.ON')

        if buffer_size is not None:
            self.assign('buffer_size', buffer_size)

        if buffer_fill_mode is not None:
            if buffer_fill_mode == 'fill_once':
                self.assign('buffer_fill_mode', 'buffer.FILL_ONCE')
            if buffer_fill_mode == 'continuous':
                self.assign('buffer_fill_mode', 'buffer.FILL_CONTINUOUS')

        if v0_cal is not None:
            self.assign('v0_cal', v0_cal)

        if vm_cal is not None:
            self.assign('vm_cal', vm_cal)

        if i0_cal is not None:
            self.assign('i0_cal', i0_cal)

        if im_cal is not None:
            self.assign('im_cal', im_cal)

        if trigger_var is not None:
            self.assign('trigger_var', trigger_var)

        if max_source_diff is not None:
            self.assign('max_source_diff', max_source_diff)

    # %% Arm

    def arm(
        self,
        delay: float = 0,
        trigger_source: str = 'bus',
        trigger_timeout: float = 1e5,
        trigger_out: bool = False,
    ):
        """
        Arm the SMU.

        trigger_source: str, optional
            Either 'bus' or 'ext'. Bus will trigger by GPIB bus (either through self.trigger() or a GPIB GET
            command through a GPIB interface). Ext will trigger externally by digital i/o pin 1.

        trigger_timeout: float,
            How long to wait for a trigger signal before continuing the feedback
            loop. The default is 1e5s.

        trigger_out; bool,
            If True, asserts a trigger pulse over digital i/o pin 6 when triggered.
            The default is False.

        delay: float,
            How long to wait after a trigger before starting the feedback loop. The default is 0.

        Returns
        -------
        None.

        """
        super().arm(
            delay=delay,
            trigger_source=trigger_source,
            trigger_timeout=trigger_timeout,
            trigger_out=trigger_out,
        )
        self.flush_readout()
        self.write('trigger_source = "' + trigger_source + '"')
        if trigger_out:
            self.write('trigger_out = true')
        else:
            self.write('trigger_out = false')
        self.assign('trigger_timeout', trigger_timeout)
        self.assign('trigger_delay', delay)

        self.run_script('K2450_dc_sub_power_meter')

        # %% trigger

    def trigger(self, *instruments):
        """
        Trigger a DC susbtituted power measurement.

        Returns
        -------
        None.

        """
        super().trigger(*instruments)
        self.visa_resource.assert_trigger()
        self.meas_start_time = self.get_relative_time()
        if len(instruments) > 0:
            do_after_group_trigger(*instruments)

    # %% Fetch Data
    def _wrap_fetch_data(self, func):
        """
        Force stop a measurmeent before fetch data is actually called.

        Parameters
        ----------
        func : TYPE
            DESCRIPTION.

        obj : TYPE
            DESCRIPTION.

        Returns
        -------
        TYPE
            DESCRIPTION.

        """
        from functools import wraps

        @wraps(func)
        def wrapped(*args, **kwargs):
            key = 'stop_measurement'
            if key in kwargs.keys() and kwargs[key]:
                self.visa_resource.assert_trigger()
                self.wait_until_data_available(timeout=5)
            out = func(*args, **kwargs)
            return out

        return wrapped

    def fetch_data(
        self,
        delete_buffer: bool = True,
        meas_start_time: float = None,
        stop_measurement: bool = False,
    ) -> dict:
        """
        Fetch data from the buffer.

        Parameters
        ----------
        delete_buffer : bool, optional
            If True, deallocates the buffer from the SMU's memory. The default is True.

        meas_start_time: float, optional
            If provided, will be used as the absolute start time for the
            relevant timestamps taken from the K2450. Useful for providing start
            times of triggered measurements. If not provided, will use
            self.meas_start_time, which is calculated at the time of the trigger()
            call. The default is None.

        stop_measurement: bool, optional
            If True, will cancel any measurement in progress before fetching
            data. The default is False.

        Returns
        -------
        dict
            Dictionary of measurements. Columns are automatically named based on how the
            instrument was initalized.

        """
        super().fetch_data(
            delete_buffer=delete_buffer,
            meas_start_time=meas_start_time,
            stop_measurement=stop_measurement,
        )
        # if stop_measurement:
        #     self.visa_resource.assert_trigger()
        # print('waiting for busy check in fetch data')
        # # self.tsp_trace()
        # # waits for the termintaion string on loop before trying to read
        self.wait(self.timeout)
        # read data buffer out and delete
        # print('calling read buffer')
        # self.tsp_trace()
        data = self.read_buffer(deleteBuffer=delete_buffer)
        if self.initial_setup_settings['sensor_type'] == 'platinum_thinfilm':
            data['timestamp'] = self.meas_start_time + data.pop('time')
            data['Voltage (V)'] = data.pop('source')
            data['Current (A)'] = data.pop('measure')

        elif self.initial_setup_settings['sensor_type'] == 'thermistor':
            data['timestamp'] = self.meas_start_time + data.pop('time')
            data['Voltage (V)'] = data.pop('measure')
            data['Current (A)'] = data.pop('source')

        try:
            data['timestamp'] += self.arm_settings['delay']

        except KeyError:
            pass  # if not there, assume no ddefault of delay

        if meas_start_time is not None:
            data['timestamp'] += meas_start_time - self.meas_start_time

        # sort if getting data from a continuous array
        if self.setup_settings['buffer_fill_mode'] == 'continuous':
            ind = np.argsort(data['timestamp'])
            data = {k: v[ind] for k, v in data.items()}
        return data

    # %% query state

    def query_state(self):
        """
        Check the state of the machine according to state model.

        Returns
        -------
        str
            Current state of the instrument.

        """
        check_list = ['unarmed', 'armed', 'measuring', 'data_available']
        if self.state in check_list:
            osb = self.get_output_bit(7)
            busy = self.check_busy()
            # if self.state == 'armed' and not osb and busy:
            #     self.set_state('unarmed')
            if not osb and busy and self.state != 'measuring':
                self.state = 'armed'
            elif osb and busy:
                self.state = 'measuring'
            elif osb and not busy:
                self.state = 'data_available'
                self.write('status.clear()')
        return self.state

    # %% Information Polling

    def get_machine_info(self):
        """
        Poll machine for serial and firmware version numbers.

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

    def close(self):
        """
        Close out the instrument safely.

        Returns
        -------
        None.

        """
        if self.query_state() == 'armed':
            self.trigger()
        if self.query_state() == 'measuring':
            self.fetch_data(stop_measurement=True)
        self.setup(source=False)


# %% Tests
if __name__ == '__main__':
    import matplotlib.pyplot as plt

    # test rf power class
    # K2450 SMU as RF Power MeterResource
    rm = visa.ResourceManager()
    smurf = DCSubPowerMeter('GPIB0::18::INSTR', resource_manager=rm)
    smurf.logs = True
    smurf.initial_setup(
        sensor_type='platinum_thinfilm',
        panel='rear',
        initial_V=3,
    )

    print(smurf.query_state())
    smurf.setup(
        resistance_setpoint=965.4,
        k_p=0,
        k_i=1.5,
        n_filter=1,
        duration=10,
        source_ubound=7,
        source_lbound=1,
        source='off',
        source_level=1,
        source_range=10,
        measure_range=10e-3,
        measure_autozero=False,
        over_voltage_protection=10,
        nplc=1,
        source_readback=True,
        source_delay='auto',
        buffer_size=1e6,
        buffer_fill_mode='continuous',
        trigger_var=0,
    )
    setpoint = smurf.setup_settings['resistance_setpoint']
    esum = 0
    print(smurf.query_state())
    smurf.arm()
    print(smurf.query_state())
    smurf.trigger()
    t0 = time.time()
    while smurf.query_state() != 'data_available':
        # print(smurf.query_state(), time.time() - t0)
        time.sleep(0.01)
    smurf.wait_until_data_available(timeout=5)

    print(smurf.query_state())
    data = smurf.fetch_data()

    print(smurf.query_state())
    plt.close('all')

    fig, axs = plt.subplots(2, 2, sharex=True, figsize=(12, 12))
    t = data['timestamp']
    err = setpoint - data['Voltage (V)'] / data['Current (A)']
    esum_arr = [esum]
    ub = smurf.setup_settings['source_ubound']
    lb = smurf.setup_settings['source_lbound']
    ki = smurf.setup_settings['k_i']
    kp = smurf.setup_settings['k_p']
    diff = smurf.setup_settings['max_source_diff']
    for i in np.arange(1, len(err)):
        old = esum
        esum += -ki * err[i] * (t[i] - t[i - 1])
        if esum > old + diff:
            esum = old + diff
        if esum < old - diff:
            esum = old - diff
        if esum > ub:
            esum = ub
        if esum < lb:
            esum = lb
        esum_arr.append(esum)
    predicted_source = -kp * err + np.array(esum_arr)
    predicted_source_rnd = np.round(2 * predicted_source, 5) / 2
    axs[0, 0].plot(data['timestamp'], err, '.')
    axs[0, 1].plot(t, esum_arr)
    axs[1, 0].plot(t, -err * kp)
    axs[1, 1].plot(t, 1e3 * predicted_source, '.', label='predicted')

    for a in axs.flatten():
        a.grid()
    axs[0, 0].set_ylabel('Error (Ohm)')
    axs[0, 1].set_ylabel(r'$-K_i \Sigma \left(Err\Delta t\right)$')
    axs[1, 0].set_ylabel(r'$-K_p Err$')
    axs[1, 1].set_ylabel(' Predicted Current (mA)')
    axs[1, 1].set_xlabel('Time (s)')
    axs[1, 1].set_xlabel('Time (s)')

    fig, axs = plt.subplots(2, 2, sharex=True, figsize=(12, 12))
    axs[0, 0].plot(data['timestamp'], data['Voltage (V)'], '.-')
    axs[0, 0].set_ylabel('Volts')
    axs[0, 1].plot(
        data['timestamp'], 1000 * data['Current (A)'], '.-', label='Measured'
    )
    axs[0, 1].set_ylabel('Current (mA)')
    axs[1, 0].plot(data['timestamp'], data['Voltage (V)'] / data['Current (A)'], '.-')
    axs[1, 0].set_ylabel('Resistance')
    axs[1, 1].plot(
        data['timestamp'], 1000 * data['Voltage (V)'] * data['Current (A)'], '.-'
    )
    axs[1, 1].set_ylabel('Power (mW)')
    # cleanup
    smurf.setup(source='off')
    rm.close()
