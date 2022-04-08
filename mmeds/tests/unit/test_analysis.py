from unittest import TestCase
import mmeds.config as fig

from mmeds.util import run_analysis
from mmeds.summary import summarize_qiime


class AnalysisTests(TestCase):
    """ Test running analyses """
    @classmethod
    def setUpClass(cls):
        """ Set up tests """
        # path to an example study, created from a MMEDs upload of existing test files
        # definied in config.py
        cls.test_study = fig.TEST_STUDY

    def test_qiime2(self):
        """ Test running a qiime2 analysis """
        run_analysis(self.test_study, 'qiime2', testing=True)
        summarize_qiime(f'{self.test_study}/Qiime2_0', 'qiime2', testing=True)
