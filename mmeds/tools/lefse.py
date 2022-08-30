from mmeds.config import DATABASE_DIR
from mmeds.tools.tool import Tool
from mmeds.util import get_file_index_entry_location


class Lefse(Tool):
    """ A class for LEfSe analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type,  config, testing,
                 run_on_node, analysis=True, child=False, restart_stage=0, kill_stage=-1):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, run_on_node,
                         analysis=analysis, child=child, restart_stage=restart_stage, kill_stage=kill_stage)
        if testing:
            load = 'module use {}/.modules/modulefiles; module load lefse;'.format(DATABASE_DIR.parent)
        else:
            load = 'ml anaconda3;\nsource activate lefse;'
        self.jobtext.append(load)
        self.module = load

        self.subclass = None
        self.subjects = None

    def extract_feature_table(self):
        self.add_path('tmp_unzip')
        self.add_path('biom_feature', '.biom')
        self.add_path('feature_table', '.tsv')
        table = get_file_index_entry_location(self.path.parent, 'Qiime2', 'filtered_table')
        self.unzip_general(table, self.get_file('tmp_unzip'))
        self.move_general(self.get_file('tmp_unzip') / 'data' / 'feature-table.biom', self.get_file('biom_feature'))
        self.source_activate("qiime")
        self.biom_convert(self.get_file('biom_feature'), self.get_file('feature_table'))

    def process_qiime_input(self):
        """ Generate table that LEfSe can read from qiime output using MMEDS script """

        self.add_path('lefse_table', '.tsv')
        self.source_activate("mmeds")

    def format_input(self):
        """ Convert uploaded .txt file into file type usable by LEfSe """

        self.add_path('lefse_input', '.in')
        cmd = 'format_input.py {data} {output} -c 1'

        if self.subclass:
            cmd += ' -s 2'
            if self.subjects:
                cmd += ' -u 3'
        elif self.subjects:
            cmd += ' -u 2'
        cmd += ' -o 1000000;'

        self.jobtext.append(cmd.format(data=self.get_file('lefse_table'),
                                       output=self.get_file('lefse_input')))

    def lefse(self):
        """ Perform the analysis """

        self.add_path('lefse_results', '.res')
        cmd = 'run_lefse.py {input_file} {output_file};'
        self.jobtext.append(cmd.format(input_file=self.get_file('lefse_input'),
                                       output_file=self.get_file('lefse_results')))

    def plot_results(self):
        """ Create basic plot of the results """

        self.add_path('results_plot', '.png')
        cmd = 'plot_res.py {input_file} {plot};'
        self.jobtext.append(cmd.format(input_file=self.get_file('lefse_results'),
                                       plot=self.get_file('results_plot')))

    def cladogram(self):
        """ Create cladogram of the results """

        self.add_path('results_cladogram', '.png')
        cmd = 'plot_cladogram.py {input_file} {cladogram} --format png;'
        self.jobtext.append(cmd.format(input_file=self.get_file('lefse_results'),
                                       cladogram=self.get_file('results_cladogram')))

    def features(self):
        """ Create plots of abundance for specific bacteria
            Produce a .zip with just features identified as biomarkers and
            produce a .zip with all the features
        """

        self.add_path('features_biomarkers', '.zip')
        self.add_path('features_all', '.zip')
        cmd = 'plot_features.py -f {features} --archive zip {input_1} {input_2} {output};'
        self.jobtext.append(cmd.format(features='diff',
                                       input_1=self.get_file('lefse_input'),
                                       input_2=self.get_file('lefse_results'),
                                       output=self.get_file('features_biomarkers')))
        self.jobtext.append(cmd.format(features='all',
                                       input_1=self.get_file('lefse_input'),
                                       input_2=self.get_file('lefse_results'),
                                       output=self.get_file('features_all')))

    def setup_analysis(self, summary=False):
        self.subclass = 'subclass' in self.doc.reads_type
        self.subjects = 'subjects' in self.doc.reads_type
        self.set_stage(0)
        self.extract_feature_table()
        self.format_input()
        self.set_stage(1)
        self.lefse()
        self.set_stage(2)
        self.plot_results()
        self.cladogram()
        self.features()
        self.write_file_locations()
        super().setup_analysis(summary=summary)
