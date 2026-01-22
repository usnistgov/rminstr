# -*- coding: utf-8 -*-
"""
VNA control code for R&S ZVA67.

Based on the PNAX written by Bryan Bosworth,
with contributions from Chris Long, Tomasz Karpisz, and possibly others
Requires Python 3.10+.

Besides changing commands for compatibility with the ZVA67, CalorimeterPython
style and flow control is used wherever possible without breaking compatibility
with code written for the PNAX.

Note, the VNA remote language should be "DEFAULT". In the GUI, the language
setting is under System -> System Configuration -> Remote Language


References
----------
https://www.rohde-schwarz.com/webhelp/zva_html_usermanual_en/zva_html_usermanual_en.html
"""

from rminstr.instruments.measurement_functionalities import ABC_VNA
from rminstr.instruments.communications import Instrument, get_bit, InstrumentError

# import inspect
import numpy as np
import datetime
import pyvisa as visa
import re
import os

# because the notation used by the VNA is hard to remember
PARAMETER_ALIAS = {
    'a11': 'R1,1',
    'b11': 'A,1',
    'a21': 'R2,1',
    'b21': 'B,1',
    'a31': 'R3,1',
    'b31': 'C,1',
    'a41': 'R4,1',
    'b41': 'D,1',
    'a12': 'R1,2',
    'b12': 'A,2',
    'a22': 'R2,2',
    'b22': 'B,2',
    'a32': 'R3,2',
    'b32': 'C,2',
    'a42': 'R4,2',
    'b42': 'D,2',
    'a13': 'R1,3',
    'b13': 'A,3',
    'a23': 'R2,3',
    'b23': 'B,3',
    'a33': 'R3,3',
    'b33': 'C,3',
    'a43': 'R4,3',
    'b43': 'D,3',
    'a14': 'R1,4',
    'b14': 'A,4',
    'a24': 'R2,4',
    'b24': 'B,4',
    'a34': 'R3,4',
    'b34': 'C,4',
    'a44': 'R4,4',
    'b44': 'D,4',
}


