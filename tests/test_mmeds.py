from mmeds import mmeds
from time import sleep
import mmeds.config as fig
import easyimap
import email
import datetime
import hashlib as hl
import os
import difflib


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
