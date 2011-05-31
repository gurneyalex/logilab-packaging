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

        with tempdir(False) as tmpdir:
            tgz = builder.make_orig_tarball(tmpdir)
            self.assertTrue(os.path.exists(tgz))

    def test_make_tarball_rev2(self):
        os.chdir(os.path.join(os.path.dirname(__file__), 'data/packages/next'))
        builder = build.Builder()

        with self.assertRaises(LGPException):
            with tempdir(False) as tmpdir:
                builder.make_orig_tarball(tmpdir)

if __name__ == '__main__':
    unittest_main()
