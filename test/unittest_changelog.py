from os.path import join, dirname
from cStringIO import StringIO

from logilab.common.testlib import TestCase, unittest_main

from logilab.devtools.lib.changelog import *


class ChangeLogTC(TestCase):
    cl_class = ChangeLog
    cl_file = join(dirname(__file__), 'data', 'ChangeLog')

    def test_round_trip(self):
        cl = self.cl_class(self.cl_file)
        out = StringIO()
        cl.write(out)
        self.assertMultiLineEqual(open(self.cl_file).read(),
                                  out.getvalue())


class DebianChangeLogTC(ChangeLogTC):
    cl_class = DebianChangeLog
    cl_file = join(dirname(__file__), 'data', 'debian', 'changelog')


class DebianVersionTC(TestCase):
    def test_simple(self):
        v = Version('1.2.3-2')
        self.assertEqual(v.upstream_version, '1.2.3')
        self.assertEqual(v.debian_revision, '2')
        self.assertEqual(str(v), '1.2.3-2')

    def test_nmu(self):
        v = Version('1.2.3-2.2')
        self.assertEqual(v.upstream_version, '1.2.3')
        self.assertEqual(v.debian_revision, '2.2')
        self.assertEqual(v.epoch, None)

        self.assertEqual(str(v), '1.2.3-2.2')

    def test_epoch(self):
        v = Version('1:1.2.3-2')
        self.assertEqual(v.upstream_version, '1.2.3')
        self.assertEqual(v.debian_revision, '2')
        self.assertEqual(v.epoch, "1")
        self.assertEqual(str(v), '1:1.2.3-2')

    def test_comparison(self):
        v1 = Version('1.2.3-1')
        v2 = Version('1.2.3-1')
        self.assertTrue(v1 == v2)
        v3 = Version('1.2.3-2')
        self.assertTrue(v1 < v3)
        self.assertTrue(v3 >= v1)
        v4 = Version('1.2.3~rc1-1')
        self.assertTrue(v4 < v1)


if __name__  == '__main__':
    unittest_main()
