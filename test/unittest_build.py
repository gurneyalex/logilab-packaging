#!/usr/bin/python

import os

from logilab.common.testlib import TestCase, unittest_main

from logilab.devtools.lgp.utils import tempdir
from logilab.devtools.lgp.exceptions import LGPException
from logilab.devtools.lgp import build

class BuildTC(TestCase):

    def setUp(self):
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_make_tarball_rev1(self):
        os.chdir(os.path.join(os.path.dirname(__file__), 'data/packages/first'))
        builder = build.Builder()
        builder.go_into_package_dir(None)
        builder._set_package_format()

        with tempdir(False) as tmpdir:
            tgz = builder.make_orig_tarball(tmpdir)
            self.assertTrue(os.path.exists(tgz))
            with tempdir(False) as tmpdir2:
                dscfile = builder.make_debian_source_package('sid', tmpdir=tmpdir2)
                self.assertTrue(os.path.exists(dscfile))

    def test_make_tarball_rev2(self):
        os.chdir(os.path.join(os.path.dirname(__file__), 'data/packages/next'))
        builder = build.Builder()
        builder._set_package_format()

        with self.assertRaises(LGPException):
            with tempdir(False) as tmpdir:
                builder.make_orig_tarball(tmpdir)

if __name__ == '__main__':
    unittest_main()
