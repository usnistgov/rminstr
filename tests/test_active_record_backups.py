from rminstr.data_structures import ActiveRecord
from rminstr.data_structures._data_record import LOCAL_BACKUPS
from pathlib import Path
import time
import os
import shutil

LOCAL_MUT = Path(__file__).parents[0] / 'mutable'


try:
    for f in os.listdir(LOCAL_BACKUPS):
        shutil.rmtree(LOCAL_BACKUPS / f)
except FileNotFoundError:
    pass


def test_temp_loss():
    measname = 'temp_loss'
    target = LOCAL_MUT / ('testdir_' + measname)
    moved = LOCAL_MUT / ('moved_' + measname)
    try:
        shutil.rmtree(target)
    except FileNotFoundError:
        pass
    try:
        shutil.rmtree(moved)
    except FileNotFoundError:
        pass

    output_dir = target.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with ActiveRecord(
        meas_name=measname,
        columns=['a', 'b'],
        maxlen=(5),
        output_dir=target,
    ) as rec:
        # persistently lose access to target directory
        for i in range(50):
            time.sleep(0.01)
            rec.update('a', i)
            if i == 10:
                os.rename(target, moved)

            elif i == 40:
                os.rename(moved, target)

    assert len(rec.check_missing_files()) == 0


def test_persistent_loss():
    measname = 'persistent_loss'
    target = LOCAL_MUT / ('testdir_' + measname)
    moved = LOCAL_MUT / ('moved_' + measname)
    try:
        shutil.rmtree(target)
    except FileNotFoundError:
        pass
    try:
        shutil.rmtree(moved)
    except FileNotFoundError:
        pass

    output_dir = target.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with ActiveRecord(
        meas_name=measname,
        columns=['a', 'b'],
        maxlen=(10),
        output_dir=target,
    ) as rec:
        # persistently lose access to target directory
        for i in range(50):
            time.sleep(0.01)
            rec.update('a', i)
            if i == 10:
                os.rename(target, moved)

    # can't find any files because it can't find the target directory
    assert len(rec.check_missing_files()) == 5


if __name__ == '__main__':
    test_temp_loss()
    test_persistent_loss()
