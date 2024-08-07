from unittest import TestCase, expectedFailure
from pathlib import Path
import mmeds.config as fig
from subprocess import run, CalledProcessError

from mmeds.util import setup_environment
from mmeds.logging import Logger

class SnakemakeTests(TestCase):
    """ Test running analyses """
    @classmethod
    def setUpClass(cls):
        """ Set up tests """
        # path to an example study, created from a MMEDs upload of existing test files
        # definied in config.py
        cls.mmeds_env = setup_environment("mmeds-stable")

    def run_snakemake(self, path):
        """ Run graph generation and Snakemake dry run in a given directory """
        snakefile = path / 'Snakefile'
        dag = path / 'test_dag.pdf'
        rulegraph = path / 'test_rulegraph.pdf'
        try:
            run(f"cp {path / f'{path.name}.Snakefile'} {snakefile}; \
                sed -i 's|snakemake_dir|{fig.SNAKEMAKE_RULES_DIR}|g' {snakefile}",
                shell=True, check=True)
            run(f"cd {path}; snakemake --dag | dot -Tpdf > {dag}",
                shell=True, check=True, env=self.mmeds_env)
            run(f"cd {path}; snakemake --rulegraph | dot -Tpdf > {rulegraph}",
                shell=True, check=True, env=self.mmeds_env)
            run(f"cd {path}; snakemake -n",
                shell=True, check=True, env=self.mmeds_env)
        except CalledProcessError as e:
            Logger.error(e)
            self.assertTrue(False)
        run(f"rm -f {dag}; rm -f {rulegraph}; rm -f {snakefile}", shell=True)
        return 0


    def test_a_standard_pipeline(self):
        """ Test snakemake standard pipeline analysis """
        result = self.run_snakemake(Path(fig.TEST_SNAKEMAKE_DIR) / "standard_pipeline")
        self.assertEquals(result, 0)


    def test_b_lefse(self):
        """ Test snakemake lefse analysis """
        result = self.run_snakemake(Path(fig.TEST_SNAKEMAKE_DIR) / "lefse")
        self.assertEquals(result, 0)

    @expectedFailure
    def test_c_lefse_failure(self):
        """ Test analysis with undefined snakemake method """
        result = self.run_snakemake(Path(fig.TEST_SNAKEMAKE_DIR) / "lefse_failure")
        self.assertEquals(result, 0)
