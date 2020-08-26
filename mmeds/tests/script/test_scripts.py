from unittest import TestCase
from pathlib import Path
from subprocess import run


import mmeds.config as fig
from mmeds.util import setup_environment


TESTING = True


class ScriptTests(TestCase):

    def test_upload_metadata(self):
        # Execute the upload script
        env = setup_environment('mmeds-stable')
        cmd = "upload_metadata.py -s {} -f {} -t 'human' -u Tester -n Test_Study"
        output = run(cmd.format(fig.TEST_SUBJECT, fig.TEST_SPECIMEN).split(' '),
                     capture_output=True,
                     check=True,
                     env=env)
        print(output)

        # Verify the files were placed correctly

