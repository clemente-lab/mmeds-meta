from unittest import TestCase
import mmeds.validate as valid
import mmeds.config as fig
from pathlib import Path


class ValidateTests(TestCase):
    def test_a_validate_mapping_files(self):
        """ Checks that the primary testing metadata files of each type validate without error """
        errors, warnings, subjects = valid.validate_mapping_file(fig.TEST_ANIMAL_SUBJECT,
                                                                 'Good_Study',
                                                                 'subject',
                                                                 None,
                                                                 'animal')
        assert not errors
        assert not warnings

        errors, warnings, subjects = valid.validate_mapping_file(fig.TEST_SPECIMEN,
                                                                 'Good_Study',
                                                                 'specimen',
                                                                 subjects,
                                                                 'animal')
        assert not errors
        assert not warnings

        errors, warnings, subjects = valid.validate_mapping_file(fig.TEST_SUBJECT,
                                                                 'Good_Study',
                                                                 'subject',
                                                                 None,
                                                                 'human')
        assert not errors
        assert not warnings

        errors, warnings, subjects = valid.validate_mapping_file(fig.TEST_SPECIMEN,
                                                                 'Good_Study',
                                                                 'specimen',
                                                                 subjects,
                                                                 'human')
        assert not errors
        assert not warnings

    def test_b_error_files(self):
        """ Checks that the metadata files altered for validation raise the appropriate errors """
        subject_ids = None
        for metadata_type in ['subject', 'specimen']:
            error_files = fig.TEST_PATH.glob('validation_files/{}_validate_error*'.format(metadata_type))
            for test_file in error_files:
                name = Path(test_file).name
                error = ' '.join(name.split('.')[0].split('_')[3:])
                errors, warnings, subjects = valid.validate_mapping_file(test_file,
                                                                         'Good_Study',
                                                                         metadata_type,
                                                                         subject_ids,
                                                                         'human')
                if subject_ids is None:
                    subject_ids = subjects

                # Check the correct error is raised
                assert error in errors[0].lower()

                # Check the messages are foramtted correctly
                parts = errors[0].split('\t')
                assert len(parts) == 3
                assert parts[0].strip('-').isnumeric()
                assert parts[1].strip('-').isnumeric()

    def test_c_warning_files(self):
        """ Checks that the metadata files altered for validation raise the appropriate warnings """
        subject_ids = None
        for metadata_type in ['subject', 'specimen']:
            warning_files = fig.TEST_PATH.glob('validation_files/{}_validate_warning*'.format(metadata_type))
            for test_file in warning_files:
                name = Path(test_file).name
                warning = ' '.join(name.split('.')[0].split('_')[3:])
                warnings, warnings, subjects = valid.validate_mapping_file(test_file,
                                                                           'Good_Study',
                                                                           metadata_type,
                                                                           subject_ids,
                                                                           'human')
                if subject_ids is None:
                    subject_ids = subjects

                # Check the correct warning is raised
                assert warning in warnings[0].lower()

                # Check the messages are foramtted correctly
                parts = warnings[0].split('\t')
                assert len(parts) == 3
                assert parts[0].strip('-').isnumeric()
                assert parts[1].strip('-').isnumeric()

    def test_d_valid_file(self):
        assert valid.valid_file(fig.TEST_ALIQUOT_UPLOAD, 'aliquot')
        assert not valid.valid_file(fig.TEST_ALIQUOT_UPLOAD, 'sample')
        assert valid.valid_file(fig.TEST_SAMPLE_UPLOAD, 'sample')
        assert not valid.valid_file(fig.TEST_SAMPLE_UPLOAD, 'aliquot')
