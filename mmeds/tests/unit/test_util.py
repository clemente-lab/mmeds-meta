from unittest import TestCase
from mmeds import util
from mmeds.error import InvalidConfigError, InvalidSQLError
from mmeds.validate import validate_mapping_file
from pathlib import Path
from pytest import raises
from tempfile import gettempdir
from tidylib import tidy_document
from pandas import read_csv
import mmeds.config as fig
import hashlib as hl
import os


class UtilTests(TestCase):
    def test_load_stats(self):
        util.load_mmeds_stats(True)

    def test_format_alerts(self):
        args = {
                'error': 'This is an error',
                'warning': 'This is an warning',
                'success': 'This is an success',
                }
        formatted = util.format_alerts(args)
        assert 'error' not in formatted
        assert 'warning' not in formatted
        assert 'success' not in formatted

    def test_load_metadata_template(self):
        util.load_metadata_template('human')
        util.load_metadata_template('animal')

    def test_is_numeric(self):
        assert util.is_numeric('45') is True
        assert util.is_numeric('4.5') is True
        assert util.is_numeric('r.5') is False
        assert util.is_numeric('5.4.5') is False
        assert util.is_numeric('r5') is False
        assert util.is_numeric('5r') is False
        assert util.is_numeric('2016-12-01') is False

    def test_create_local_copy(self):
        """ Test the creation of a new unique file. """
        h1 = hl.md5()
        h2 = hl.md5()
        with open(fig.TEST_METADATA, 'rb') as f:
            copy = util.create_local_copy(f, 'metadata.tsv', fig.TEST_DIR)
            f.seek(0, 0)  # Reset the file pointer
            data1 = f.read()
        h1.update(data1)
        hash1 = h1.hexdigest()

        with open(copy, 'rb') as f:
            data2 = f.read()
        os.remove(copy)
        h2.update(data2)
        hash2 = h2.hexdigest()

        assert hash1 == hash2

    def test_get_valid_columns(self):
        columns, col_types = util.get_valid_columns(fig.TEST_METADATA, 'all')
        for key in col_types.keys():
            assert key in columns

        # Test that only columns meeting the criteria get included
        columns, col_types = util.get_valid_columns(fig.TEST_CONFIG_METADATA, 'all')
        assert 'GoodColumnDiscrete' in columns
        assert 'GoodColumnContinuous' in columns
        assert 'BadColumnUniform' not in columns
        assert 'BadColumnDisparate' not in columns
        assert 'BadColumnEmpty' not in columns

        # Check that columns are correctly identified as continuous (True) or discrete (False)
        assert not col_types['GoodColumnDiscrete']
        assert col_types['GoodColumnContinuous']

        columns, col_types = util.get_valid_columns(fig.TEST_METADATA, ['Ethnicity', 'Nationality'])
        assert columns == 'Ethnicity,Nationality'.split(',')

        with raises(InvalidConfigError) as e_info:
            columns, col_types = util.get_valid_columns(fig.TEST_METADATA,
                                                        ['Ethnicity',
                                                         'BarSequence',
                                                         'Nationality',
                                                         'StudyName'])
        assert 'Invalid metadata column' in e_info.value.message

        with raises(InvalidConfigError) as e_info:
            columns, col_types = util.get_valid_columns(fig.TEST_METADATA,
                                                        ['Ethnicity',
                                                         'BarcodeSequence',
                                                         'Nationality',
                                                         'StudyName'])
        assert 'selected for analysis' in e_info.value.message

    def test_load_config_file(self):
        # Test when no config is given
        config = util.load_config(None, fig.TEST_METADATA)
        for param in fig.CONFIG_PARAMETERS:
            assert config.get(param) is not None

        config = util.load_config(Path(fig.TEST_CONFIG_ALL), fig.TEST_METADATA)
        assert len(config['taxa_levels']) == 7

        config = util.load_config(Path(fig.TEST_CONFIG_SUB), fig.TEST_METADATA)
        assert config['sub_analysis'] == ['SpecimenBodySite']

        # Check the config file fail states
        with raises(InvalidConfigError) as e_info:
            config = util.load_config(Path(fig.TEST_CONFIG_1), fig.TEST_METADATA)
        assert 'Missing parameter' in e_info.value.message

        with raises(InvalidConfigError) as e_info:
            config = util.load_config(Path(fig.TEST_CONFIG_2), fig.TEST_METADATA)
        assert 'Invalid metadata column' in e_info.value.message

        with raises(InvalidConfigError) as e_info:
            config = util.load_config(Path(fig.TEST_CONFIG_3), fig.TEST_METADATA)
        assert 'Invalid parameter' in e_info.value.message

    def test_mmeds_to_MIxS(self):
        return  # TODO Either fix the test or deprecate the functionality
        tempdir = Path(gettempdir())
        util.mmeds_to_MIxS(fig.TEST_METADATA, tempdir / 'MIxS.tsv')
        util.MIxS_to_mmeds(tempdir / 'MIxS.tsv', tempdir / 'mmeds.tsv')
        assert (tempdir / 'mmeds.tsv').read_bytes() == Path(fig.TEST_METADATA).read_bytes()

        util.MIxS_to_mmeds(fig.TEST_MIXS, tempdir / 'new_mmeds.tsv')
        assert (tempdir / 'new_mmeds.tsv').is_file()

    def test_generate_error_html(self):
        errors, warnings, subjects = validate_mapping_file(fig.TEST_SUBJECT_ERROR, 'subject', None, 'human')
        html = util.generate_error_html(fig.TEST_SUBJECT_ERROR, errors, warnings)
        # Check that the html is valid
        document, errors = tidy_document(html)
        assert not errors

    def test_copy_metadata(self):
        tempdir = Path(gettempdir())
        util.copy_metadata(fig.TEST_METADATA, tempdir / 'new_metadata.tsv')
        df = read_csv(tempdir / 'new_metadata.tsv', header=[0, 1], skiprows=[2, 3, 4], sep='\t')
        assert df['AdditionalMetaData']['Together'].any()
        assert df['AdditionalMetaData']['Separate'].any()

    def test_read_write_mmeds(self):
        tmpdir = Path(gettempdir())
        mdf = util.load_metadata(fig.TEST_METADATA)
        util.write_metadata(mdf, tmpdir / 'metadata_copy.tsv')

        h1 = hl.md5()
        h2 = hl.md5()
        h1.update(Path(fig.TEST_METADATA).read_bytes())
        h2.update((tmpdir / 'metadata_copy.tsv').read_bytes())
        hash1 = h1.hexdigest()
        hash2 = h2.hexdigest()

        assert hash1 == hash2

    def test_join_metadata(self):
        # Test joining human metadata
        subject = util.load_metadata(fig.TEST_SUBJECT)
        specimen = util.load_metadata(fig.TEST_SPECIMEN)
        df = util.join_metadata(subject, specimen, 'human')
        assert df is not None

        # Test joining animal metadata
        subject = util.load_metadata(fig.TEST_ANIMAL_SUBJECT)
        specimen = util.load_metadata(fig.TEST_SPECIMEN)
        df = util.join_metadata(subject, specimen, 'animal')
        assert df is not None

    def test_quote_sql(self):
        """ Test the qouting of sql """
        with self.assertRaises(AssertionError):
            util.quote_sql('some string', quote=';')
        with self.assertRaises(InvalidSQLError):
            util.quote_sql(23)
        with self.assertRaises(InvalidSQLError):
            util.quote_sql('{house}', house=23)
        with self.assertRaises(InvalidSQLError):
            util.quote_sql('{house}', house=100 * 'asdf')
        with self.assertRaises(InvalidSQLError):
            util.quote_sql('{house}', house='asdf *** ')

        self.assertEquals('select `HostSubjectId` from `Subjects`',
                          util.quote_sql('select {col} from {table}', col='HostSubjectId', table='Subjects'))

    def test_safe_dict(self):
        test_dict = util.SafeDict({
            'val1': 1,
            'val2': 2
        })

        # Assert the missing item is handled
        to_format = '{val1} is less than {val2} is less than {val3}'
        formatted = '1 is less than 2 is less than {val3}'
        self.assertEqual(to_format.format_map(test_dict), formatted)
        self.assertIn('val3', test_dict.missed)

        # Assert the missed set is updated
        test_dict['val3'] = 3
        all_formatted = '1 is less than 2 is less than 3'
        self.assertEqual(to_format.format_map(test_dict), all_formatted)
        self.assertNotIn('val3', test_dict.missed)
