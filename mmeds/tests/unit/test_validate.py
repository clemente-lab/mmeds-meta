import mmeds.validate as valid
import pandas as pd
import mmeds.config as fig


def test_validate_mapping_files():
    errors, warnings, study_name, subjects = valid.validate_mapping_file(fig.TEST_METADATA)
    assert not errors
    assert not warnings

    errors, warnings, study_name, subjects = valid.validate_mapping_file(fig.TEST_METADATA_1)
    assert len(errors) == 1
    assert 'AdditionalMetaData Column Error' in errors[-1]
    assert len(warnings) == 1
    assert 'Categorical Data Warning' in warnings[-1]

"""

def test_check_header():
    errors = valid.check_header('1', 0)
    assert 'Number Header' in errors[0]

    errors = valid.check_header('n.a.', 0)
    assert 'NA Header' in errors[0]

    errors = valid.check_header('\\', 0)
    assert 'Illegal Header' in errors[0]

    errors = valid.check_header('social_security', 0)
    assert 'PHI Header' in errors[0]

    errors = valid.check_header(' France', 0)
    assert 'Illegal Header' in errors[0]
    assert 'Whitespace Header' in errors[1]


def test_check_column():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)

    errors, warnings = valid.check_column(test_df['Test']['StudyName'], 0)
    assert 'Multiple studies in one' in errors[0]

    errors, warnings = valid.check_column(test_df['Test']['Non-standard1'], 0)
    assert 'Non standard NA format' in errors[0]

    errors, warnings = valid.check_column(test_df['Test']['Non-standard2'], 0)
    assert 'Non standard NA format' in errors[0]

    errors, warnings = valid.check_column(test_df['Test']['MixedTypes'], 0)
    assert 'Mixed Type' in warnings[0]

    errors, warnings = valid.check_column(test_df['Test']['EmptyCell1'], 0)
    assert 'Mixed Type' in errors[0]
    assert 'Empty cell value' in errors[1]

    errors, warnings = valid.check_column(test_df['Test']['EmptyCell2'], 0)
    assert 'Empty cell value' in errors[0]

    errors, warnings = valid.check_column(test_df['Test']['Categorical'], 0)
    assert 'Categorical Data' in warnings[0]

    errors, warnings = valid.check_column(test_df['Test']['Whitespace'], 0)
    assert 'Whitespace' in errors[0]

    errors, warnings = valid.check_column(test_df['Test']['BadDate'], 0)
    assert 'Date Error' in errors[0]

    errors, warnings = valid.check_column(test_df['Test']['GoodDate'], 0)
    assert len(errors) == 0 and len(warnings) == 0

    errors, warnings = valid.check_column(test_df['Test']['GoodString'], 0)
    assert len(errors) == 0 and len(warnings) == 0

    errors, warnings = valid.check_column(test_df['Test']['GoodNumber'], 0)
    assert len(errors) == 0 and len(warnings) == 0

    errors, warnings = valid.check_column(test_df['Test']['GoodNumberDeviation'], 0)
    assert len(errors) == 0
    assert 'StdDev' in warnings[0]


def test_check_duplicates():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = valid.check_duplicates(test_df['Test']['GoodNumber'], 0)
    assert len(errors) == 0

    errors = valid.check_duplicates(test_df['Test']['GoodString'], 0)
    assert 'Duplicate Value' in errors[0]


def test_check_lengths():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = valid.check_lengths(test_df['Test']['GoodBarcodes'], 0)
    assert len(errors) == 0

    errors = valid.check_lengths(test_df['Test']['BadBarcodes'], 0)
    assert 'different length from other' in errors[0]


def test_check_barcode_chars():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = valid.check_barcode_chars(test_df['Test']['GoodBarcodes'], 0)
    assert len(errors) == 0

    errors = valid.check_barcode_chars(test_df['Test']['BadBarcodes'], 0)
    assert 'Invalid BarcodeSequence' in errors[0]


def test_check_duplicate_cols():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    headers = list(test_df['Test'].axes[1])
    dups = valid.check_duplicate_cols(headers)
    assert len(dups) > 0


def test_check_dates():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = valid.check_dates(test_df['BadDates'])
    assert 'earlier than start date' in errors[0]

    errors = valid.check_dates(test_df['GoodDates'])
    assert len(errors) == 0


def test_check_ICD_code():
    valid_codes = ['XXX.XXXX', 'Z46.6XXX', 'Z46.81XX', 'Z46.82XX', 'Z46.89XX']
    invalid_codes = ['XXX.59XX', 'Z466XXX', 'Z46.81', 'Z46.G2XX', 'Z4X.X9XX']
    errors = valid.check_ICD_codes(valid_codes, 0)
    assert not errors
    errors = valid.check_ICD_codes(invalid_codes, 0)
    assert len(errors) == 5
    """
