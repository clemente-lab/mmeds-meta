from mmeds.config import DATABASE_DIR, CUTIE_CONFIG_TEMPLATE
from mmeds.util import get_file_index_entry_location
from mmeds.tools.tool import Tool


class CUTIE(Tool):
    """ A class for CUTIE analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, runs,
                 run_on_node, analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, runs,
                         run_on_node=run_on_node, analysis=analysis, restart_stage=restart_stage, kill_stage=kill_stage,
                         child=child)
        if testing:
            load = 'module use {}/.modules/modulefiles; module load CUTIE;'.format(DATABASE_DIR.parent)
        else:
            load = 'ml anaconda3;\nsource activate CUTIE;'
        self.jobtext.append(load)
        self.module = load

        self.stat = self.config['statistic']

    def create_input_config_file(self):
        """ Create input config file defining CUTIE run """
        self.add_path('input_config', '.ini')
        self.add_path('CUTIE_out')

        with open(self.get_file('input_config'), "w") as f:
            f.write(CUTIE_CONFIG_TEMPLATE.format(
                f1_path=,
                f1_sep='/t',
                f1_tidy=,
                f1_skip=,
                f1_col_start=,
                f1_col_end=,
                f2_path=,
                f2_sep='/t',
                f2_tidy=,
                f2_skip=,
                f2_col_start=,
                f2_col_end=,
                paired=,
                out_dir=self.get_file('CUTIE_out'),
                statistic=self.stat
            ))

    def run_CUTIE(self):
        """ Run the CUTIE analysis """
        cmd = 'calculate_cutie.py -i {}'.format(self.get_file('input_config'))
        self.jobtext.append(cmd)

    def setup_analysis(self, summary=False):
        self.set_stage(0)
        self.create_input_config_file()
        self.set_stage(1)
        self.run_CUTIE()
        self.write_file_locations()
        super().setup_analysis(summary=summary)
