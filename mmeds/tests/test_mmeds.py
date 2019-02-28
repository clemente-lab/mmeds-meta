from mmeds import mmeds
from mmeds.error import InvalidConfigError
from pathlib import Path
from pytest import raises
from tempfile import gettempdir
from tidylib import tidy_document
import mmeds.config as fig
import hashlib as hl
import os
import pandas as pd


def test_is_numeric():
    assert mmeds.is_numeric('45') is True
    assert mmeds.is_numeric('4.5') is True
    assert mmeds.is_numeric('r.5') is False
    assert mmeds.is_numeric('5.4.5') is False
    assert mmeds.is_numeric('r5') is False
    assert mmeds.is_numeric('5r') is False
    assert mmeds.is_numeric('2016-12-01') is False


def test_create_local_copy():
    """ Test the creation of a new unique file. """
    h1 = hl.md5()
    h2 = hl.md5()
    with open(fig.TEST_METADATA, 'rb') as f:
        copy = mmeds.create_local_copy(f, 'metadata.tsv', fig.TEST_DIR)
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


def test_check_header():
    errors = mmeds.check_header('1', 0)
    assert 'Number Header' in errors[0]

    errors = mmeds.check_header('n.a.', 0)
    assert 'NA Header' in errors[0]

    errors = mmeds.check_header('\\', 0)
    assert 'Illegal Header' in errors[0]

    errors = mmeds.check_header('social_security', 0)
    assert 'PHI Header' in errors[0]

    errors = mmeds.check_header(' France', 0)
    assert 'Illegal Header' in errors[0]
    assert 'Whitespace Header' in errors[1]


def test_check_column():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors, warnings = mmeds.check_column(test_df['Test']['StudyName'], 0)
    assert 'Multiple studies in one' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Non-standard1'], 0)
    assert 'Non standard NA format' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Non-standard2'], 0)
    assert 'Non standard NA format' in errors[0]

    #  errors, warnings = mmeds.check_column(test_df['Test']['MixedTypes'], 0)
    #  assert 'Mixed Type' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['EmptyCell1'], 0)
    #  assert 'Mixed Type' in errors[0]
    assert 'Empty cell value' in errors[1]

    errors, warnings = mmeds.check_column(test_df['Test']['EmptyCell2'], 0)
    assert 'Empty cell value' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Categorical'], 0)
    assert 'Categorical Data' in warnings[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Whitespace'], 0)
    assert 'Whitespace' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['BadDate'], 0)
    assert 'Date Error' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['GoodDate'], 0)
    assert len(errors) == 0 and len(warnings) == 0

    errors, warnings = mmeds.check_column(test_df['Test']['GoodString'], 0)
    assert len(errors) == 0 and len(warnings) == 0

    errors, warnings = mmeds.check_column(test_df['Test']['GoodNumber'], 0)
    assert len(errors) == 0 and len(warnings) == 0


def test_check_table_column():
    pass


def test_check_table():
    pass


def test_check_duplicates():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = mmeds.check_duplicates(test_df['Test']['GoodNumber'], 0)
    assert len(errors) == 0

    errors = mmeds.check_duplicates(test_df['Test']['GoodString'], 0)
    assert 'Duplicate Value' in errors[0]


def test_check_lengths():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = mmeds.check_lengths(test_df['Test']['GoodBarcodes'], 0)
    assert len(errors) == 0

    errors = mmeds.check_lengths(test_df['Test']['BadBarcodes'], 0)
    assert 'different length from other' in errors[0]


def test_check_barcode_chars():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = mmeds.check_barcode_chars(test_df['Test']['GoodBarcodes'], 0)
    assert len(errors) == 0

    errors = mmeds.check_barcode_chars(test_df['Test']['BadBarcodes'], 0)
    assert 'Invalid BarcodeSequence' in errors[0]


def test_check_duplicate_cols():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    headers = list(test_df['Test'].axes[1])
    dups = mmeds.check_duplicate_cols(headers)
    assert len(dups) > 0


def test_check_dates():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = mmeds.check_dates(test_df['BadDates'])
    assert 'earlier than start date' in errors[0]

    errors = mmeds.check_dates(test_df['GoodDates'])
    assert len(errors) == 0


