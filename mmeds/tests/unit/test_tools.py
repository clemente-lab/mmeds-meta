from unittest import TestCase, skip
from shutil import rmtree
from pathlib import Path
from multiprocessing import Queue

from mmeds.tools.qiime2 import Qiime2
from mmeds.tools.sparcc import SparCC
from mmeds.tools.lefse import Lefse
from mmeds.tools.picrust2 import PiCRUSt2
from mmeds.tools.cutie import CUTIE
from mmeds.util import load_config
from mmeds.logging import Logger
import mmeds.config as fig


class ToolsTests(TestCase):
    """ Tests of individual tools """

    @classmethod
    def setUpClass(self):
        self.config = load_config(None, fig.TEST_METADATA_SHORT, 'qiime2')
        self.q = Queue()
        self.testing = True

    def run_analysis(self, code, tool_type, analysis_type, TOOL, config, runs={}):
        tool = TOOL(self.q, fig.TEST_USER, 'random_code', code, tool_type, analysis_type, config,
                    self.testing, runs, True, analysis=True)
        Logger.debug('Starting {}, id is {}'.format(tool.name, id(tool)))
        tool.run()
        self.assertEqual(tool.doc.analysis_type, analysis_type)
        rmtree(tool.path)

    def test_a_qiime2_setup_analysis(self):
        for tool_type, analysis_type in [('qiime2', 'dada2'), ('qiime2', 'deblur')]:
            for code in [fig.TEST_CODE_SHORT, fig.TEST_CODE_PAIRED, fig.TEST_CODE_DEMUX]:
                self.run_analysis(code, tool_type, analysis_type, Qiime2, self.config)

    def test_b_qiime2_child_setup_analysis(self):
        config = load_config(Path(fig.TEST_CONFIG), fig.TEST_METADATA, 'qiime2')
        q2 = Qiime2(self.q, fig.TEST_USER, 'random_new_code', fig.TEST_CODE_SHORT, 'qiime2',
                    'dada2', config, self.testing, {}, True, analysis=False)
        q2.initial_setup()
        q2.setup_analysis()
        q2.create_children()
        for child in q2.children:
            self.assertEqual(child.doc.data_type, 'single_end')

        rmtree(q2.path)

    def test_c_sparcc_setup_analysis(self):
        config = load_config(fig.DEFAULT_CONFIG_SPARCC, fig.TEST_METADATA_SHORT, 'sparcc')
        self.run_analysis(fig.TEST_CODE_PAIRED, 'sparcc', 'default', SparCC, config)

    def test_d_lefse_setup_analysis(self):
        config = load_config(fig.DEFAULT_CONFIG_LEFSE, fig.TEST_METADATA_SHORT, 'lefse')
        self.run_analysis(fig.TEST_CODE_SHORT, 'lefse', 'default', Lefse, config)

    def test_e_picrust2_setup_analysis(self):
        config = load_config(fig.DEFAULT_CONFIG_PICRUST2, fig.TEST_METADATA_SHORT, 'picrust2')
        self.run_analysis(fig.TEST_CODE_DEMUX, 'picrust2', 'default', PiCRUSt2, config)

    def test_f_cutie_setup_analysis(self):
        config = load_config(fig.DEFAULT_CONFIG_CUTIE, fig.TEST_METADATA_SHORT, 'cutie')
        self.run_analysis(fig.TEST_CODE_PAIRED, 'cutie', 'default', CUTIE, config)

    @skip
    def test_lefse_sub_analysis(self):
        # TODO: Implement conversion from otu table to lefse table so Lefse can be run as a sub analysis
        return
        config = load_config(Path(fig.TEST_CONFIG), fig.TEST_METADATA, 'lefse')
        q2 = Qiime2(self.q, fig.TEST_USER, 'SomeCodeHere', fig.TEST_CODE_SHORT, 'qiime2', 'dada2',
                    config, self.testing, True, analysis=False)
        q2.initial_setup()
        q2.setup_analysis()
        q2.create_analysis(Lefse)
        rmtree(q2.path)

    @skip
    def test_sparcc_sub_analysis(self):
        config = load_config(Path(fig.TEST_CONFIG), fig.TEST_METADATA, 'sparcc')
        q2 = Qiime2(self.q, fig.TEST_USER, 'random_new_code', fig.TEST_CODE_SHORT, 'qiime2',
                    'dada2', config, self.testing, True, analysis=False)
        q2.initial_setup()
        q2.setup_analysis()
        q2.queue_analysis('sparcc')
        item = self.q.get()
        while item[0] == 'email':
            item = self.q.get()
        process = item
        self.assertSequenceEqual(process,
                                 ('analysis', q2.owner, q2.doc.access_code, 'sparcc',
                                  q2.config['type'], q2.doc.config, True, q2.kill_stage))
        rmtree(q2.path)
