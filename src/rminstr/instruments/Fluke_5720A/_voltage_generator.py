# -*- coding: utf-8 -*-
"""Voltage generator implementation of a DP8200."""

import pyvisa as visa
from rminstr.instruments.measurement_functionalities import ABC_VoltageGenerator
from rminstr.instruments.communications import Instrument
from bisect import bisect_right
from decimal import Decimal

class VoltageGenerator(Instrument, ABC_VoltageGenerator):
    """Implementation of the Fluke 5720A as a voltage generator."""

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

        self.info_dict['model_number'] = '5720A'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        self.default_setup_settings = {'source_level': 0}
        self.write('*CLS')
        self.write('*RST')
        self.write('OPER')
    

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
            Not implemented for this interface. Leave as None, currently
            this instrument defaults to autorange on start up and uses
            that alone.

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

        if v_range is not None:
            raise NotImplementedError('This instrument does not implement v_range. It currently uses auto range.')

        if source_level is not None:
            msg = 'OUT {:+.10E}V'.format(Decimal(source_level))
            self.write(msg)


if __name__ == '__main__':
    gen = VoltageGenerator('GPIB0::5::INSTR')
    gen.initial_setup()
    gen.setup(source_level = 1e-3)
    gen.setup(source_level=-1)
    gen._check_method_syntax('setup')