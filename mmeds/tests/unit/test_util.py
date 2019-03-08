from mmeds import util
from mmeds.error import InvalidConfigError
from mmeds.validate import validate_mapping_file
from pathlib import Path
from pytest import raises
from tempfile import gettempdir
from tidylib import tidy_document
from pandas import read_csv
import mmeds.config as fig
import hashlib as hl
import os


def test_is_numeric():
    assert util.is_numeric('45') is True
    assert util.is_numeric('4.5') is True
    assert util.is_numeric('r.5') is False
    assert util.is_numeric('5.4.5') is False
    assert util.is_numeric('r5') is False
    assert util.is_numeric('5r') is False
    assert util.is_numeric('2016-12-01') is False


def test_create_local_copy():
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


def test_get_valid_columns():
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

    columns, col_types = util.get_valid_columns(fig.TEST_METADATA, 'Ethnicity,Nationality')
    assert columns == 'Ethnicity,Nationality'.split(',')

    with raises(InvalidConfigError) as e_info:
        columns, col_types = util.get_valid_columns(fig.TEST_METADATA, 'Ethnicity,BarSequence,Nationality,StudyName')
    assert 'Invalid metadata column' in e_info.value.message

    with raises(InvalidConfigError) as e_info:
        columns, col_types = util.get_valid_columns(fig.TEST_METADATA,
                                                    'Ethnicity,BarcodeSequence,Nationality,StudyName')
    assert 'selected for analysis' in e_info.value.message


def test_load_config_file():
    # Test when no config is given
    config = util.load_config(None, fig.TEST_METADATA)
    assert len(config.keys()) == 6

    config = util.load_config(Path(fig.TEST_CONFIG_ALL).read_text(), fig.TEST_METADATA)
    assert len(config['taxa_levels']) == 7

    # Check the config file fail states
    with raises(InvalidConfigError) as e_info:
        config = util.load_config(Path(fig.TEST_CONFIG_1).read_text(), fig.TEST_METADATA)
    assert 'Missing parameter' in e_info.value.message

    with raises(InvalidConfigError) as e_info:
        config = util.load_config(Path(fig.TEST_CONFIG_2).read_text(), fig.TEST_METADATA)
    assert 'Invalid metadata column' in e_info.value.message

    with raises(InvalidConfigError) as e_info:
        config = util.load_config(Path(fig.TEST_CONFIG_3).read_text(), fig.TEST_METADATA)
    assert 'Invalid parameter' in e_info.value.message


def test_mmeds_to_MIxS():
    tempdir = Path(gettempdir())
    util.mmeds_to_MIxS(fig.TEST_METADATA, tempdir / 'MIxS.tsv')
    util.MIxS_to_mmeds(tempdir / 'MIxS.tsv', tempdir / 'mmeds.tsv')
    assert (tempdir / 'mmeds.tsv').read_bytes() == Path(fig.TEST_METADATA).read_bytes()

    util.MIxS_to_mmeds(fig.TEST_MIXS, tempdir / 'new_mmeds.tsv')
    assert (tempdir / 'new_mmeds.tsv').is_file()


def test_generate_error_html():
    with open(fig.TEST_METADATA_1) as f:
        errors, warnings, study_name, subjects = validate_mapping_file(f)
    html = util.generate_error_html(fig.TEST_METADATA_1, errors, warnings)
    # Check that the html is valid
    document, errors = tidy_document(html)
    util.log(errors)
    assert not errors


def test_copy_metadata():
    tempdir = Path(gettempdir())
    util.copy_metadata(fig.TEST_METADATA, tempdir / 'new_metadata.tsv')
    df = read_csv(tempdir / 'new_metadata.tsv', header=[0, 1], skiprows=[2, 3, 4], sep='\t')
    assert df['AdditionalMetaData']['Together'].any()
    assert df['AdditionalMetaData']['Separate'].any()


def test_load_html():
    page = util.load_html('welcome', title='Welcome', user='David')
    page = util.insert_error(page, 22, 'There was a problem')
    page = util.insert_html(page, 22, 'There was a problem')
    page = util.insert_warning(page, 22, 'There was a problem')
    # Check that the html is valid
    document, errors = tidy_document(page)
    util.log(errors)
    # Assert no errors, warnings are okay
    for warn in errors:
        assert not ('error' in warn or 'Error' in warn)


def test_send_email():
    args = {
        'email': 'test@test.com',
        'user': 'Dan',
        'analysis': 'qiime2-DeBlur',
        'study': 'SomeStudy',
        'cemail': 'ctest@ctest.com'
    }
    for message in ['upload', 'reset', 'change', 'analysis', 'error']:
        result = util.send_email(message, **args)


