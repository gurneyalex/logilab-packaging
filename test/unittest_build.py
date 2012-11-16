#!/usr/bin/python

from __future__ import with_statement

import os, os.path as osp
import tempfile
import tarfile

from logilab.common.testlib import TestCase, unittest_main, within_tempdir

from logilab.devtools.lgp.utils import tempdir
from logilab.devtools.lgp.exceptions import LGPCommandException
from logilab.devtools.lgp import build

from logilab.devtools.lgp.check import check_debsign


class BuildTC(TestCase):

    def setUp(self):
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_make_tarball_rev1(self):
        project_dir = self.datapath('packages/first')
        builder = build.Builder()
        builder.go_into_package_dir([project_dir])
        builder._set_package_format()

        with tempdir(False) as tmpdir:
            tgz = builder.make_orig_tarball(tmpdir)
            self.assertTrue(osp.exists(tgz))
            with tempdir(False) as tmpdir2:
                dscfile = builder.make_debian_source_package('sid', tmpdir=tmpdir2)
                self.assertTrue(osp.exists(dscfile))

    def test_make_tarball_rev2(self):
        project_dir = self.datapath('packages/next')
        builder = build.Builder()
        builder.go_into_package_dir([project_dir])
        builder._set_package_format()

        with self.assertRaises(LGPCommandException):
            with tempdir(False) as tmpdir:
                builder.make_orig_tarball(tmpdir)

    def test_make_tarball_with_orig(self):
        project_dir = self.datapath('packages/first')
        builder = build.Builder()
        builder.go_into_package_dir([project_dir])
        builder._set_package_format()

        with tempdir(False) as tmpdir:
            tgz1 = builder.make_orig_tarball(tmpdir)
            self.assertTrue(osp.exists(tgz1))

            project_dir = self.datapath('packages/next')
            builder = build.Builder()
            builder.go_into_package_dir([project_dir])
            builder._set_package_format()
            builder.config.orig_tarball = tgz1

            with tempdir(False) as tmpdir:
                tgz2 = builder.make_orig_tarball(tmpdir)
                self.assertFalse(os.system('diff -b %s %s' % (tgz1, tgz2)))
                self.assertEqual(osp.basename(tgz1), osp.basename(tgz2))
                tar1 = tarfile.open(tgz1, "r:gz")
                tar2 = tarfile.open(tgz2, "r:gz")

        self.assertSequenceEqual([(to.name,to.size) for to in tar1.getmembers()],
                                 [(to.name,to.size) for to in tar2.getmembers()])


class PostTreatmentTC(TestCase):

    @within_tempdir
    def test_post_treatments(self):
        builder = build.Builder()
        builder.go_into_package_dir([])
        resultdir = tempfile.gettempdir()
        builder.config.dist_dir = resultdir
        package_file = osp.join(resultdir, "lenny", "Packages.gz")
        self.assertFalse(osp.isfile(package_file))
        builder.run_post_treatments("lenny")
        self.assertTrue(osp.isfile(package_file))


class SignTC(TestCase):
    def test_check_sign(self):
        builder = build.Builder()
        builder.load_command_line_configuration(['--sign=no'])
        self.assertFalse(builder.config.sign)
        builder.load_command_line_configuration(['--sign=yes'])
        self.assertTrue(builder.config.sign)
        if 'GPG_AGENT_INFO' in os.environ:
            del os.environ['GPG_AGENT_INFO']
        self.assertTrue(check_debsign(builder) == 0)


if __name__ == '__main__':
    unittest_main()
