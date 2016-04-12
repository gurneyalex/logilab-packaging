from __future__ import print_function

from os.path import dirname, abspath
from unittest import TestCase, main
from logilab.packaging.lib import pkginfo, TextReporter


class PkgInfoProject(TestCase):

    def test_pkginfo_project_itself(self):
        pkgdir = dirname(dirname(abspath(__file__)))
        self.assertEqual(1, pkginfo.check_info_module(TextReporter(), pkgdir))


if __name__ == '__main__':
    main()
