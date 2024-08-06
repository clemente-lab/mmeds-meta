from unittest import TestCase
from pathlib import Path
import mmeds.config as fig
from time import sleep

from mmeds.util import run_analysis, load_config, upload_sequencing_run_local
from mmeds.summary import summarize_qiime
from mmeds.spawn import Watcher
from mmeds.tools.analysis import Analysis
from mmeds.database.database import Database


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
        with Database(owner=fig.TEST_USER_0, testing=True) as db:
            cls.analysis_code = db.create_access_code()
        cls.config = load_config(fig.DEFAULT_CONFIG, fig.TEST_MIXED_METADATA, 'standard_pipeline')

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
        with Database(owner=fig.TEST_USER_0, testing=True) as db:
            self.runs = db.get_sequencing_run_locations(fig.TEST_MIXED_METADATA, fig.TEST_USER_0)
        analysis = Analysis(self.queue, fig.TEST_USER_0, self.analysis_code, fig.TEST_CODE_MIXED,
                            'standard_pipeline', 'default', 'test_init', self.config, True, self.runs, False)
        analysis.run()

        info = analysis.get_info()
        self.assertEquals(info['owner'], fig.TEST_USER_0)
        self.assertEquals(info['analysis_code'], self.analysis_code)
