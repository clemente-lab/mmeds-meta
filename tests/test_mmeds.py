from mmeds import mmeds
from time import sleep
import mmeds.config as fig
import easyimap
import email
import datetime
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


# Not in current use
def get_email():
    mmeds.send_email(fig.TEST_EMAIL, fig.TEST_USER, code=fig.TEST_CODE)
    imapper = easyimap.connect('imap.gmail.com', fig.TEST_EMAIL, fig.TEST_EMAIL_PASS)
    sleep(10)
    for mail in imapper.unseen(limit=1):
        # Assert the email was sent from the correct address
        assert mail.from_addr == fig.MMEDS_EMAIL

        # Get the timestamp from the email
        parsed = email.utils.parsedate_tz(mail.date)
        email_datetime = datetime.datetime(*parsed[:-3])
        delta = datetime.datetime.now() - email_datetime
        # parsed[-1] contains the timezone offset
        assert delta.total_seconds() + parsed[-1] < 600

    imapper.quit()


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
    assert 'names cannot be numbers' in errors[0]

    errors = mmeds.check_header('n.a.', 0)
    assert 'names cannot be NA' in errors[0]

    errors = mmeds.check_header('\\', 0)
    assert 'Illegal character(s)' in errors[0]

    errors = mmeds.check_header('name', 0)
    assert 'Potentially identifying information' in errors[0]

    errors = mmeds.check_header(' France', 0)
    assert 'Illegal character(s)' in errors[0]
    assert 'Preceding or trailing whitespace' in errors[1]


def test_check_column():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors, warnings = mmeds.check_column(test_df['Test']['StudyName'], 0)
    assert 'Multiple studies in one' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Non-standard1'], 0)
    assert 'Non standard NA format' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Non-standard2'], 0)
    assert 'Non standard NA format' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['MixedTypes'], 0)
    assert 'Mixed datatypes' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['EmptyCell1'], 0)
    assert 'Mixed datatypes' in errors[0]
    assert 'Empty cell value' in errors[1]

    errors, warnings = mmeds.check_column(test_df['Test']['EmptyCell2'], 0)
    assert 'Empty cell value' in errors[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Catagorical'], 0)
    assert 'catagorical data' in warnings[0]

    errors, warnings = mmeds.check_column(test_df['Test']['Whitespace'], 0)
    assert 'trailing whitespace' in errors[0]
    errors, warnings = mmeds.check_column(test_df['Test']['GoodString'], 0)
    assert len(errors) == 0 and len(warnings) == 0

    errors, warnings = mmeds.check_column(test_df['Test']['GoodNumber'], 0)
    assert len(errors) == 0 and len(warnings) == 0


def test_check_duplicates():
    test_df = pd.read_csv(fig.TEST_METADATA_VALID, header=[0, 1], sep='\t', na_filter=False)
    errors = mmeds.check_duplicates(test_df['Test']['GoodNumber'], 0)
    assert len(errors) == 0

    errors = mmeds.check_duplicates(test_df['Test']['GoodString'], 0)
    assert 'duplicate of row' in errors[0]


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


def test_validate_mapping_files():
    with open(fig.TEST_METADATA) as f:
        errors, warnings, study_name, subjects = mmeds.validate_mapping_file(f)
    assert len(errors) == 0
    assert len(warnings) == 0

    with open(fig.TEST_METADATA_VALID) as f:
        errors, warnings, study_name, subjects = mmeds.validate_mapping_file(f)
    assert 'Missing required fields' in errors[-1]
