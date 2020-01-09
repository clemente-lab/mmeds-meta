from mmeds.tool import tool

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

        TODO: kill stage value

    #format
    #run
    #plot
    #cladogram
    #other plots


    def setup_analysis:
        self.set_stage(0)
        #format
        self.set_stage(1)
        #run
        self.set_stage(2)
        #plot
        #cladogram
        #other plots
        super().setup_analysis()

