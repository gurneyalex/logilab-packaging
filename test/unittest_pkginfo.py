import os
from logilab.common.testlib import TestCase, unittest_main
from logilab.devtools.lib import pkginfo, TextReporter


class DefaultFunctionsTC(TestCase):

    def test_get_known_licenses(self):
        self.assertEqual(pkginfo.get_known_licenses(), ['CECILL', 'GPL', 'LCL', 'LGPL', 'PYTHON', 'ZPL'])

    def test_license_text(self):
        self.assertEqual(pkginfo.get_license_text('gpl'),
                          "This program is free software; you can redistribute it and/or modify it under\nthe terms of the GNU General Public License as published by the Free Software\nFoundation; either version 2 of the License, or (at your option) any later\nversion.\n\nThis program is distributed in the hope that it will be useful, but WITHOUT\nANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS\nFOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.\n\nYou should have received a copy of the GNU General Public License along with\nthis program; if not, write to the Free Software Foundation, Inc.,\n51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.\n\nOn Debian systems, the complete text of the GNU General Public License\nmay be found in '/usr/share/common-licenses/GPL-2'.\n")
        self.assertEqual(pkginfo.get_license_text('GPL'),
                          "This program is free software; you can redistribute it and/or modify it under\nthe terms of the GNU General Public License as published by the Free Software\nFoundation; either version 2 of the License, or (at your option) any later\nversion.\n\nThis program is distributed in the hope that it will be useful, but WITHOUT\nANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS\nFOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.\n\nYou should have received a copy of the GNU General Public License along with\nthis program; if not, write to the Free Software Foundation, Inc.,\n51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.\n\nOn Debian systems, the complete text of the GNU General Public License\nmay be found in '/usr/share/common-licenses/GPL-2'.\n")


class PkgInfoProject(TestCase):

    def test_pkginfo_project_itself(self):
        import logilab.devtools
        self.assertEqual(pkginfo.check_info_module(TextReporter(),
                                                    os.path.dirname(logilab.devtools.__file__)),
                                                    1)


if __name__ == '__main__':
    unittest_main()