def test_validate_mapping_files():
    with open(fig.TEST_METADATA) as f:
        errors, warnings, study_name, subjects = mmeds.validate_mapping_file(f)
    assert not errors
    assert not warnings

    with open(fig.TEST_METADATA_1) as f:
        errors, warnings, study_name, subjects = mmeds.validate_mapping_file(f)
    assert len(errors) == 1
    assert 'Empty Cell' in errors[-1]
    assert len(warnings) == 1
    assert 'Categorical Data Warning' in warnings[-1]

    with open(fig.TEST_METADATA_VALID) as f:
        errors, warnings, study_name, subjects = mmeds.validate_mapping_file(f)
    assert 'Missing required fields' in errors[-1]



def test_get_valid_columns():
    columns, col_types = mmeds.get_valid_columns(fig.TEST_METADATA, 'all')
    for key in col_types.keys():
        assert key in columns

    # Test that only columns meeting the criteria get included
    columns, col_types = mmeds.get_valid_columns(fig.TEST_CONFIG_METADATA, 'all')
    assert 'GoodColumnDiscrete' in columns
    assert 'GoodColumnContinuous' in columns
    assert 'BadColumnUniform' not in columns
    assert 'BadColumnDisparate' not in columns
    assert 'BadColumnEmpty' not in columns

    # Check that columns are correctly identified as continuous (True) or discrete (False)
    assert not col_types['GoodColumnDiscrete']
    assert col_types['GoodColumnContinuous']

    columns, col_types = mmeds.get_valid_columns(fig.TEST_METADATA, 'Ethnicity,Nationality')
    assert columns == 'Ethnicity,Nationality'.split(',')

    with raises(InvalidConfigError) as e_info:
        columns, col_types = mmeds.get_valid_columns(fig.TEST_METADATA, 'Ethnicity,BarSequence,Nationality,StudyName')
    assert 'Invalid metadata column' in e_info.value.message

    with raises(InvalidConfigError) as e_info:
        columns, col_types = mmeds.get_valid_columns(fig.TEST_METADATA,
                                                     'Ethnicity,BarcodeSequence,Nationality,StudyName')
    assert 'selected for analysis' in e_info.value.message


def test_load_config_file():
    # Test when no config is given
    config = mmeds.load_config(None, fig.TEST_METADATA)
    assert len(config.keys()) == 6

    config = mmeds.load_config(Path(fig.TEST_CONFIG_ALL).read_text(), fig.TEST_METADATA)
    assert len(config['taxa_levels']) == 7

    # Check the config file fail states
    with raises(InvalidConfigError) as e_info:
        config = mmeds.load_config(Path(fig.TEST_CONFIG_1).read_text(), fig.TEST_METADATA)
    assert 'Missing parameter' in e_info.value.message

    with raises(InvalidConfigError) as e_info:
        config = mmeds.load_config(Path(fig.TEST_CONFIG_2).read_text(), fig.TEST_METADATA)
    assert 'Invalid metadata column' in e_info.value.message

    with raises(InvalidConfigError) as e_info:
        config = mmeds.load_config(Path(fig.TEST_CONFIG_3).read_text(), fig.TEST_METADATA)
    assert 'Invalid parameter' in e_info.value.message


def test_mmeds_to_MIxS():
    tempdir = Path(gettempdir())
    mmeds.log(tempdir)
    mmeds.mmeds_to_MIxS(fig.TEST_METADATA, tempdir / 'MIxS.tsv')
    mmeds.MIxS_to_mmeds(tempdir / 'MIxS.tsv', tempdir / 'mmeds.tsv')
    assert (tempdir / 'mmeds.tsv').read_bytes() == Path(fig.TEST_METADATA).read_bytes()


def test_generate_error_html():
    with open(fig.TEST_METADATA_1) as f:
        errors, warnings, study_name, subjects = mmeds.validate_mapping_file(f)
    html = mmeds.generate_error_html(fig.TEST_METADATA_1, errors, warnings)
    # Check that the html is valid
    document, errors = tidy_document(html)
    mmeds.log(errors)
    assert not errors
