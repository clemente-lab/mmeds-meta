from mmeds.config import DATABASE_DIR
from mmeds.tools.tool import Tool


class SparCC(Tool):
    """ A class for SparCC analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, run_on_node,
                 analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing,
                         run_on_node=run_on_node, analysis=analysis, restart_stage=restart_stage,
                         kill_stage=kill_stage, child=child)
        if testing:
            load = 'module use {}/.modules/modulefiles; module load sparcc;'.format(DATABASE_DIR.parent)
        else:
            load = 'module load sparcc;'
        self.jobtext.append(load)
        self.module = load

    def sparcc(self, data_permutation=None):
        """ Quantify the correlation between all OTUs """

        if data_permutation is None:
            data_file = self.get_file('otu_table')
            self.add_path('correlation', '.out')
        else:
            data_file = data_permutation
        cmd = 'SparCC.py {data} -i {iterations} --cor_file={output}'

        if self.doc.config.get('stat') is not None:
            cmd += ' -a {stat}'

        # If running on permutations have commands execute in parallel
        if data_permutation is None:
            cmd += ';'
        else:
            cmd += '&'
        self.jobtext.append(cmd.format(data=data_file,
                                       iterations=self.doc.config['iterations'],
                                       output=self.get_file('correlation'),
                                       stat=self.doc.config.get('stat')))

    def make_bootstraps(self):
        """ Create the shuffled datasets """
        cmd = 'MakeBootstraps.py {data} -n {permutations} -t permutation_#.txt -p {pvals}/'
        self.add_path('pvals')
        if not self.get_file('pvals', True).is_dir():
            self.get_file('pvals', True).mkdir()
        self.jobtext.append(cmd.format(data=self.get_file('correlation'),
                                       permutations=self.doc.config['permutations'],
                                       pvals=self.get_file('pvals')))

    def pseudo_pvals(self, sides='two'):
        """ Calculate the psuedo p-values """
        self.add_path('PseudoPval', '.txt')
        cmd = 'PseudoPvals.py {data} {perm} {iterations} -o {output} -t {sides}_sided'
        self.jobtext.append(cmd.format(data=self.get_file('correlation'),
                                       perm=self.get_file('pvals') / 'permutation_#.txt',
                                       iterations=self.doc.config['iterations'],
                                       output=self.get_file('PseudoPval'),
                                       sides=sides))

    def setup_analysis(self, summary=False):
        self.set_stage(0)
        self.sparcc()
        self.set_stage(1)
        self.make_bootstraps()
        self.set_stage(2)
        files = [self.get_file('pvals') / 'perm_cor_{}.txt'.format(i)
                 for i in range(int(self.doc.config['permutations']))]
        for pfile in files:
            self.sparcc(pfile)
        self.set_stage(3)
        self.pseudo_pvals()
        self.write_file_locations()
        super().setup_analysis(summary=summary)
