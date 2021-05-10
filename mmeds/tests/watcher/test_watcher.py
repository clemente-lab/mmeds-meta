
from unittest import TestCase

from mmeds.spawn import Watcher
import coverage

coverage.process_startup()


class WatcherTests(TestCase):
    @classmethod
    def setUpClass(self):
        self.m = Watcher()

    def test(self):
        with self.assertRaises(SystemExit):
            self.m.start()
