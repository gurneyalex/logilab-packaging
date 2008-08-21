import unittest
from os.path import join, dirname
from cStringIO import StringIO

from logilab.common.testlib import TestCase

from logilab.devtools.lib.changelog import *

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


class DebianVersionTC(TestCase):
    def test_simple(self):
        v = DebianVersion('1.2.3-2')
        self.assertEquals(v.upstream_version, '1.2.3')
        self.assertEquals(v.debian_version, '2')
        self.assertEquals(str(v), '1.2.3-2')

    def test_nmu(self):
        v = DebianVersion('1.2.3-2.2')
        self.assertEquals(v.upstream_version, '1.2.3')
        self.assertEquals(v.debian_version, '2.2')
        self.assertEquals(v.epoch, "")

        self.assertEquals(str(v), '1.2.3-2.2')



    def test_epoch(self):
        v = DebianVersion('1:1.2.3-2')
        self.assertEquals(v.upstream_version, '1.2.3')
        self.assertEquals(v.debian_version, '2')
        self.assertEquals(v.epoch, "1")
        self.assertEquals(str(v), '1:1.2.3-2')

    def test_comparison(self):
        v1 = DebianVersion('1.2.3-1')
        v2 = DebianVersion('1.2.3-1')
        self.failUnless(v1 == v2)
        v3 = DebianVersion('1.2.3-2')
        self.failUnless(v1 < v3)
        self.failUnless(v3 >= v1)
        v4 = DebianVersion('1.2.3~rc1-1')
        self.failUnless(v4 < v1)

if __name__  == '__main__':
    unittest.main()
