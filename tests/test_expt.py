# -*- coding: utf-8 -*-
"""
Created on Sat Apr 12 07:34:10 2025

@author: dcg2
"""

from pathlib import Path
from rminstr.data_structures import ExptParameters

LOCAL_MUT = Path(__file__).parents[0] / 'sample_files'


def test_expt_parameter():
    ep = ExptParameters(
        [
            LOCAL_MUT / 'general_config.csv',
            LOCAL_MUT / 'HP34420A_ThermopoleMonitor.csv',
            LOCAL_MUT / 'RS_NRP75TWG_powermeter.csv',
            LOCAL_MUT / 'RS_SMA100B_as_RF_source.csv',
        ],
        LOCAL_MUT / 'runlist_gc.csv',
    )

    assert ep['stats_settings']['initial_wait'] == 3600
    assert type(ep['stats_settings']['initial_wait']) == float
    assert not ep['levelling_settings']['use_AM_levelling']
    assert type(ep['levelling_settings']['use_AM_levelling']) == bool
    assert ep['instruments']['RF_source']['initial_settings']['dBm_limit'] == 20
    assert (
        type(ep['instruments']['RF_source']['initial_settings']['dBm_limit']) == float
    )

    ep.advance()
    assert ep.config['Frequency_GHz'] == 0
    ep.advance()
    ep.advance()
    assert ep.config['Frequency_GHz'] == 0.2

if __name__ == '__main__':
    test_expt_parameter()
