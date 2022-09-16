from mmeds.config import DATABASE_DIR
from mmeds.util import get_file_index_entry_location
from mmeds.tools.tool import Tool


class PiCRUSt2(Tool):
    """ A class for picrust2 analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, runs,
                 run_on_node, analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, runs,
                         run_on_node=run_on_node, analysis=analysis, restart_stage=restart_stage, kill_stage=kill_stage,
                         child=child)
        if testing:
            load = 'conda activate picrust2;'
        else:
            load = 'ml anaconda3;'
        self.jobtext.append(load)
        self.module = load

        self.stratified = self.config['stratified']
        self.per_seq_contrib = self.config['per_sequence_contrib']

    def extract_picrust_input(self):
        """ Extract the filtered table and representative sequences data from Qiime2 """
        self.extract_qiime2_feature_table()
        self.extract_qiime2_rep_seqs()

    def picrust_pipeline(self):
        """ Run the picrust2 analysis """
        self.add_path('picrust2_out')
        cmd = 'picrust2_pipeline.py -s {} -i {} -o {}'.format(
            self.get_file('rep_seqs'),
            self.get_file('biom_feature'),
            self.get_file('picrust2_out'))
        if self.stratified:
            cmd += ' --stratified'
        if self.per_seq_contrib:
            cmd += ' --per_sequence_contrib'
        self.jobtext.append(cmd)

    def setup_analysis(self, summary=False):
        self.set_stage(0)
        self.extract_picrust_input()
        self.set_stage(1)
        self.source_activate('picrust2')
        self.picrust_pipeline()
        self.set_stage(2)
        # TODO: What happens downstream?
        self.write_file_locations()
        super().setup_analysis(summary=summary)
