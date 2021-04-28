from mmeds.database.database import upload_otu, upload_metadata
from mmeds.authentication import add_user, remove_user
import mmeds.config as fig
from unittest import TestCase, skip

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

        self.test_fastq = ('/home/david/Work/stash/inactivate/Subject_file.tsv',
                           'human',
                           '/home/david/Work/stash/inactivate/Specimen_file.tsv',
                           fig.TEST_DIR,
                           fig.TEST_USER,
                           'Viral_Inactivation_in_Microbiome_Samples',
                           'single_end',
                           'single_barcodes',
                           fig.TEST_READS,
                           None,
                           fig.TEST_BARCODES,
                           fig.TEST_CODE_SHORT,
                           testing)

    @classmethod
    def tearDownClass(self):
        remove_user(self.user, testing=testing)

    def test_fastq_upload(self):
        assert 0 == upload_metadata(self.test_fastq)

    @skip
    def test_uploader(self):
        assert 0 == upload_otu(self.test_otu)
