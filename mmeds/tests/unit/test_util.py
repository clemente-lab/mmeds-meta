from unittest import TestCase, skip
from mmeds import util
from mmeds.error import InvalidConfigError, InvalidSQLError
from mmeds.validate import validate_mapping_file
from pathlib import Path
from pytest import raises
from tempfile import gettempdir
from tidylib import tidy_document
from pandas import read_csv, DataFrame, MultiIndex
from numpy import nan
import Levenshtein as lev
import mmeds.config as fig
import hashlib as hl
import os


class UtilTests(TestCase):
    def test_load_stats(self):
        util.load_mmeds_stats()

    @skip
    def test_a_simplified_to_full(self):
        df = util.simplified_to_full(fig.TEST_SUBJECT_SIMPLIFIED, '/tmp/subject_df.tsv', 'subject')
        df2 = util.simplified_to_full(fig.TEST_SPECIMEN_SIMPLIFIED, '/tmp/specimen_df.tsv', 'specimen')
        errors, dwarnings, subjects = validate_mapping_file('/tmp/subject_df.tsv',
                                                            df2['Study']['StudyName'][4],
                                                            'subject',
                                                            [],
                                                            'human',
                                                            user=fig.TEST_USER)
        errors, warnings, subjects = validate_mapping_file('/tmp/specimen_df.tsv',
                                                           df2['Study']['StudyName'][5],
                                                           'specimen',
                                                           subjects,
                                                           'human',
                                                           user=fig.TEST_USER)
        for error in errors:
            print(error)
        for warning in warnings:
            print(warning)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_b_format_alerts(self):
        args = {
                'error': 'This is an error',
                'warning': 'This is an warning',
                'success': 'This is an success',
                }
        formatted = util.format_alerts(args)
        assert 'w3-pale-red' in formatted['error']
        assert 'w3-pale-yellow' in formatted['warning']
        assert 'w3-pale-green' in formatted['success']

    def test_c_load_metadata_template(self):
        util.load_metadata_template('human')
        util.load_metadata_template('animal')

    def test_d_is_numeric(self):
        assert util.is_numeric('45') is True
        assert util.is_numeric('4.5') is True
        assert util.is_numeric('r.5') is False
        assert util.is_numeric('5.4.5') is False
        assert util.is_numeric('r5') is False
        assert util.is_numeric('5r') is False
        assert util.is_numeric('2016-12-01') is False

    def test_e_create_local_copy(self):
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

    def test_f_get_valid_columns(self):
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

    def test_g_load_config_file(self):
        # Test when no config is given
        config = util.load_config(None, fig.TEST_METADATA, 'qiime2')
        for param in fig.CONFIG_PARAMETERS['qiime2']:
            assert config.get(param) is not None

        config = util.load_config(Path(fig.TEST_CONFIG_ALL), fig.TEST_METADATA, 'qiime2')
        assert len(config['taxa_levels']) == 7

        config = util.load_config(Path(fig.TEST_CONFIG_SUB), fig.TEST_METADATA, 'qiime2')
        assert config['sub_analysis'] == ['SpecimenBodySite']

        # Check the config file fail states
        with raises(InvalidConfigError) as e_info:
            config = util.load_config(Path(fig.TEST_CONFIG_1), fig.TEST_METADATA, 'qiime2')
        assert 'Missing parameter' in e_info.value.message

        with raises(InvalidConfigError) as e_info:
            config = util.load_config(Path(fig.TEST_CONFIG_2), fig.TEST_METADATA, 'qiime2')
        assert 'Invalid metadata column' in e_info.value.message

        with raises(InvalidConfigError) as e_info:
            config = util.load_config(Path(fig.TEST_CONFIG_3), fig.TEST_METADATA, 'qiime2')
        assert 'Invalid parameter' in e_info.value.message

        with raises(InvalidConfigError) as e_info:
            config = util.load_config(Path(fig.TEST_METADATA), fig.TEST_METADATA, 'qiime2')
        assert 'YAML format' in e_info.value.message

    def test_h_mmeds_to_MIxS(self):
        return  # TODO Either fix the test or deprecate the functionality
        tempdir = Path(gettempdir())
        util.mmeds_to_MIxS(fig.TEST_METADATA, tempdir / 'MIxS.tsv')
        util.MIxS_to_mmeds(tempdir / 'MIxS.tsv', tempdir / 'mmeds.tsv')
        assert (tempdir / 'mmeds.tsv').read_bytes() == Path(fig.TEST_METADATA).read_bytes()

        util.MIxS_to_mmeds(fig.TEST_MIXS, tempdir / 'new_mmeds.tsv')
        assert (tempdir / 'new_mmeds.tsv').is_file()

    def test_i_generate_error_html(self):
        errors, warnings, subjects = validate_mapping_file(fig.TEST_SUBJECT_ERROR,
                                                           'Good_Study',
                                                           'subject',
                                                           None,
                                                           'human')
        html = util.generate_error_html(fig.TEST_SUBJECT_ERROR, errors, warnings)
        # Check that the html is valid
        document, errors = tidy_document(html)
        assert not errors

    def test_j_copy_metadata(self):
        tempdir = Path(gettempdir())
        util.copy_metadata(fig.TEST_METADATA, tempdir / 'new_metadata.tsv')
        df = read_csv(tempdir / 'new_metadata.tsv', header=[0, 1], skiprows=[2, 3, 4], sep='\t')
        assert df['AdditionalMetaData']['Together'].any()
        assert df['AdditionalMetaData']['Separate'].any()

    def test_k_read_write_mmeds(self):
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

    def test_l_join_metadata(self):
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

    def test_m_quote_sql(self):
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
            util.quote_sql('{house}', house='asdf *$** ')

        self.assertEquals('select `HostSubjectId` from `Subjects`',
                          util.quote_sql('select {col} from {table}', col='HostSubjectId', table='Subjects'))

    def test_n_safe_dict(self):
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

    def test_o_parse_ICD(self):
        """ Test the parsing of ICD_codes """
        cols = MultiIndex.from_tuples([('ICDCode', 'ICDCode')])
        codes = [
            ['XXX.XXXX'],
            ['A19.XXXX'],
            ['Y33.XXXA'],
            ['V93.24XS'],
            [nan]
        ]
        df = DataFrame(codes, columns=cols)

        check_cols = MultiIndex.from_tuples([
            ('ICDCode', 'ICDCode'),
            ('IllnessBroadCategory', 'ICDFirstCharacter'),
            ('IllnessCategory', 'ICDCategory'),
            ('IllnessDetails', 'ICDDetails'),
            ('IllnessDetails', 'ICDExtension'),
        ])
        check_codes = [
            ['XXX.XXXX', 'X', nan, 'XXX', 'X'],
            ['A19.XXXX', 'A', 19.0, 'XXX', 'X'],
            ['Y33.XXXA', 'Y', 33.0, 'XXX', 'A'],
            ['V93.24XS', 'V', 93.0, '24X', 'S'],
            ['XXX.XXXX', 'X', nan, 'XXX', 'X'],
        ]
        check_df = DataFrame(check_codes, columns=check_cols)

        parsed_df = util.parse_ICD_codes(df)
        assert check_df.equals(parsed_df)

    def test_p_levenshtein_distance(self):
        """ Test the python-Levenshtein library's distance function """
        # To add more barcode tests, add tuples with format (string_1, string_2, expected_distance)
        test_barcodes = [
            ('', '', 0),
            ('ACTG', 'ACTG', 0),
            ('AAGGGGCC', 'AAGGGGCC', 0),
            ('GCTAAA', 'GCTAAC', 1),
            ('CTAG', 'CTA', 1),
            ('CCAGTG', 'CGACTG', 2),
            ('TTAAC', 'TTAACGA', 2),
            ('', 'TAG', 3),
            ('ACGGT', 'GCAATGT', 4),
            ('ACTGACTG', 'ACTGACTGACTGACTG', 8)
        ]

        for str1, str2, expected_dist in test_barcodes:
            actual_dist = lev.distance(str1, str2)
            assert expected_dist == actual_dist

    def test_q_metadata_concat_and_split(self):
        """ Test the concatenating of metadata for meta studies and splitting into subj-spec """
        entries = {'Test_Single_Short': ['L6S93', 'L6S95'],
                   'Test_Paired': ['L6S98', 'L6S99']}
        paths = {'Test_Single_Short':
                 '/home/runner/mmeds_server_data/studies/testuser_Test_Single_Short_0/full_metadata.tsv',
                 'Test_Paired':
                 '/home/runner/mmeds_server_data/studies/testuser_Test_Paired_0/full_metadata.tsv'}

        df = util.concatenate_metadata_subsets(entries, paths)
        subj_df, spec_df = util.split_metadata(df, new_study_name="New_Test_Study")
