
from mmeds.config import DATABASE_DIR
from mmeds.tool import Tool


class SparCC(Tool):
    """ A class for SparCC analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing,
                 analysis=True, restart_stage=0):
        super().__init__(owner, access_code, atype, config, testing,
                         analysis=analysis, restart_stage=restart_stage)
        load = 'module use {}/.modules/modulefiles; module load sparcc;'.format(DATABASE_DIR.parent)
        self.jobtext.append(load)
        self.module = load
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))

    def sparcc(self):
        stat = 'pearson'
        iterations = 5
        name = 'correlation_{}_{}'.format(iterations, stat)
        self.add_path(name, '.out')
        cmd = 'SparCC.py {} -i {} --cor_file={}'.format(self.get_file('correlation_matrix'),
                                                        iterations,
                                                        self.get_file(name)),
        if stat is not None:
            cmd += ' -a {}'.format(stat)
        self.jobtext.append(cmd)
