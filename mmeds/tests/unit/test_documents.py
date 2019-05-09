from unittest import TestCase
from pathlib import Path
import mongoengine as men


class DocTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        men.connect('test')

    @classmethod
    def tearDownClass(self):
        men.disconnect()

    def test_access(self):
        """"""
