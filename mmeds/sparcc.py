
from mmeds.config import DATABASE_DIR
from mmeds.tool import Tool


class SparCC(Tool):
    """ A class for SparCC analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing,
                 analysis=True, restart_stage=0, kill_stage=0):
        super().__init__(owner, access_code, atype, config, testing,
                         analysis=analysis, restart_stage=restart_stage)
        load = 'module use {}/.modules/modulefiles; module load sparcc;'.format(DATABASE_DIR.parent)
        self.jobtext.append(load)
        self.module = load
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))
        parts = self.doc.doc_type.split('-')
        self.stat = parts[-1]

    def sparcc(self):
        """ Quantify the correlation between all OTUs """
        self.add_path('correlation', '.out')
        cmd = 'SparCC.py {} -i {} --cor_file={}'.format(self.get_file('otu_table'),
                                                        self.doc.config['iterations'],
                                                        self.get_file('correlation'))
        if self.stat is not None:
            cmd += ' -a {}'.format(self.stat)
        self.jobtext.append(cmd)

    def make_bootstraps(self):
        """ Calculate the psuedo p-values """
        iterations = 5
        cmd = 'MakeBootstraps.py {data} -n {iterations} -t {permutations} -p {pvals}'
        pvals = 'somewhereovertherainbow'
        permutations = 5
        self.jobtext.append(cmd.format(data=self.get_file('correlation_matrix'),
                                       iterations=iterations,
                                       permutations=permutations,
                                       pvals=pvals))

    def pseudo_pvals(self):
        cmd = 'PseudoPvals.py {data} {cor} {iter} -o {output} -t {type}'
        print(cmd)

    def setup_analysis(self):
        self.sparcc()
        self.write_file_locations()
        super().setup_analysis(summary=False)
