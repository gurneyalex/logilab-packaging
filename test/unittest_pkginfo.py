import os
from logilab.common.testlib import TestCase, unittest_main
from logilab.packaging.lib import pkginfo, TextReporter


class PkgInfoProject(TestCase):

    def test_pkginfo_project_itself(self):
        import logilab.packaging
        self.assertEqual(pkginfo.check_info_module(TextReporter(),
                                                    os.path.dirname(logilab.packaging.__file__)),
                                                    1)


if __name__ == '__main__':
    unittest_main()
