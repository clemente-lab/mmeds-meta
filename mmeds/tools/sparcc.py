from mmeds.config import DATABASE_DIR
from mmeds.tools.tool import Tool


class SparCC(Tool):
    """ A class for SparCC analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, runs,
                 run_on_node, analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, runs,
                         run_on_node=run_on_node, analysis=analysis, restart_stage=restart_stage,
                         kill_stage=kill_stage, child=child)
        if testing:
            load = 'module use {}/.modules/modulefiles; module load sparcc;'.format(DATABASE_DIR.parent)
        else:
            load = 'module load sparcc/2016-10-17;'
        self.jobtext.append(load)
        self.module = load

        self.stat = self.config['statistic']
        self.iterations = self.config['iterations']
        self.permutations = self.config['permutations']

    def create_sub_folders(self):
        """ Create the necessary sub-folders for SparCC analysis """
        self.add_path('pvals')
        if not self.get_file('pvals', True).is_dir():
            self.get_file('pvals', True).mkdir()

        self.add_path('pcorrelations')
        if not self.get_file('pcorrelations', True).is_dir():
            self.get_file('pcorrelations', True).mkdir()

        self.add_path('pcovariances')
        if not self.get_file('pcovariances', True).is_dir():
            self.get_file('pcovariances', True).mkdir()

    def sparcc(self, data_permutation=None):
        """ Quantify the correlation between all OTUs """

        if data_permutation is None:
            data_file = self.get_file('feature_table')
            cor = 'correlation'
            cov = 'covariance'
            cor_dir = self.path
            cov_dir = self.path
        else:
            data_file = data_permutation
            permutation_num = data_permutation.stem.split('_')[-1]
            cor = f'correlation_perm_{permutation_num}'
            cov = f'covariance_perm_{permutation_num}'
            cor_dir = self.get_file('pcorrelations', True)
            cov_dir = self.get_file('pcovariances', True)

        self.add_path(cor_dir / cor, '.txt', key=cor)
        self.add_path(cov_dir / cov, '.txt', key=cov)

        cmd = 'SparCC.py {data} -i {iterations} -c {cor_output} -v {cov_output} -a {stat}'

        # If running on permutations have commands execute in parallel
        if data_permutation is None:
            cmd += ';'
        else:
            cmd += '&'
        self.jobtext.append(cmd.format(data=data_file,
                                       iterations=self.iterations,
                                       cor_output=self.get_file(cor),
                                       cov_output=self.get_file(cov),
                                       stat=self.stat))

    def sparcc_permutations(self):
        """ Run sparcc on each generated permutation """
        files = [self.get_file('pvals') / 'permutation_{}.txt'.format(i)
                 for i in range(int(self.permutations))]
        for pfile in files:
            self.sparcc(pfile)

    def make_bootstraps(self):
        """ Create the shuffled datasets """
        cmd = 'MakeBootstraps.py {data} -n {permutations} -t permutation_#.txt -p {pvals}/'
        self.jobtext.append(cmd.format(data=self.get_file('correlation'),
                                       permutations=self.permutations,
                                       pvals=self.get_file('pvals')))

    def pseudo_pvals(self, sides='two'):
        """ Calculate the psuedo p-values """
        self.add_path('PseudoPval', '.txt')
        cmd = 'PseudoPvals.py {data} {perm} {iterations} -o {output} -t {sides}_sided'
        self.jobtext.append(cmd.format(data=self.get_file('correlation'),
                                       perm=self.get_file('pcorrelations') / 'correlation_perm_#.txt',
                                       iterations=self.iterations,
                                       output=self.get_file('PseudoPval'),
                                       sides=sides))

    def setup_analysis(self, summary=False):
        self.set_stage(0)
        self.create_sub_folders()
        self.extract_qiime2_feature_table()
        self.sparcc()
        self.set_stage(1)
        self.make_bootstraps()
        self.set_stage(2)
        self.sparcc_permutations()
        self.set_stage(3)
        self.pseudo_pvals()
        self.write_file_locations()
        super().setup_analysis(summary=summary)
