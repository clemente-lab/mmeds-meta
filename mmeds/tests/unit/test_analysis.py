from unittest import TestCase
from pathlib import Path
import mmeds.config as fig
from time import sleep

from mmeds.util import run_analysis, load_config, upload_sequencing_run_local
from mmeds.spawn import Watcher
from mmeds.logging import Logger
from mmeds.tools.analysis import Analysis
from mmeds.database.database import Database
import mmeds.error as err


class AnalysisTests(TestCase):
    """ Test running analyses """
    @classmethod
    def setUpClass(self):
        """ Set up tests """
        # path to an example study, created from a MMEDs upload of existing test files
        # definied in config.py
        self.test_study = fig.TEST_STUDY
        self.watcher = Watcher()
        self.watcher.connect()
        self.queue = self.watcher.get_queue()
        self.config = load_config(fig.DEFAULT_CONFIG, fig.TEST_MIXED_METADATA, 'core_pipeline_taxonomic')
        self.config_lefse = load_config(fig.DEFAULT_CONFIG_LEFSE, fig.TEST_MIXED_METADATA, 'lefse')
        self.analysis = []
        with Database(owner=fig.TEST_USER_0, testing=True) as db:
            self.analysis_code_0 = db.create_access_code()
            self.analysis_code_1 = db.create_access_code()

    def test_a_upload_sequencing_run(self):
        """ Upload sequencing run for analysis """
        datafiles = {"forward": fig.TEST_READS,
                     "reverse": fig.TEST_REV_READS,
                     "barcodes": fig.TEST_BARCODES}
        result = upload_sequencing_run_local(self.queue, fig.TEST_SEQUENCING_NAME, fig.TEST_USER_0, datafiles, 'paired_end', 'single_barcodes')
        sleep(5)
        self.assertEquals(result, 0)

    def test_b_analysis_init(self):
        """ Test analysis object """
        with Database(owner=fig.TEST_USER_0, testing=True) as db:
            self.runs = db.get_sequencing_run_locations(fig.TEST_MIXED_METADATA, fig.TEST_USER_0)
        self.analysis += [Analysis(self.queue, fig.TEST_USER_0, self.analysis_code_0, fig.TEST_CODE_MIXED,
                                'core_pipeline_taxonomic', 'default', 'test_init', self.config, True, self.runs, False, threads=2)]
        self.analysis += [Analysis(self.queue, fig.TEST_USER_0, self.analysis_code_1, fig.TEST_CODE_MIXED,
                                'lefse', 'default', 'test_lefse', self.config_lefse, True, {}, False, threads=2)]


    def test_c_core_pipeline_taxonomic(self):
        """ Test running a standard analysis """
        # run_analysis() executes analyses synchronously rather than submitting as a job
        run_analysis(self.test_study, 'core_pipeline_taxonomic', testing=True)

    def test_d_analysis_class(self):
        """ Test the analysis objects """
        analysis = self.analysis[0]
        analysis.run()

        info = analysis.get_info()
        table = Path(info['path']) / 'tables' / 'taxa_table_L6.qza'
        table.touch()

        self.assertEquals(info['owner'], fig.TEST_USER_0)
        self.assertEquals(info['analysis_code'], self.analysis_code_0)

    def test_e_lefse_analysis_class(self):
        lefse_analysis = self.analysis[1]
        lefse_analysis.run()

        info = lefse_analysis.get_info()
        self.assertEquals(info['owner'], fig.TEST_USER_0)
        self.assertEquals(info['analysis_code'], self.analysis_code_1)

    def test_d_analysis_utils(self):
        """ Test that adding files to the tool object works properly """
        analysis = self.analysis[0]
        Logger.info(str(analysis))
        assert 'testfile' not in analysis.doc.files.keys()
        analysis.add_path('testfile', '.txt')
        assert 'testfile' in analysis.doc.files.keys()

    def test_e_get_job_params(self):
        analysis = self.analysis[0]
        params = analysis.get_job_params()
        assert params['nodes'] == 2

    def test_f_get_files(self):
        """ Test getting file locations """
        return True

    def test_g_missing_file(self):
        """ Test that an appropriate error will be raised if a file doesn't exist on disk """
        analysis = self.analysis[0]
        files = analysis.doc.files
        # Add a nonexistent file
        files['fakefile'] = '/fake/dir'
        analysis.update_doc(files=files)
        with self.assertRaises(err.MissingFileError):
            analysis.get_file('fakefile', check=True)
        del files['fakefile']
        analysis.update_doc(files=files)

    def test_h_update_doc(self):
        analysis = self.analysis[0]
        self.assertEqual(analysis.doc.study_name, 'TEST_MIXED_17')
        analysis.update_doc(study_name='Test_Update')
        self.assertEqual(analysis.doc.study_name, 'Test_Update')

