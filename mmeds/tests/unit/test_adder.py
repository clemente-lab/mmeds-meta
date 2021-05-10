from unittest import TestCase

import mmeds.config as fig
from mmeds.database.metadata_adder import MetaDataAdder
from mmeds.database.database import Database

testing = True


class MetaDataAdderTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        """ Load data that is to be used by multiple test cases """

        with Database(testing=testing) as db:
            self.doc = db.get_docs(study_name='Test_Single_Short').first()
        self.access_code = self.doc.access_code

    def test_a_add_aliquot(self):

        # Test adding an Aliquot with NAs
        mda = MetaDataAdder(fig.TEST_USER, self.access_code, fig.TEST_NA_ALIQUOT, 'aliquot', False, testing)
        assert mda.run() == 0

        # Test generating an aliquot ID
        mda = MetaDataAdder(fig.TEST_USER, self.access_code, fig.TEST_ALIQUOT_UPLOAD, 'aliquot', True, testing)
        assert mda.run() == 0

        # Test adding an Aliquot ID
        mda = MetaDataAdder(fig.TEST_USER, self.access_code, fig.TEST_ADD_ALIQUOT, 'aliquot', False, testing)
        assert mda.run() == 0

    def test_b_generate_sample(self):
        mda = MetaDataAdder(fig.TEST_USER, self.access_code, fig.TEST_SAMPLE_UPLOAD, 'sample', True, testing)
        assert mda.run() == 0

        # Test adding a Sample ID
        mda = MetaDataAdder(fig.TEST_USER, self.access_code, fig.TEST_ADD_SAMPLE, 'sample', True, testing)
        assert mda.run() == 0

    def test_c_add_subject(self):
        mda = MetaDataAdder(fig.TEST_USER, self.access_code, fig.TEST_ADD_SUBJECT, 'subject', False, testing)
        assert mda.run() == 0
