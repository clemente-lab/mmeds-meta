from mmeds.config import DATABASE_DIR
from mmeds.tools.tool import Tool


class PiCRUSt1(Tool):
    """ A class for SparCC analysis of uploaded studies. """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, run_on_node,
                 analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing,
                         run_on_node=run_on_node, analysis=analysis, restart_stage=restart_stage, kill_stage=kill_stage,
                         child=child)
        if testing:
            load = 'module use {}/.modules/modulefiles; module load picrust1;'.format(DATABASE_DIR.parent)
        else:
            load = 'ml picrust;'
        self.jobtext.append(load)
        self.module = load

    def convert_to_biom(self):
        """
        Converts the currently stored OTU file in biom format
        """
        self.add_path('biom_table', '.biom')
        cmd = 'biom convert -i {} --to-hdf5 -o {}'.format(self.get_file('otu_table'),
                                                          self.get_file('biom_table'))
        self.jobtext.append(cmd)

    def normalize_otu(self):
        """
        Normalizes the OTU table by dividing each OTU by the known/predicted 16S copy number abdundance.
        ================================================================================
        Input is the users OTU table (that has been referenced picked against Greengenes).
        """
        self.add_path('normalized_otu', '.biom')
        cmd = 'normalize_by_copy_number.py -i {} -o {}'.format(self.get_file('biom_table'),
                                                               self.get_file('normalized_otu'))
        self.jobtext.append(cmd)

    def predict_metagenomes(self):
        """
        predict_metagenomes.py creates the final metagenome functional predictions.
        It multiplies each normalized OTU abundance by each predicted functional
        trait abundance to produce a table of functions (rows) by samples (columns).
        """
        self.add_path('meta_predictions', '.tab')
        self.add_path('nsti_values', '.tab')
        cmd = 'predict_metagenomes.py -i {} -o {} -a {}'.format(self.get_file('normalized_otu'),
                                                                self.get_file('meta_predictions'),
                                                                self.get_file('nsti_values'))
        self.jobtext.append(cmd)

    def setup_analysis(self, summary=False):
        self.set_stage(0)
        self.convert_to_biom()
        self.set_stage(1)
        self.normalize_otu()
        self.set_stage(2)
        self.predict_metagenomes()
        self.write_file_locations()
        super().setup_analysis(summary=summary)
