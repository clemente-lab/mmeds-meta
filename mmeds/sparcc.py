
from mmeds.config import DATABASE_DIR
from mmeds.tool import Tool


class SparCC(Tool):
    """ A class for SparCC analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing,
                 analysis=True, restart_stage=0, kill_stage=0, child=False):
        super().__init__(owner, access_code, atype, config, testing,
                         analysis=analysis, restart_stage=restart_stage, child=child)
        load = 'module use {}/.modules/modulefiles; module load sparcc;'.format(DATABASE_DIR.parent)
        self.jobtext.append(load)
        self.module = load
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))

    def sparcc(self, data_permutation=None):
        """ Quantify the correlation between all OTUs """

        if data_permutation is None:
            data_file = self.get_file('otu_table')
            self.add_path('correlation', '.out')
        else:
            data_file = data_permutation
        cmd = 'SparCC.py {data} -i {iterations} --cor_file={output}'

        if self.stat is not None:
            cmd += ' -a {stat}'

        # If running on permutations have commands execute in parallel
        if data_permutation is None:
            cmd += ';'
        else:
            cmd += '&'
        self.jobtext.append(cmd.format(data=data_file,
                                       iterations=self.doc.config['iterations'],
                                       output=self.get_file('correlation'),
                                       stat=self.stat))

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

    def setup_analysis(self):
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
        super().setup_analysis(summary=False)
