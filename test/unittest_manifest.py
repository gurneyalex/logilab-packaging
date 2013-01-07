#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.
"""unittest for the lib/manifest.py module
"""

import sys
from os.path import dirname, join
from logilab.common.testlib import TestCase, unittest_main

from logilab.devtools.lib.manifest import *
from logilab.devtools.lib import TextReporter

reporter = TextReporter()

class MatchExtensionsFunctionTest(TestCase):

    def test_known_values_1(self):
        self.assertEqual(match_extensions('truc.py', ('.c', '.py',)), 1)

    def test_known_values_2(self):
        self.assertEqual(match_extensions('truc.po', ('.c', '.py',)), 0)

class ReadManifestInFunctionTest(TestCase):

    def test_known_values(self):
        self.assertEqual(read_manifest_in(reporter,
                                          dirname=join(dirname(__file__),'data/')),
                         ['good_file.xml', 'bin/tool.bat'])

# class GetManifestFilesFunctionTest(TestCase):

#     def test_known_values(self):
#         self.skipTest('manifest "prune" command ignored (#2888)')
#         # https://www.logilab.net/elo/ticket/2888
#         detected = get_manifest_files(dirname=join(dirname(__file__),'data/'))
#         detected.sort()
#         self.assertEqual(detected,
#                          ['ChangeLog',
#                           'bad_file.rst', 'bad_file.xml', 'bin/tool',
#                           'bin/tool.bat', 'good_file.rst', 'good_file.xml',
#                           'warning_rest.txt'])

if __name__ == '__main__':
    unittest_main()

