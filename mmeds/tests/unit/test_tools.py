from unittest import TestCase
from shutil import rmtree
from pathlib import Path
from time import sleep

from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.sparcc import SparCC
from mmeds.lefse import Lefse
from mmeds.util import load_config
import mmeds.config as fig


class ToolsTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        self.config = load_config(None, fig.TEST_METADATA_SHORT)

    def run_qiime(self, code, tool_type, analysis_type, data_type, Qiime):
        qiime = Qiime(fig.TEST_USER, code, tool_type, analysis_type, self.config, testing=self.testing, analysis=False)
        qiime.start()
        while qiime.is_alive():
            sleep(2)
        self.assertEqual(qiime.doc.reads_type, data_type)
        rmtree(qiime.path)

    def test_sparcc_setup_analysis(self):
        self.run_qiime(fig.TEST_CODE_OTU, 'sparcc', 'default', 'otu_table', SparCC)

    
    def test_lefse_setup_analysis(self):
        self.run_qiime(fig.TEST_CODE_LEFSE, 'lefse', 'default', 'lefse_table', Lefse)

    def test_qiime1_setup_analysis(self):
        return  # TODO remove
        for tool_type, analysis_type in [('qiime1', 'open'), ('qiime1', 'closed')]:
            for data_type, code in [('single_end', fig.TEST_CODE_SHORT),
                                    ('paired_end', fig.TEST_CODE_PAIRED),
                                    ('single_end_demuxed', fig.TEST_CODE_DEMUX)]:
                self.run_qiime(code, tool_type, analysis_type, data_type, Qiime1)

    def test_qiime2_setup_analysis(self):
        return  # TODO remove
        for tool_type, analysis_type in [('qiime2', 'dada2'), ('qiime2', 'deblur')]:
            for data_type, code in [('single_end', fig.TEST_CODE_SHORT),
                                    ('paired_end', fig.TEST_CODE_PAIRED),
                                    ('single_end_demuxed', fig.TEST_CODE_DEMUX)]:
                self.run_qiime(code, tool_type, analysis_type, data_type, Qiime2)

    def test_qiime2_child_setup_analysis(self):
        return  # TODO remove
        config = load_config(Path(fig.TEST_CONFIG).read_text(), fig.TEST_METADATA, testing=self.testing)
        q2 = Qiime2(fig.TEST_USER, fig.TEST_CODE_SHORT, 'qiime2', 'dada2', config, testing=self.testing, analysis=False)
        q2.setup_analysis()
        q2.create_children()
        for child in q2.children:
            self.assertEqual(child.doc.data_type, 'single_end')

        rmtree(q2.path)
    
    def test_lefse_sub_analysis(self):
        config = load_config(Path(fig.TEST_CONFIG).read_text(), fig.TEST_METADATA)
        q2 = Qiime2(fig.TEST_USER, fig.TEST_CODE_SHORT, 'qiime2', 'dada2', config, testing = self.testing, analysis=False)
        q2.setup_analysis()
        q2.create_analysis(Lefse)
        rmtree(q2.path)
    
    def test_sparcc_sub_analysis(self):
        config = load_config(Path(fig.TEST_CONFIG).read_text(), fig.TEST_METADATA)
        q2 = Qiime2(fig.TEST_USER, fig.TEST_CODE_SHORT, 'qiime2', 'dada2', config, testing=self.testing, analysis=False)
        q2.setup_analysis()
        q2.create_analysis(SparCC)
        rmtree(q2.path)

