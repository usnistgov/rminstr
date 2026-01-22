# -*- coding: utf-8 -*-
"""Voltage generator implementation of a DP8200."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_VoltageGenerator
from rminstr.instruments.communications import Instrument
from bisect import bisect_right


class VoltageGenerator(Instrument, ABC_VoltageGenerator):
    """Implementation of the DP8200 as a voltage generator."""

    def __init__(
        self,
        GPIB_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize DP8200 as a voltage generator.

        Parameters
        ----------
        visa_address : str
            Visa address of instrument.

        resource_manager : visa.ResourceManager
            Optionally declare what resource manager to use for opening the
            visa resource object.

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
        ABC_VoltageGenerator.__init__(self, log_path=log_path)

        self.info_dict['model_number'] = 'DP8200'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        self.default_setup_settings = {'v_range': 1, 'source_level': 0}

    def query_state(self):
        """
        Check the state of the machine.

        Returns
        -------
        str
            Current state of the instrument.

        """
        return self.state

    def get_errors(self):
        """Get errors."""
        return None

    def raise_errors(self):
        """Raise errors present on instrument as exceptions."""
        return None

    def initial_setup(self, **kwargs):
        """
        Run initial setup routine on voltage calibrator.

        Returns
        -------
        None.

        """
        super().initial_setup()
        self.setup(**self.default_setup_settings)
        self.setup(**kwargs)

    def setup(self, v_range: float = None, source_level: float = None):
        """
        Adjust settings on the DP8200.

        Parameters
        ----------
        v_range : float, optional
            Voltage range of output. 100e-3, 10, 100, or 1000 V.
            Value will be rounded up to nearest valid value. The default is None.

        source_level : float, optional
            Voltage level to output. The default is None.

        Raises
        ------
        Exception
            On bad inputs.

        Returns
        -------
        None.

        """
        super().setup(v_range=v_range, source_level=source_level)
        source_level = self.setup_settings['source_level']
        v_range_val = self.setup_settings['v_range']
        ranges = [100e-3, 10, 100, 1000]
        if v_range_val in ranges:
            v_range = str([i for i, v in enumerate(ranges) if v_range_val == v][0])
        else:
            v_range = str(bisect_right(ranges, v_range_val))

        if v_range != '1':
            raise Exception(
                'Voltage range ' + str(v_range_val) + ' not yet implemented'
            )

        sign = '+'
        if source_level < 0:
            sign = '-'
        level = format(abs(source_level), '#0.5f').replace('.', '').zfill(7)
        msg = 'V' + v_range + sign + level
        self.write(msg)


if __name__ == '__main__':
    dp = VoltageGenerator('GPIB0::14::INSTR')
    dp.initial_setup()
    dp.setup(v_range=10, source_level=0)
