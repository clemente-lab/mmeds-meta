from mmeds.database.database import upload_otu
from mmeds.authentication import add_user, remove_user
import mmeds.config as fig
from unittest import TestCase

testing = True


class UploaderTests(TestCase):

    @classmethod
    def setUpClass(self):
        self.user = 'Upload_User'
        self.test_code = 'ThisIsATest'
        add_user(self.user, 'uploads', 'na@na.com', testing=testing)

        self.test_otu = (fig.TEST_SUBJECT_SHORT,
                         'human',
                         fig.TEST_SPECIMEN_SHORT,
                         fig.TEST_DIR,
                         self.user,
                         'Test_Uploader',
                         fig.TEST_OTU,
                         self.test_code)

    @classmethod
    def tearDownClass(self):
        remove_user(self.user, testing=testing)

    def test_uploader(self):
        assert 0 == upload_otu(self.test_otu)