class VNA(Instrument, ABC_VNA):
    """
    Implementation the ZVA67 as a VNA.

    Attributes
    ----------
    ID : str
        ID string from the VNA.

    """

    def __init__(
        self,
        VNA_GPIB: str,
        timeout=5000,
        resetParams=True,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize a VNA object

        Parameters
        ----------
        VNA_GPIB : str
            Visa address of instrument.

        timeout : int
            When to time out the resource. The default is 5000.

        resetParams : bool
            Whether or not to reset the parameters. The default is True.

        resource_manager : visa.ResourceManager, optional
            Pyvisa resource manager for opening visa resources. The default is None.

        log_path : str, optional
            If provided, will log at the specified path. The default is None.

        Returns
        -------
        None.

        """

        ABC_VNA.__init__(self, log_path=log_path)

        # open visa resource, and intitlize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        if 'GPIB' in VNA_GPIB:
            GPIB_addr = VNA_GPIB
        else:
            GPIB_addr = 'GPIB0::%d::INSTR' % VNA_GPIB

        visa_resource = resource_manager.open_resource(GPIB_addr)

        # open visa resource, and intialize as instrument
        Instrument.__init__(self, visa_resource)
        self.visa_resource.timeout = timeout
        self.ID = self.query('*IDN?').strip()  # ID string
        opt = self.query('*OPT?').strip()
        print('ID: ' + self.ID)

        self.write('format:data ascii')

        # this is here twice. I dont think it needs to be but leaving here in case it breaks -Zenn
        # initialize as signal generator
        # instrument.__init__(self, visa_resource)

        info = self.ID.split(',')
        self.info_dict['model_number'] = info[0] + ' ' + info[1]
        self.info_dict['serial'] = info[2]
        self.info_dict['firmware_version'] = info[3]
        self.info_dict['ID'] = self.ID
        self.info_dict['OPT'] = opt
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        self.default_setup_settings = {
            'IFBW': 100,
            'params': ['a11', 'b11'],
            'power_dBm': -3,
            'flist_GHz': np.arange(1, 50, 1),
            'fstart_GHz': None,
            'fstop_GHz': None,
            'npoints': None,
            'sweep_type': None,
            'average': 0,
        }

        if resetParams:
            # Set to default and no calibration
            self._resetInstrument()

    def _deleteAllSegments(self):
        """
        Delete all segments.

        Returns
        -------
        None.

        """
        self.write('SENS:SEGM:DEL:ALL')

    def _deleteSegmentNum(self, num: int):
        """
        Delete a segment.

        Parameters
        ----------
        num : int
            Segment number.

        Returns
        -------
        None.

        """
        self.write('SENS:SEGM%d:DEL' % num)

    def _getFrequencies(self) -> np.array:
        """
        Get frequency list.

        Returns
        -------
        np.array
            Frequency list.

        """

        sweepType = self._getSweepType().lower()
        if 'cw' in sweepType:
            frequencyList = np.array([self._getCWfreq()] * self._getNumSweepPts())

        else:
            frequencyList = self._getXaxis()

        return frequencyList

    def _getID(self) -> str:
        """
        Get ID string.

        Returns
        -------
        str
            ID string.

        """
        return self.ID

    def _getIFBW(self) -> float:
        """
        Get IF bandwidth.

        Returns
        -------
        float
            IF bandwidth in Hz.

        """
        return float(self.query('SENS:BWID?').strip())

    def _getSourcePower(self) -> float:
        """
        Get source power in dBm.

        Returns
        -------
        float
            Source power.

        """
        return float(self.query('SOUR:POW?').strip())

    def _getNumParams(self) -> int:
        """
        Get number of sweep parameters.

        Returns
        -------
        int
            Number of sweep parameters.

        """
        resp = self.query('CALC1:PAR:CAT?')
        numParams = len(re.findall(r'param\d', resp))
        return numParams

    def _getNumSweepPts(self) -> int:
        """
        Get number of sweep points.

        Returns
        -------
        int
            Number of sweep points.

        """
        return int(self.query('SENS:SWEep:POINts?'))

    def _getSweepType(self) -> str:
        """
        Get sweep type.

        Returns
        -------
        str
            Sweep type.

        """
        return self.query('SENS:SWE:TYPE?').strip()

    def _getSweepTime(self) -> float:
        """
        Get sweep time.

        Returns
        -------
        float
            Sweep time in seconds.

        """
        return float(self.query('SENS:SWE:TIME?').strip())

    def _getCWfreq(self) -> float:
        """
        Get CW frequency in HZ.

        Returns
        -------
        float
            CW frequency in Hz.

        """
        return float(self.query('SENS:FREQ:CW?').strip())

    def _getAverageState(self) -> bool:
        """
        Get averaging state. False signifies averaging is disabled.
        Returns
        -------
        bool
            Average state.

        """
        return bool(self.query('SENS:AVER:STAT?').strip())

    def _getAverageNum(self) -> float:
        """
        Get average number.

        Returns
        -------
        float
            Average number.

        """
        return float(self.query('SENS:AVER:COUNt?').strip())

    def _getXaxis(self) -> np.ndarray:
        """
        Get Xaxis: list of frequency points in string format.

        Returns
        -------
        np.ndarray
            List of frequency points in string format.

        """
        resp = self.query('CALC1:DATA:STIM?')
        xListStr = resp.replace('\n', '').split(',')
        xList = np.array([float(x) for x in xListStr])
        return xList

    def _getNumSegments(self) -> int:
        """
        Get number of segments.

        Returns
        -------
        int
            Number of segments.

        """
        return int(self.query('SENS:SEGM:COUNt?').strip())

    def _getParamComplexData(self) -> tuple:
        """
        Get measured data.

        This will cause VNA to perform a single sweep and hold.
        Returns two columns (real and imag) per parameter measurement.

        Returns
        -------
        tuple
            If time_data:
                Frequencies, times, sweep data.

            else:
                Frequencies, sweep data.

        """
        self.arm()
        self.trigger()
        self.wait_until_data_available()
        data = self.fetch_data()
        return data

    def _resetInstrument(self):
        """
        Put intstrument into known initial state.

        Returns
        -------
        None.

        """
        self.initial_setup()

    def _setCorrection(self, correction: bool):
        """
        Set the correction state.

        Parameters
        ----------
        correction : bool
            True to acquire calibrated data.

        Returns
        -------
        None.

        """
        if correction:
            self.write('SENS:CORRection:STATe ON')  # Set calibration to ON
        else:
            self.write('SENS:CORRection:STATe OFF')  # Set calibration to OFF

    # removed paramList argument because it was unncessary
    def _setAutoYScale(self):
        """
        Autoscales the Y axis of all traces.

        Returns
        -------
        None.

        """
        paramCount = self.getNumParams()  # len(paramList)
        for k in range(1, paramCount + 1):
            self.write('DISP:WIND1:TRAC:Y:AUTO ONCE Trc%s' % (k))

    def _setCenter(self, center: float):
        """
        Set the center frequency.

        Parameters
        ----------
        center : float
            Center frequency in Hz.

        Returns
        -------
        None.

        """
        self.write('SENSe1:FREQuency:CENTer %E' % center)

    def _setSpan(self, span: float):
        """
        Set the span.

        Parameters
        ----------

        span : float
            Span in Hz.

        Returns
        -------
        None.

        """
        self.write('SENSe1:FREQuency:SPAN %E' % span)

    def _setCenterSpan(self, center: float, span: float):
        """
        Set the center and span.

        Parameters
        ----------
        center : float
            Center frequency in Hz.

        span : float
            Span in Hz.

        Returns
        -------
        None.

        """
        self.write('SENSe1:FREQuency:CENTer %E' % center)
        self.write('SENSe1:FREQuency:SPAN %E' % span)

    def _setContSweep(self):
        """
        Set continuous sweep.

        Returns
        -------
        None.

        """
        self.write('SENS:SWE:MODE CONT')

    def _setFreqStart(self, fstart: float):
        """
        Set the start frequency.

        Parameters
        ----------
        fstart : float
            Start frequency in Hz.

        Returns
        -------
        None.

        """
        self.write('SENS:FREQuency:STARt %E' % fstart)

    def _setFreqStop(self, fstop: float):
        """
        Set the stop frequency.

        Parameters
        ----------
        fstop : float
            Stop frequency in Hz.

        Returns
        -------
        None.

        """
        self.write('SENS:FREQuency:STOP %E' % fstop)

    def _setFreqStartStop(self, fstart: float, fstop: float):
        """
        Set the start and stop frequencies.

        Parameters
        ----------
        fstart : float
            Start frequency in Hz.

        fstop : float
            Stop frequency in Hz.

        Returns
        -------
        None.

        """
        self.write('SENS:FREQuency:STARt %E' % fstart)
        self.write('SENS:FREQuency:STOP %E' % fstop)

    def _setCWFreq(self, freq: float):
        """
        Set the CW frequency.

        Parameters
        ----------
        freq : float
            CW frequency in Hz.

        Returns
        -------
        None.

        """
        self.write('SENS:FREQ:CW %d' % freq)

    def _setIFBW(self, IF_BW: float):
        """
        Set the IF bandwidth.

        Parameters
        ----------
        IF_BW : float
            IF bandwidth in Hz.

        Returns
        -------
        None.

        """
        self.write('SENS:BWIDth %d' % IF_BW)

    def _setReduceIFBWatLowFreq(self, on: bool):
        """
        Set the reduce IF bandwidth state.

        Parameters
        ----------
        on : bool
            True to turn on Reduce IF bandwidth at low frequencies.

        Returns
        -------
        None.

        """
        if on:
            self.write('SENS:BWID:TRAC ON')

        else:
            self.write('SENS:BWID:TRAC OFF')

    def _setNumSweepPts(self, numPoints: int):
        """
        Set number of sweep points.

        Parameters
        ----------
        numPoints : int
            Number of sweep points.

        Returns
        -------
        None.

        """
        self.write('SENSe1:SWEep:POINts %d' % numPoints)

    def _setAverageState(self, on: bool):
        """
        Set whether or not to average. True will turn on averaging.

        Parameters
        ----------
        on : bool
            Averaging state

        Returns
        -------
        None.

        """
        if on:
            self.write('SENS:AVER:STAT ON')
        else:
            self.write('SENS:AVER:STAT OFF')

    def _setAverageNum(self, num: int):
        """
        Set average number.

        Parameters
        ----------
        num : int
            Average number.

        Returns
        -------
        None.

        """
        self.write('SENS:AVER:COUNt %d' % num)

    def _setOutputOnOff(self, on: bool = True):
        """
        Set the output state.

        Parameters
        ----------
        on : bool, optional
            True turns on RF output power. The default is True.

        Returns
        -------
        None.

        """
        if on:
            self.write('OUTP ON')
        else:
            self.write('OUTP OFF')

    # This command is in the manual, but when I try to run it, I get an
    # eror message "function not available"
    # def _setSourcePowerAtten(self, port: int, atten: float):
    #     """
    #     Set source attenuators.

    #     From manual:
    #     Sets a fixed attenuation factor for the generated wave at test port no.
    #     <port> and switches the attenuator mode to MANual setting.
    #     The incident wave is attenuated via [SENSe<Ch>:]POWer:ATTenuation.

    #     Parameters
    #     ----------
    #     port : int
    #         Test port number.

    #     atten : float
    #         From maunal:
    #         Depending on the analyzer/attenuator model, e.g. 0 dB to 80 dB [dB].
    #         UP and DOWN increment/decrement the attenuation in 10-dB steps.
    #         The analyzer rounds any entered value below the maximum attenuation
    #         to the closest step.

    #     Returns
    #     -------
    #     None.

    #     """
    #     self.write("SOUR:POW%d:ATT %d" % (port, atten))

    def _setSourcePowerAttenMode(self, port: int, mode_str: str):
        """
        Set how the source attenuators are set.

        Parameters
        ----------
        port : int
            Test port number.

        mode_Str : str
            Options are: AUTO, MAN, and LNO

        Returns
        -------
        None.

        """
        self.write('SOUR:POW%d:ATT:MODE ' % port + mode_str)

    def _setPort1PowerAttenMode(self, mode_str: str):
        """
        Set how the source attenuators are set on port 1.

        Parameters
        ----------
        mode_Str : str
            Options are: AUTO, MAN, and LNO

        Returns
        -------
        None.

        """
        self.write('SOUR:POW1:ATT:MODE ' + mode_str)

    def _setSourcePowerMode(self, port: int, mode_str: str):
        """
        Set source power mode.

        Parameters
        ----------
        port : int
            Test port number

        mode_str : str
            Options: ON, OFF

        Returns
        -------
        None.

        """
        self.write('SOUR:POW%d:STAT %s' % (port, mode_str))

    def _setPort1SourcePowerMode(self, mode_str: str):
        """
        Set source power mode of port 1.

        Parameters
        ----------
        mode_str : str
            Options: ON, OFF

        Returns
        -------
        None.

        """
        self.write('SOUR:POW1:STAT %s' % (mode_str))

    def _setSourcePureCW(self, on: bool):
        """
        Set source pure CW mode.

        Pure CW mode prevents power drops, phase discontinuities at the start
        of a sweep. (as of 20230608, untested)

        Parameters
        ----------
        on: bool
            If True, turn on pure CW mode.

        Returns
        -------
        None.

        """
        if on:
            self.write('SOUR:POW:PUCW ON')

        else:
            self.write('SOUR:POW:PUCW OFF')

    # """Specifies whether the IF Bandwidth resolution can be set independently for each segment."""
    def _setSegmentBWControl(self, on: bool = True):
        """
        Set whether or not IF bandwidth resolutions can be set independently for each segment.

        Parameters
        ----------
        on : bool, optional
            If True, the IF bandwidth of segments can be controlled
            independently. The default is True.

        Returns
        -------
        None.

        """
        if on:
            self.write('SENS:SEGM:BWID:CONT ON')

        else:
            self.write('SENS:SEGM:BWID:CONT OFF')

    def _setSegmentPowerControl(self, on: bool = True):
        """
        Set whether or not power level can be set independently for each segment.

        Parameters
        ----------
        on : bool, optional
            If True, power level can be set independently for each segment.
            The default is True.

        Returns
        -------
        None.

        """
        if on:
            self.write('SENS:SEGM:POW:CONT ON')

        else:
            self.write('SENS:SEGM:POW:CONT OFF')

    def _setSegmentPowerLevel(self, port: int, level: float, seg: int = 1):
        """
        Set segment power level.

        Calling this function enables independent segment power control.

        Parameters
        ----------
        port : int
            Test port number. Ignored by ZVA67.

        level : float
            Power level in dBm

        seg : int, optional
            Segment number. The default is 1.

        Returns
        -------
        None.

        """
        self.write('SENS:SEGM%d:POW%d:LEV %d' % (seg, port, level))

    def _setSegmentNumPoints(self, numPts: int, seg: int = 1):
        """
        Set segment number of points.

        Parameters
        ----------
        numPts : int
            Number of sweep points.

        seg : int, optional
            Segment number. The default is 1.

        Returns
        -------
        None.

        """
        self.write('SENS:SEGM%d:SWE:POIN %d' % (seg, numPts))

    def _setSegmentFreqStartStop(self, fstart: float, fstop: float, seg: int = 1):
        """
        Set segment start and stop frequencies.

        Parameters
        ----------
        fstart : float
            Sweep start frequency in Hz.

        fstop : float
            Sweep stop frequency in Hz.

        seg : int, optional
            Segment number. The default is 1.

        Returns
        -------
        None.

        """
        self.write('SENS:SEGM%d:FREQ:STAR %E' % (seg, fstart))
        self.write('SENS:SEGM%d:FREQ:STOP %E' % (seg, fstop))

    def _setSegmentOnOff(self, on: bool = True, seg: int = 1):
        """
        Enable or disable a segment.

        Parameters
        ----------
        on : bool, optional
            If True, enable segment. The default is True.

        seg : int, optional
            Segment number. The default is 1.

        Returns
        -------
        None.

        """
        if on:
            self.write('SENS:SEGM%d ON' % seg)
        else:
            self.write('SENS:SEGM%d OFF' % seg)

    def _clearSegments(self):
        self.write('SENSe:SEGMent:DELete:ALL')

    # I assume the seg option is number of segments. If I am wrong please correct the doc string -Zenn
    def _addSegment(self, turnOn: bool = True, seg: int = 1):
        """
        Add segment.

        Parameters
        ----------
        turnOn : bool, optional
            If True, enable segment. The default is True.

        seg : int, optional
            Number of segments to add. The default is 1.

        Returns
        -------
        None.

        """
        self.write('SENS:SEGM%d:ADD' % seg)
        if turnOn:
            self._setSegmentOnOff(seg, True)

    def _setSourcePowerLevel(self, level: float):
        """
        Set the source power level.

        All test ports are affected.

        Parameters
        ----------

        level : float
            Power level in dBm. Range: -54 to +20. This range was determined
            through testing.

        Returns
        -------
        None.

        """
        # Note: the ZVA67 does not give the user independent control of the
        # different sources in one channel. All of the rest of the code in this
        # class is written assuming only only channel 1 is used
        self.write('SOUR%d:POW%d %f' % (1, 1, level))

    # # Stepped rather than continuously swept frequency
    def _setSweepIsStepped(self, on: bool):
        """
        Set whether or not sweeps are stepped.

        Parameters
        ----------
        on : bool
            If True, stepped sweep

        Returns
        -------
        None.

        """
        if on:
            self.write('SENS:SWE:GEN STEP')

        else:
            self.write('SENS:SWE:GEN ANALOG')

    def _setSweepType(self, inStr: str):
        """
        Set sweep type.

        Parameters
        ----------
        inStr : str
            Options are LIN, LOG, SEGM, and CW.

            POWER is also an option, but most of the commands to change
            power sweep settings are not implemented yet.

        Returns
        -------
        None.

        """
        if 'log' in inStr.lower():
            self.write('SENS:SWE:TYPE LOG')

        elif 'cw' in inStr.lower():
            self.write('SENS:SWE:TYPE CW')

        elif 'segm' in inStr.lower():
            self.write('SENS:SWE:TYPE SEGMent')

        else:
            self.write('SENS:SWE:TYPE LIN')

    def _setSweepTime(self, swe_time: float):
        """
        Set sweep time.

        Parameters
        ----------
        swe_time : float
            Sweep time in seconds.

        Returns
        -------
        None.

        """
        self.write('SENS:SWE:TIME ' + str(swe_time))  # time in seconds

    def _setDisplayType(self, displayType: str):
        """
        Set display state.

        Parameters
        ----------
        displayType : str, optional
            Specifies how to display data. There are lots of options, see manual.

        Returns
        -------
        None.

        """
        self.write('CALC1:FORM ' + displayType)

    def _setVisaTimeout(self, timeoutMillis: float):
        """
        Set visa timeout.

        Parameters
        ----------
        timeoutMillis : float
            timeout in milliseconds.

        Returns
        -------
        None.

        """
        self.visa_resource.timeout = timeoutMillis

    def _setupParameters(self, paramList: list, displayType: str = 'MLOG'):
        """
        Sets up measurement sweeps.

        Parameters
        ----------
        paramList : list
            List items are strings. Ex: 'S11', 'A1',...

        displayType : str, optional
            Specifies how to display data. There are lots of options, see manual
            entry for CALC:FORM. The default is 'MLOG'.

        Returns
        -------
        None.

        """
        paramCount = len(paramList)
        kwargs = {'displayType': displayType}

        # Set up the common features on both parameter measurements
        for k in range(1, paramCount + 1):
            param = 'param%d' % k
            kwargs[param] = paramList[k - 1]

        self.setup(**kwargs)

    def _set_Y_DivNum(self, DIV: float):
        """
        Set the horizontal line spacing.

        Parameters
        ----------
        DIV : float
            The space between horizontal lines (divisions) on the display.
            The units depend on what kind of data are displayed.

        Returns
        -------
        None.

        """
        paramCount = VNA.getNumParams()
        for k in range(1, paramCount + 1):
            self.write('DISP:WIND1:TRAC%d:Y:PDIVision %d' % (k, DIV))

    def _set_Y_Ref_Level(self, REF: float):
        """
        Set the y axis reference value.

        Parameters
        ----------
        REF : float
            The reference value of they Y axis of the display. The units
            depend on what kind of data are displayed. This setting interacts
            with the reference position. The reference level is set to the
            reference position on the display.

        Returns
        -------
        None.

        """
        paramCount = VNA.getNumParams()
        for k in range(1, paramCount + 1):
            self.write('DISP:WIND1:TRAC%d:Y:RLEVel %d' % (k, REF))

    def _set_Y_Ref_Position(self, REF_pos: float):
        """
        Set the y axis position.

        Parameters
        ----------
        REF_pos : float
            The reference position of they Y axis of the display in percent.
            The top of the screen is 100 %, while the bottom is 0 %. This
            setting interacts with the reference level. The reference level
            is set to the reference position on the display.

        Returns
        -------
        None.

        """
        paramCount = VNA.getNumParams()
        for k in range(1, paramCount + 1):
            self.write('DISP:WIND1:TRAC%d:Y:RPOSition %d' % (k, REF_pos))

    @staticmethod
    def _segment_flist(frequencies: np.ndarray[float]) -> list[tuple]:
        """
        Generate a list of frequency list segment parameters.

        Parameters
        ----------
        frequencies : np.ndarray[float]
            Frequencies to generate segments for.

        Returns
        -------
        list[tuple]
            List of tuples of (fstart, fstop, N).

        """
        step_change = np.diff(np.diff(frequencies))
        seg_bounds = np.logical_not(np.isclose(step_change, 0, atol=1e-3))
        seg_bounds = np.where(seg_bounds)[0]
        seg_bounds = np.append(seg_bounds, len(frequencies) - 1)
        seg_bounds = np.append(-1, seg_bounds)
        segments = []
        for i in range(1, len(seg_bounds)):
            fstart = frequencies[seg_bounds[i - 1] + 1]
            fstop = frequencies[seg_bounds[i]]
            N = seg_bounds[i] - seg_bounds[i - 1]
            segments.append((fstart, fstop, N))
        return segments

    def _writeFile(
        self,
        filename: str,
        frequencyList: list,
        waveDataList: list,
        header: str = '',
        fileExt: str = '.w2p',
    ):
        """
        Writes data to a file.

        Frequencies and waveData can be numpy arrays or lists of arrays to
        write several acquisitions into one file. note that frequencies can
        overlap if you're not careful.

        Parameters
        ----------
        filename : str
            Filename, including path and extension.

        frequencyList : list
            List of numpy arrays of the type returned by fetch_data.
            A single numpy array of this type will work as well.

        waveDataList : np.ndarray
            List of numpy arrays of the type returned by fetch_data.
            A single numpy array of this type will work as well.

        header : str, optional
            Extra string to write at top of file. The default is ''.

        fileExt : str, optional
            File extension. The default is '.w2p'.

        Returns
        -------
        None.

        """
        # Open the file
        # NumPoints = self.getNumSweepPts()
        if isinstance(frequencyList, np.ndarray) and isinstance(
            waveDataList, np.ndarray
        ):
            frequencyList = [frequencyList]
            waveDataList = [waveDataList]

        if os.path.isfile(filename):
            filename = filename.split('.')[0] + '_Repeat1' + fileExt
            counter = 1
            # if Repeat1 exists, we go on to Repeat2, etc., until we find a file name that doesn't already exist
            while os.path.isfile(filename):
                filename = (
                    filename[0 : len(filename) - 4 - len(str(counter))]
                    + str(counter + 1)
                    + fileExt
                )
                counter = counter + 1
            print('Duplicate filename!')
            print('New file name: ' + filename)
        # Open file for write, overwriting file if it exits
        f = open(filename, 'w')

        # Write the comments section
        f.write('! Data description: VNA parameter measurements \n')
        f.write(
            '! Date: %s\n' % datetime.datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')
        )
        if isinstance(header, str) and len(header) > 0:
            f.write(header)

        # close the file
        f.close()
        # The numpy arrays could be combined first, but if we cared about
        # efficiency we wouldn't be using ASCII files
        for frequencies, waveData in zip(frequencyList, waveDataList):
            # write the data
            (rows, cols) = waveData.shape
            cols = cols + 1  # add 1 for freq
            dataOut = np.zeros((rows, cols))
            dataOut[:, 0] = frequencies * 1e-9
            dataOut[:, 1:] = waveData
            f = open(filename, 'ab')  # numpy.savetxt writes bytes
            fmtstr = ''
            for k in range(cols):
                fmtstr = fmtstr + '%+0.10e '
            np.savetxt(f, dataOut, fmtstr, newline='\r\n', delimiter=' ')
            f.close()
            del f
        print(filename, ' written')

    def initial_setup(self, **kwargs):
        """
        Put instrument into safe and known initial state.

        Parameters
        ----------
        **kwargs
            Optional keyword arguments. These will be sent to the setup function.

        Returns
        -------
        None.

        """
        super().initial_setup(**kwargs)
        self.write('*CLS')
        self.write('SYSTem:PRESet')  # Set VNA to factory default state -- S11
        # VNA should default to uncorrected, but set it anyway
        # self.write("SENSe1:CORRection:STATe OFF")  # Set calibration to OFF
        self.write('SRE 32')
        self.write('*ESE 1')
        self.write('ABORT;INITiate:CONTinuous OFF')
        self.write('FORM ASC,0')

        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        # at this point, the state should be uninit
        # set state to init so that we can call setup
        # but keep the state as init
        self.state = 'init'
        # self.write("CALCulate:PARameter:DEL:ALL")
        self.setup(**initial_settings)
        calState = self.query(':SENSe1:CORRection:STATe?')
        print('Correction state: ' + calState)

    def arm(self):
        """
        Arm the VNA so that it will measure a trace when triggered.

        Returns
        -------
        None.

        """
        super().arm()
        self.write('TRIG:SOUR IMM')
        self.write('SENS:SWE:MODE SINGle')
        self.write('*CLS')  # clear status register

    def trigger(self):
        """
        Start a measurement.

        Only works if the trigger source is set to MAN (manual). Otherwise,
        this method does nothing.

        Returns
        -------
        None.

        """
        super().trigger()
        self.meas_start_time = self.get_relative_time()
        self.write('INIT:IMM; *OPC; *WAI ')

    def fetch_data(
        self,
    ) -> tuple:
        """
        Fetch measurement data.

        Returns
        -------
        dict
           keys 'Frequency (GHz)', <param1>, <param2>, etc. Frequency is
           a 1-d array of floats. Each param is a 1d array
           of complex data. Params keys are the parameters passed in setup (e.g.
           a11, b11, etc...).
        """
        super().fetch_data()
        sweep_type = self._getSweepType()
        acceptable = ['LIN', 'LOG', 'SEGM']
        sweep_type = self._getSweepType()
        acceptable = ['LIN', 'LOG', 'SEGM']
        if sweep_type in acceptable:
            numPoints = self._getNumSweepPts()
            frequencies = self._getFrequencies()
            numParams = self._getNumParams()
            waveData = {}
            waveData['Frequency (GHz)'] = frequencies * 1e-9
            for k, param in zip(range(1, numParams + 1), self.setup_settings['params']):
                self.write(":CALCulate1:PARameter:SELect 'Param%d'" % k)
                rawdata = self.query(('CALC:DATA? SDATA'))
                datastr = rawdata.strip().split(',')
                # data = np.array(datastr).astype(float)
                data = np.array(
                    [
                        [float(datastr[x]), float(datastr[x + 1])]
                        for x in range(0, len(datastr), 2)
                    ]
                )
                data = data[:, 0] + 1.0j * data[:, 1]
                assert len(data) == len(frequencies)
                waveData[param] = data

        else:
            raise ValueError('Sweep type: ' + sweep_type + ' not implemented')
        return waveData

    def setup(
        self,
        flist_GHz: np.ndarray[float] = None,
        fstart_GHz: float = None,
        fstop_GHz: float = None,
        npoints: float = None,
        sweep_type: str = None,
        params: list[str] = None,
        power_dBm: float = None,
        IFBW: bool = None,
        average: int = None,
    ):
        """
        Change the settings of the VNA.

        Parameters
        ----------
        flist_GHz : np.ndarray[float], optional
            List of frequencies to sweep over.
            The default is None.
        fstart_GHz : float, optional
            Start frequency for a sweep. fstart, fstop, npoints, and sweep
            type must be provided all at once. The default is None.
        fstop_GHz : float, optional
            Stop frequency. fstart, fstop, npoints, and sweep
            type must be provided all at onceThe default is None.
        npoints : float, optional
            Number of points. fstart, fstop, npoints, and sweep
            type must be provided all at once. The default is None.
        sweep_type : str, {lin, log}
            Linear or logarithmic sweep. fstart, fstop, npoints, and sweep
            type must be provided all at once. The default is None.
        params : list[str], optional
            Parameters to measure (a11, b12, S11, etc). The default is None.
            Firs number is source port, second number is recieving port.
        power_dBm : float, optional
            Power to source. The default is None.
        IFBW : bool, optional
            Intermediate frequency bandwidth in Hz. The default is None.
        average: int, optional
            If provided, the VNA will average multiple passes. The default is 0.
            Adjusting this setting will clear the average state on the VNA.
        Raises
        ------
        ValueError
            DESCRIPTION.

        Returns
        -------
        None.

        """

        super().setup(
            flist_GHz=flist_GHz,
            fstart_GHz=fstart_GHz,
            fstop_GHz=fstop_GHz,
            npoints=npoints,
            sweep_type=sweep_type,
            params=params,
            power_dBm=power_dBm,
            IFBW=IFBW,
        )

        if params is not None:
            if type(params) is str:
                raise ValueError('Expected list object.')

            resp = self.query('DISPlay:WINDow1:STATE?')
            if '0' in resp:
                self.write('DISPlay:WINDow1:STATE ON')

            self.write('CALC1:PAR:DEL:ALL')

            k = 1
            param = 'param%d' % k
            for param_name in params:
                self.validate_param(param_name)
                param_name = PARAMETER_ALIAS[param_name]

                self.write("CALC:PAR:DEF 'param%d', %s" % (k, param_name))
                self.write("DISP:WIND1:TRAC%d:FEED 'param%d'" % (k, k))
                k += 1
                param = 'param%d' % k

            resp = self.query('CALC:PAR:CAT?')
            print('Parameter setup:\n' + resp)

            paramCount = self._getNumParams()
            for k in range(1, paramCount + 1):
                self.write('DISP:WIND1:TRAC:Y:AUTO ONCE Trc%s' % (k))

        # aliases, for compatibility with RF_source classes
        if power_dBm is not None:
            self._setSourcePowerLevel(power_dBm)

        sweep_settings = [fstart_GHz, fstop_GHz, npoints, sweep_type]
        if any([ss is not None for ss in sweep_settings]):
            if not all([ss is not None for ss in sweep_settings]):
                raise ValueError(
                    'fstart, fstop, npoints, and sweep type must be provided all at once'
                )
            if flist_GHz is not None:
                raise ValueError(
                    'flist_GHz cant be provided at same time as a sweep. Conflicting settings.'
                )
            if sweep_type not in ['lin', 'log']:
                raise ValueError('Sweep type must be lin or log')
            self._setSweepType(sweep_type.upper())
            self._setFreqStartStop(fstart_GHz * 1e9, fstop_GHz * 1e9)
            self._setNumSweepPts(npoints)

        # if provided, use to genereate a series of segments
        if flist_GHz is not None:
            segments = self._segment_flist(flist_GHz)
            self._clearSegments()
            self.write('SENSe:SEGMent:DELete:ALL')
            assert int(self.query('SENS:SEGM:COUNt?')) == 0
            for i, (start, stop, n) in enumerate(segments):
                self._addSegment(turnOn=True, seg=i + 1)
                self._setSegmentFreqStartStop(start * 1e9, stop * 1e9, seg=i + 1)
                self._setSegmentNumPoints(numPts=n, seg=i + 1)
            assert int(self.query('SENS:SEGM:COUNt?')) == len(segments)
            self._setSweepType('SEGM')

        if IFBW is not None:
            self._setIFBW(IFBW)

        if average is not None:
            if average == 0:
                self._setAverageState(False)
            else:
                self.write('SENS:AVER:CLE')
                self._setAverageState(True)
                self._setAverageNum(average)

    def query_state(self) -> str:
        """
        Checks the state of the machine according to state model.

        Returns
        -------
        state : str
            Current state of the instrument.

        """
        # if not measuring, return saved state
        stb = self.read_stb()

        if get_bit(stb, 32) and (self.state == 'armed' or self.state == 'measuring'):
            self.state = 'data_available'

        # otherwise return measuring
        return self.state

    def do_after_group_trigger(self):
        """
        Run post-trigger commands after an external trigger event.

        Returns
        -------
        None.

        """
        self.meas_start_time = self.get_relative_time()
        self.write('*TRG')

    def raise_errors(self):
        """
        Query the status of the instrument.

        If there are errors, raise them as Python errors.

        Raises
        ------
        InstrumentError
            Raises an instrument error when the instrument claims it has errors or is in an error state.

        Returns
        -------
        None.

        """
        resp = self.query('SYST:ERR:ALL?')
        if resp != '0,"No error"\n':
            raise InstrumentError(resp)

    def get_errors(self):
        """
        Query the status of the instrument.

        Returns
        -------
        str
            Error message

        """
        resp = self.query('SYST:ERR:ALL?')
        if resp != '0,"No error"\n':
            return resp


if __name__ == '__main__':
    rm = visa.ResourceManager()
    intf = rm.open_resource('GPIB0::INTFC')
    VNA = VNA('GPIB0::20::INSTR', resource_manager=rm)

    # Linear Sweep
    VNA.setup(
        power_dBm=5,
        IFBW=1000,
        params=['a11', 'b11'],
        fstart_GHz=0.1,
        fstop_GHz=50,
        npoints=100,
        sweep_type='lin',
    )

    VNA.arm()
    VNA.trigger()
    VNA.wait_until_data_available(10)
    data = VNA.fetch_data()

    import matplotlib.pyplot as plt

    plt.close('all')
    fig, ax = plt.subplots(1, 1)
    fig.suptitle('Linear Sweep')
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['b11'])), 'o-', label='b11'
    )
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['a11'])), 'o-', label='a11'
    )
    ax.legend(loc='best')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Parameter (dB)')

    # Logarithmic Sweep
    VNA.setup(
        power_dBm=5,
        IFBW=1000,
        params=['a11', 'b11'],
        fstart_GHz=0.1,
        fstop_GHz=50,
        npoints=100,
        sweep_type='log',
    )

    VNA.arm()
    VNA.trigger()
    VNA.wait_until_data_available(10)
    data = VNA.fetch_data()

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1)
    fig.suptitle('Log Sweep')
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['b11'])), 'o-', label='b11'
    )
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['a11'])), 'o-', label='a11'
    )
    ax.legend(loc='best')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Parameter (dB)')

    # Frequency List Sweep
    VNA.setup(
        power_dBm=5,
        IFBW=1,
        params=['a11', 'b11'],
        flist_GHz=np.sort(np.random.random(10)),
    )

    VNA.arm()
    VNA.trigger()
    VNA.wait_until_data_available(10)
    data = VNA.fetch_data()

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1)
    fig.suptitle('Frequency List')
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['b11'])), 'o-', label='b11'
    )
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['a11'])), 'o-', label='a11'
    )
    ax.legend(loc='best')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Parameter (dB)')
