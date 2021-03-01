import mmeds.formatter as fmt
import mmeds.config as fig

from unittest import TestCase
from mmeds.database.database import Database


class FormatterTests(TestCase):
    """ Iterate through all the errors in MMEDs, creating an instance of each to ensure they work """
    def test_build_specimen_table(self):
        return
        with Database(testing=True) as db:
            doc = db.get_docs(access_code=fig.TEST_CODE_SHORT).first()
            data, header = db.execute(fmt.SELECT_SPECIMEN_QUERY.format(doc.study_name))
        fmt.build_html_table(data, header)

    def test_build_clickable_table(self):
        with Database(testing=True) as db:
            doc = db.get_docs(access_code=fig.TEST_CODE_SHORT).first()
            data, header = db.execute(fmt.SELECT_SPECIMEN_QUERY.format(StudyName='Short_Study'))
        breakpoint()
        fmt.build_clickable_table(header, data, 'query_generate_aliquot_id_page',
                                  {'AccessCode': doc.access_code},
                                  {'SpecimenID': 0}
                                  )
