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

            for test_file in sorted(list(error_files)):
                name = Path(test_file).name
                error = ' '.join(name.split('.')[0].split('_')[3:])
                errors, warnings, subjects = valid.validate_mapping_file(test_file,
                                                                         'Validate_Study',
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
                                                                           'Validate_Study',
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
        assert valid.valid_additional_file(fig.TEST_ALIQUOT_UPLOAD, 'aliquot')
        assert not valid.valid_additional_file(fig.TEST_ALIQUOT_UPLOAD, 'sample')
        assert valid.valid_additional_file(fig.TEST_SAMPLE_UPLOAD, 'sample')
        assert not valid.valid_additional_file(fig.TEST_SAMPLE_UPLOAD, 'aliquot')
        assert valid.valid_additional_file(fig.TEST_ADD_SUBJECT, 'subject')

    def test_e_generated_error_files(self):
        """
        Test all the error files generated by scripts/generate_test_tsv.py
        """
        
        top_dir = Path('/home/adamcantor22//mmeds-meta/test_files/validation_files/')
        sub_directories = ['blank_column_tests', 'na_column_tests', 'other_column_tests', 'number_column_tests', 'date_column_tests']

        # Get all sub directories to analyze
        total_directories = []
        for directory in sub_directories:
            total_directories.append(top_dir / directory / 'subject')
            total_directories.append(top_dir / directory / 'specimen')
            # total_directories.append(top_dir / 'misc_tests')

        good_subjects = valid.validate_mapping_file(fig.TEST_SUBJECT_SHORT, 'Short_Study', 'subject', None, 'human')[2]
        for directory in total_directories:
            for test_file in directory.glob('*.tsv'):

                # Generate headers for each file output
                length = len(test_file.name)
                bar_size = 70 
                bar = ''
                count = int((bar_size - length) / 2)
                for i in range(count):
                    bar += '='
                bar += ' ' + test_file.name + ' '
                for i in range(count):
                    bar += '='
                print(bar) 
        
                # Test subject files
                if test_file.parent.name == 'subject': 
                    try:
                        errors, warnings, subjects = valid.validate_mapping_file(test_file, 'Good_Study22', 'subject', None, 'human')
                        print('For', test_file.name, '\b:')
                        if len(errors) > 0:
                            print('\nErrors:')
                            for err in errors:
                                print(err)
                        else:
                            print('\nNo Errors Found')
                        if len(warnings) > 0:
                            print('\nWarnings:')
                            for warn in warnings:
                                print(warn)
                        else:
                            print('\nNo Warnings Found')
                        print('\n') 
                    except Exception as ex:
                        print('Exception', ex, 'of type', type(ex))
                        trace = tb.StackSummary.extract(tb.walk_tb(sys.exc_info()[2]))
                        for tr in trace:
                            print(tr)

                # Test specimen files
                else:
                    try:
                        errors, warnings, subjects = valid.validate_mapping_file(test_file, 'Short_Study', 'specimen', good_subjects, 'human')
                        print('For', test_file.name, '\b:')
                        if len(errors) > 0:
                            print('\nErrors:')
                            for err in errors:
                                print(err)
                        else:
                            print('\nNo Errors Found')
                        if len(warnings) > 0:
                            print('\nWarnings:')
                            for warn in warnings:
                                print(warn)
                        else:
                            print('\nNo Warnings Found')
                        print('\n')
                    except Exception as ex:
                        print('Exception', ex, 'of type', type(ex))
                        trace = tb.StackSummary.extract(tb.walk_tb(sys.exc_info()[2]))
                        for tr in trace:
                            print(tr)

       
