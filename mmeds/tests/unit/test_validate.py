from unittest import TestCase
import mmeds.validate as valid
import mmeds.config as fig
from pathlib import Path
from mmeds.util import log


class ValidateTests(TestCase):
    def test_a_validate_mapping_files(self):
        errors, warnings, subjects = valid.validate_mapping_file(fig.TEST_ANIMAL_SUBJECT, 'subject', None, 'animal')
        assert not errors
        assert not warnings

        errors, warnings, subjects = valid.validate_mapping_file(fig.TEST_SUBJECT, 'subject', None, 'human')
        assert not errors
        assert not warnings

        errors, warnings, subjects = valid.validate_mapping_file(fig.TEST_SPECIMEN, 'specimen', subjects, None)
        assert not errors
        assert not warnings

    def test_b_error_files(self):
        subject_ids = None
        for metadata_type in ['subject', 'specimen']:
            error_files = fig.TEST_PATH.glob('validation_files/{}_validate_error*'.format(metadata_type))
            for test_file in error_files:
                name = Path(test_file).name
                error = ' '.join(name.split('.')[0].split('_')[3:])
                errors, warnings, subjects = valid.validate_mapping_file(test_file, metadata_type, subject_ids, 'human')
                if subject_ids is None:
                    subject_ids = subjects

                print('testing {}'.format(error))
                log(errors[0])
                # Check the correct error is raised
                assert error in errors[0].lower()

                # Check the messages are foramtted correctly
                parts = errors[0].split('\t')
                assert len(parts) == 3
                assert parts[0].strip('-').isnumeric()
                assert parts[1].strip('-').isnumeric()

    def test_c_warning_files(self):
        subject_ids = None
        for metadata_type in ['subject', 'specimen']:
            warning_files = fig.TEST_PATH.glob('validation_files/{}_validate_warning*'.format(metadata_type))
            for test_file in warning_files:
                name = Path(test_file).name
                warning = ' '.join(name.split('.')[0].split('_')[3:])
                log('Testing Warning file {}'.format(name))
                warnings, warnings, subjects = valid.validate_mapping_file(test_file, metadata_type,
                                                                           subject_ids, 'human')
                if subject_ids is None:
                    subject_ids = subjects

                # Check the correct warning is raised
                assert warning in warnings[0].lower()

                # Check the messages are foramtted correctly
                parts = warnings[0].split('\t')
                log(parts)
                log(parts[1].strip('-'))
                assert len(parts) == 3
                assert parts[0].strip('-').isnumeric()
                assert parts[1].strip('-').isnumeric()
