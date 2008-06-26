import unittest
from os.path import join, dirname
from cStringIO import StringIO

from logilab.common.testlib import TestCase

from logilab.devtools.lib.changelog import ChangeLog, DebianChangeLog

class ChangeLogTC(TestCase):
    cl_class = ChangeLog
    cl_file = join(dirname(__file__), 'data', 'ChangeLog')

    def test_round_trip(self):
        cl = self.cl_class(self.cl_file)
        out = StringIO()
        cl.write(out)
        self.assertStreamEquals(open(self.cl_file),
                               out)
                          
class DebianChangeLogTC(ChangeLogTC):
    cl_class = DebianChangeLog
    cl_file = join(dirname(__file__), 'data', 'debian', 'changelog')


if __name__  == '__main__':
    unittest.main()
