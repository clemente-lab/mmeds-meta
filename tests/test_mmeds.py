from mmeds import mmeds
from time import sleep
import mmeds.config as fig
import easyimap
import email
import datetime


def test_is_numeric():
    assert mmeds.is_numeric('45') is True
    assert mmeds.is_numeric('4.5') is True
    assert mmeds.is_numeric('r.5') is False
    assert mmeds.is_numeric('5.4.5') is False
    assert mmeds.is_numeric('r5') is False
    assert mmeds.is_numeric('5r') is False


def test_get_email():
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
