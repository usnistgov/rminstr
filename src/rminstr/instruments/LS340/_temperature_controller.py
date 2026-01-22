"""Control the LS340 as a temperature controller."""

import pyvisa as visa

# import numpy as np
from rminstr.instruments.measurement_functionalities import ABC_TemperatureController
from rminstr.instruments.communications import Instrument, InstrumentError


class TemperatureController(Instrument, ABC_TemperatureController):
    """LS340 as a temperature controller."""

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize the temperature controller class instance.

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
        raise SystemError('Dont use this code it is untested')

        # open visa resource, and intialize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)
        Instrument.__init__(self, visa_resource)

        # init Voltmeter abstraction
        ABC_TemperatureController.__init__(self, log_path=log_path)
        # Commented out -Zenn. If it breaks uncomment
        # self.num_readings = 0
        # self.trigger_source = "IMM"
        self.info_dict['model_number'] = 'LS340'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        # default setup
        # I let the things that will autopopulate autopopulate
        self.default_setup_settings = {
            'loop': 1,
            'loop_enabled': False,
            'loop_on_powerup': False,
            'loop_input': 'A',
            'heater_range': 0,
            'mode': 1,
            'setpoint': 24,
            'setpoint_units': 2,
            'sensor_input': 'A',
            'sensor_type': 1,
            'P': 0,
            'I': 0,
            'D': 0,
        }

    def initial_setup(self, **kwargs):
        """
        Initiliaze the temperature controllers's local settings to a safe state.

        This funciton should only be run if the instrument is not currently in a safe state,
        otherwise settings will be overwritten.

        Returns
        -------
        None.

        """
        super().initial_setup(**kwargs)
        self.clear_output()
        self.write('*RST')
        # self.write("SYST:PRES") # not sure if different
        self.write(
            '*ESE 1'
        )  # Enable “operation complete” using the *ESE 1 command (standard event register).
        self.write(
            '*OPC'
        )  # Send the *OPC? (operation complete query) command and enter the result to assure synchronization.
        self.write('*CLS')  # remove anything left in the output queue

        self.set_state('init')
        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
        self.set_state('init')

        self.raise_errors()

    # I am sorry, there were a lot of inputs. This could be broken up into several functions, but the order matters on some of them
    def setup(
        self,
        loop: int = None,
        loop_enabled: bool = None,
        loop_on_powerup: bool = None,
        loop_input: str = None,
        heater_range: int = None,
        mode: int = None,
        setpoint: float = None,
        setpoint_units: int = None,
        sensor_input: str = None,
        sensor_type: int = None,
        sensor_units: int = None,
        sensor_coefficient: int = None,
        sensor_excitation: int = None,
        sensor_range: int = None,
        P: float = None,
        I: float = None,
        D: float = None,
        **kwargs,
    ):
        """
        Change temperature controller settings.

        Parameters
        ----------
        loop : int, optional
            Which loop (1 or 2) to set the loop parameters for and use. The default is None.

        loop_enabled : bool, optional
            Whether or not to enable the loop after setting. The default is None.

        loop_on_powerup : bool, optional
            Whether or not to enable the loop after powerup. The default is None.

        loop_input : str, optional
            Which sensor input (A or B) to use for the specified loop. The default is None.

        heater_range : int, optional
            Specifies the heater range (max wattage). The values it sets depend on other parameters,
            refer to the manual (6.12.1) The default is None.

        mode : int, optional
            Specifies the loop mode. Refer to the manual for more details. The default is None.

            Values mapping is as follows:
            1 = Manual PID
            2 = Zone
            3 = Open Loop
            4 = AutoTune PID
            5 = AutoTune PI
            6 = AutoTune P

        setpoint : float = None
            The temperature setpoint. The default is None.

        setpoint_units : int = None
            The units for the temperature setpoint. The default is None.

            Values mapping is as follows:
            1 = Kelvin
            2 = Celsius
            3 = Sensor units

        sensor_input : str, optional
            Which input (A or B) to use for setting the sensor parameters. The default is None.

        sensor_type : int, optional
            The type of sensor to use. This will autopopulate certain sensor parameters if it is not zero,
            The default is None.

            Values mapping is as follows:
            0 - Special
            1 - Silicon Diode
            2 - GaAlAs Diode
            3 - Platinum 100 (250 Ohm)
            4 - Platinum 100 (500 Ohm)
            5 - Platinum 1000
            6 - Rhodium Iron
            7 - Carbon-Glass
            8 - Cernox
            9 - RuOx
            10 - Germanium
            11 - Capacitor
            12 - Thermocouple

        sensor_units : int, optional
            Will be autoset if type is not zero. Valid entires are volts (1) or ohms (2)
            The default is None.

        sensor_coefficient : int, optional
            Will be autoset if type is not zero. Specifies the coefficient of the sensor.
            Valid entires are negative (1) or positive (2). The default is None.

        sensor_excitation : int, optional
            Will be autoset if type is not zero. Specifies the excitation of the sensor (see manual 5.1.4).
            The default is None.

            Values mapping is as follows:
            0 - Off
            1 - 30 nA
            2 - 100 nA
            3 - 300 nA
            4 - 1 μA
            5 - 3 μA
            6 - 10 μA
            7 - 30 μA
            8 - 100 μA
            9 - 300 μA
            10 - 1 mA
            11 - 10 mV
            12 - 1 mV

        sensor_range : int, optional
            Will be autoset if type is not zero. Specifies the range of the sensor (see manual 5.1.4).
            The default is None.

            Values mapping is as follows:
            1 - 1 mV 4 - 10 mV 7 - 100 mV 10 - 1 V 13 - 7.5 V
            2 - 2.5 mV 5 - 25 mV 8 - 250 mV 11 - 2.5 V
            3 - 5 mV 6 - 50 mV 9 - 500 mV 12 - 5 V

        P : float, optional
            P constant to use in manual PID mode. The default is None.

        I : float, optional
            I constant to use in manual PID mode. The default is None.

        D : float, optional
            D constant to use in manual PID mode. The default is None.

        Returns
        -------
        None.

        """
        super().setup(
            loop=loop,
            loop_enabled=loop_enabled,
            loop_on_powerup=loop_on_powerup,
            loop_input=loop_input,
            heater_range=heater_range,
            mode=mode,
            setpoint=setpoint,
            setpoint_units=setpoint_units,
            sensor_input=sensor_input,
            sensor_type=sensor_type,
            sensor_units=sensor_units,
            sensor_coefficient=sensor_coefficient,
            sensor_excitation=sensor_excitation,
            sensor_range=sensor_range,
            P=P,
            I=I,
            D=D,
            **kwargs,
        )

        if loop is not None:
            self.loop = loop

        if loop_enabled is not None:
            self.loop_enabled = loop_enabled

        if loop_on_powerup is not None:
            self.loop_on_powerup = loop_on_powerup

        # Order matters probably. Mainly want to enable the loop last
        if sensor_input is not None and sensor_type is not None:
            self.write(
                'INTYPE '
                + sensor_input
                + ', '
                + str(sensor_type)
                + ', '
                + str(sensor_units).replace('None', '')
                + ', '
                + str(sensor_coefficient).replace('None', '')
                + ', '
                + str(sensor_excitation).replace('None', '')
                + ', '
                + str(sensor_range).replace('None', '')
            )

        if mode is not None:
            self.write('CMODE ' + str(self.loop) + ', ' + str(mode))

        self.write(
            'CSET '
            + str(loop)
            + ', '
            + loop_input.replace('None', '')
            + ', '
            + str(setpoint_units).replace('None', '')
            + ', '
            + +str(int(self.loop_enabled)).replace('None', '')
            + ', '
            + str(int(self.loop_on_powerup)).replace('None', '')
        )

        if setpoint is not None:
            self.write('SETP ' + str(self.loop) + ', ' + str(setpoint))

        if heater_range is not None:
            self.write('RANGE ' + str(heater_range))

        self.raise_errors()

    def get_errors(self):
        """
        Get any errors present on the instrument as a string.

        Returns
        -------
        str
            Error string if one is there.

        """
        # TODO: make it so it raises errors
        return self.query('SYST:ERR?')

    def raise_errors(self):
        """
        If the LS340 is in an error state, raise the errors as python errors.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        err_str = self.get_errors()
        err_code = int(err_str.split(',')[0])
        if err_code != 0:
            raise InstrumentError(err_str)


# if __name__ == "__main__":
# nplc = 10
# v_range = 2e-3
# num_readings = 1
# rm = visa.ResourceManager()
# NVM = Voltmeter("GPIB0::16::INSTR", rm)

# NVM.initial_setup()
# print(NVM.query_state())
# NVM.setup(nplc=nplc, v_range=v_range, num_readings=num_readings)
# print(NVM.query_state())

# for i in range(1):
#     print("i = ", i)
#     NVM.arm()
#     time.sleep(2)
#     print(NVM.query_state())
#     NVM.trigger()
#     print(NVM.query_state())
#     NVM.wait_until_data_available(timeout=10)
#     print(NVM.query_state())
#     NVM_data = NVM.fetch_data()
#     print(NVM_data['Voltage (V)'])
#     time.sleep(1)
