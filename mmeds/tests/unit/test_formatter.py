import mmeds.formatter as fmt
import mmeds.config as fig

from unittest import TestCase
from mmeds.database.database import Database


class FormatterTests(TestCase):
    """ Iterate through all the errors in MMEDs, creating an instance of each to ensure they work """
    def test_build_specimen_table(self):
        with Database(testing=True) as db:
            doc = db.get_docs(access_code=fig.TEST_CODE_SHORT).first()
            data, header = db.execute(fmt.SELECT_SPECIMEN_QUERY.format(doc.study_name))
        breakpoint()
        fmt.build_html_table(data, header)
