from mmeds.config import DATABASE_DIR
from mmeds.tools.tool import Tool


class PiCRUSt1(Tool):
    """ A class for SparCC analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing,
                 analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing,
                         analysis=analysis, restart_stage=restart_stage, kill_stage=kill_stage, child=child)
        load = 'module use {}/.modules/modulefiles; module load picrust;'.format(DATABASE_DIR.parent)
        self.jobtext.append(load)
        self.module = load

    def place_seqs(self):
        """ Setup the place_seqs script """
        iterations = 4
        self.jobtext.append('for i in $(seq 0 {}); do\n'.format(iterations));
        self.jobtext.append('    mkdir {}/intermediate${{i}};\n'.format(self.run_dir))
        self.jobtext.append('    place_seqs.py -s {}/split_fna_${{i}}.fna'.format(self.run_dir))

