from unittest import TestCase
from pathlib import Path
import mmeds.config as fig
from time import sleep

from mmeds.util import run_analysis, load_config, upload_sequencing_run_local
from mmeds.summary import summarize_qiime
from mmeds.spawn import Watcher
from mmeds.logging import Logger
from mmeds.tools.analysis import Analysis
from mmeds.database.database import Database
import mmeds.error as err


class AnalysisTests(TestCase):
    """ Test running analyses """
    @classmethod
    def setUpClass(cls):
        """ Set up tests """
        # path to an example study, created from a MMEDs upload of existing test files
        # definied in config.py
        cls.test_study = fig.TEST_STUDY
        cls.watcher = Watcher()
        cls.watcher.connect()
        cls.queue = cls.watcher.get_queue()
        cls.config = load_config(fig.DEFAULT_CONFIG, fig.TEST_MIXED_METADATA, 'standard_pipeline')
        with Database(owner=fig.TEST_USER_0, testing=True) as db:
            cls.analysis_code = db.create_access_code()
            cls.runs = db.get_sequencing_run_locations(fig.TEST_MIXED_METADATA, fig.TEST_USER_0)
        cls.analysis = Analysis(cls.queue, fig.TEST_USER_0, cls.analysis_code, fig.TEST_CODE_MIXED,
                                'standard_pipeline', 'default', 'test_init', cls.config, True, cls.runs, False, threads=2)

    def test_a_upload_sequencing_run(self):
        """ Upload sequencing run for analysis """
        datafiles = {"forward": fig.TEST_READS,
                     "reverse": fig.TEST_REV_READS,
                     "barcodes": fig.TEST_BARCODES}
        result = upload_sequencing_run_local(self.queue, fig.TEST_SEQUENCING_NAME, fig.TEST_USER_0, datafiles, 'paired_end', 'single_barcodes')
        sleep(5)
        self.assertEquals(result, 0)


    def test_b_standard_pipeline(self):
        """ Test running a standard analysis """
        # run_analysis() executes analyses synchronously rather than submitting as a job
        run_analysis(self.test_study, 'standard_pipeline', testing=True)
        """
        summarize_qiime(f'{self.test_study}/Qiime2_0', 'standard_pipeline', testing=True)

         check for summary pdf, also gets uploaded as an artifact in github actions for inspection
        pdf_output = Path(f'{self.test_study}/Qiime2_0/summary/mkstapylton@gmail.com-mattS-qiime2.ipynb')
        self.assertTrue(pdf_output.exists())
        """

    def test_c_analysis_class(self):
        """ Test the analysis object """
        self.analysis.run()

        info = self.analysis.get_info()
        self.assertEquals(info['owner'], fig.TEST_USER_0)
        self.assertEquals(info['analysis_code'], self.analysis_code)

    def test_d_analysis_utils(self):
        """ Test that adding files to the tool object works properly """
        Logger.info(str(self.analysis))
        assert 'testfile' not in self.analysis.doc.files.keys()
        self.analysis.add_path('testfile', '.txt')
        assert 'testfile' in self.analysis.doc.files.keys()

    def test_e_get_job_params(self):
        params = self.analysis.get_job_params()
        assert params['nodes'] == 2

    def test_f_get_files(self):
        """ Test getting file locations """
        return True

    def test_g_missing_file(self):
        """ Test that an appropriate error will be raised if a file doesn't exist on disk """
        files = self.analysis.doc.files
        # Add a nonexistent file
        files['fakefile'] = '/fake/dir'
        self.analysis.update_doc(files=files)
        with self.assertRaises(err.MissingFileError):
            self.analysis.get_file('fakefile', check=True)
        del files['fakefile']
        self.analysis.update_doc(files=files)

    def test_h_update_doc(self):
        self.assertEqual(self.analysis.doc.study_name, 'TEST_MIXED_17')
        self.analysis.update_doc(study_name='Test_Update')
        self.assertEqual(self.analysis.doc.study_name, 'Test_Update')

