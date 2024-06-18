from mmeds.config import DATABASE_DIR, CUTIE_CONFIG_TEMPLATE
from mmeds.util import get_file_index_entry_location
from mmeds.tools.tool import Tool


class CUTIE(Tool):
    """ A class for CUTIE analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, workflow_type, analysis_type, config, testing, runs,
                 run_on_node, analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, workflow_type, analysis_type, config, testing, runs,
                         run_on_node=run_on_node, analysis=analysis, restart_stage=restart_stage, kill_stage=kill_stage,
                         child=child)
        if testing:
            load = 'conda activate CUTIE;'
        else:
            load = 'export LC_ALL=en_US.UTF-8;\nml anaconda3;'
        self.jobtext.append(load)
        self.module = load

        self.stat = self.config['statistic']
        self.table = self.config['feature_table']

    def create_input_config_file(self):
        """ Create input config file defining CUTIE run """
        self.add_path('input_config', '.ini')
        self.add_path('CUTIE_out')

        with open(CUTIE_CONFIG_TEMPLATE) as f:
            template = f.read()

        with open(self.get_file('input_config', True), "w") as f:
            f.write(template.format(
                f1_path=self.get_file('feature_table', True),
                f2_path=self.get_file('continuous_mapping', True),
                out_dir=self.get_file('CUTIE_out', True),
                statistic=self.stat
            ))

    def run_CUTIE(self):
        """ Run the CUTIE analysis """
        cmd = 'calculate_cutie.py -i {}'.format(self.get_file('input_config'))
        self.jobtext.append(cmd)

    def setup_analysis(self, summary=False):
        self.set_stage(0)
        self.extract_qiime2_feature_table(self.table, deactivate_prev=False)
        self.generate_continuous_mapping_file()
        self.set_stage(1)
        self.create_input_config_file()
        self.source_activate('cutie')
        self.run_CUTIE()
        self.write_file_locations()
        super().setup_analysis(summary=summary)
