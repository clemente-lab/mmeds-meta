import mmeds.validate as valid
import pandas as pd
import mmeds.config as fig
from glob import glob
from pathlib import Path
from mmeds.util import log

error_files = glob(str(fig.TEST_PATH / 'validation_files/validate_error*'))
warning_files = glob(str(fig.TEST_PATH / 'validation_files/validate_warning*'))


def test_validate_mapping_files():
    errors, warnings, study_name, subjects = valid.validate_mapping_file(fig.TEST_METADATA)
    assert not errors
    assert not warnings


def test_error_files():
    for test_file in error_files:
        name = Path(test_file).name
        error = ' '.join(name.split('.')[0].split('_')[2:])
        log('Testing Error file {}'.format(name))
        errors, warnings, study_name, subjects = valid.validate_mapping_file(test_file)

        log(errors[0])
        # Check the correct error is raised
        assert error in errors[0].lower()

        # Check the messages are foramtted correctly
        parts = errors[0].split('\t')
        assert len(parts) == 3
        assert parts[0].strip('-').isnumeric()
        assert parts[1].strip('-').isnumeric()

def test_warning_files():
    for test_file in warning_files:
        name = Path(test_file).name
        warning = ' '.join(name.split('.')[0].split('_')[2:])
        log('Testing Warning file {}'.format(name))
        warnings, warnings, study_name, subjects = valid.validate_mapping_file(test_file)

        # Check the correct warning is raised
        assert warning in warnings[0].lower()

        # Check the messages are foramtted correctly
        parts = warnings[0].split('\t')
        log(parts)
        log(parts[1].strip('-'))
        assert len(parts) == 3
        assert parts[0].strip('-').isnumeric()
        assert parts[1].strip('-').isnumeric()
