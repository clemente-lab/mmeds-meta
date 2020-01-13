from mmeds.config import DATABASE_DIR
from mmeds.tool import Tool

class Lefse(Tool):
    """ A class for LEfSe analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing,
                 analysis= True, restart_stage=0, kill_stage=0):
        super().__init__(owner, access_code, atype, config, testing, 
                         analysis=analysis, restart_stage=restart_stage)
        load = 'module use {}/.modules/modulefiles; module load sparcc;'.format(DATABASE_DIR.parent)
        self.jobtext.append(load)
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))
        self.module = load

        self.subclass = 'subclass' in self.doc.doc_type
        self.subjects = 'subjects' in self.doc.doc_type

    def format_input(self):
        """Convert uploaded .txt file into file type usable by LEfSe"""

        self.add_path('lefse_input', '.in')
        cmd = 'format_input.py {data} {output} -c 1'

        if self.subclass:
            cmd += ' -s 2'
        if self.subjects:
            cmd += ' -u 3'
        cmd += ' -o 1000000;'

        self.jobtext.append(cmd.format(data = self.get_file('lefse_table'),
                                       output=self.get_file('lefse_input')))

    def lefse(self):
        """Perform the analysis"""

        self.add_path('lefse_results', '.res')
        cmd = 'run_lefse.py {input_file} {output_file};'
        self.jobtext.append(cmd.format(input_file = self.get_file('lefse_input'),
                                       output_file = self.get_file('lefse_results')))

    def plot_results(self):
        """Create basic plot of the results"""

        self.add_path('plot_resutls', '.png')
        cmd = 'plot_res.py {input_file} {plot};'
        self.jobtext.append(cmd.format(input_file = self.get_file('lefse_results'),
                                       plot = self.get_file('lefse_plot')))

    def cladogram(self):
        """Create cladogram of the restuls"""

        self.add_path('cladogram', '.png')
        cmd = 'plot_cladogram.py {input_file} {cladogram} --format png;'
        self.jobtext.append(cmd.format(input_file = self.get_file('lefse_results'),
                                       cladogram = self.get_file('cladogram')))
    
    def features(self):
        """Create plots of abundance for specific bacteria
           Produce a .zip with just features identified as biomarkers and
           produce a .zip with all the features
        """ 
        
        self.add_path('features_biomarkers', '.zip')
        self.add_path('features_all', '.zip')
        cmd = 'plot_features.py -f {features} --archive zip {input_1} {input_2} {output};'
        self.jobtext.append(cmd.format(features = 'diff',
                                       input_1 = self.get_file('lefse_input'),
                                       input_2 = self.get_file('lefse_results'),
                                       output = self.get_file('features_biomarkers')))
        self.jobtext.append(cmd.format(features = 'all',
                                       input_1 = self.get_file('lefse_input'),
                                       input_2 = self.get_file('lefse_results'),
                                       output = self.get_file('features_all')))

    def setup_analysis(self):
        self.set_stage(0)
        self.format_input()
        self.set_stage(1)
        self.lefse()
        self.set_stage(2)
        self.plot_results()
        self.cladogram()
        self.features()
        self.write_file_locations()
        super().setup_analysis(summary = False)

