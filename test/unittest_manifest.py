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
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""unittest for the lib/manifest.py module
"""

__revision__ = '$Id: unittest_manifest.py,v 1.9 2005-07-26 09:41:25 syt Exp $'

import unittest
import sys
from logilab.devtools.lib.manifest import *
from logilab.devtools.lib import TextReporter

reporter = TextReporter()

class MatchExtensionsFunctionTest(unittest.TestCase):
    
    def test_known_values_1(self):
        self.assertEqual(match_extensions('truc.py', ('.c', '.py',)), 1)
        
    def test_known_values_2(self):
        self.assertEqual(match_extensions('truc.po', ('.c', '.py',)), 0)

class ReadManifestInFunctionTest(unittest.TestCase):
    
    def test_known_values(self):
        self.assertEqual(read_manifest_in(reporter, dirname='data/'),
                         ['bad_file.rst', 'bin/tool.bat'])
        
class GetManifestFilesFunctionTest(unittest.TestCase):
    
    def test_known_values(self):
        detected = get_manifest_files(dirname='data/')
        detected.sort()
        self.assertEqual(detected,
                         ['ChangeLog',
                          'bad_file.rst', 'bad_file.xml', 'bin/tool',
                          'bin/tool.bat', 'good_file.rst', 'good_file.xml',
                          'warning_rest.txt'])
        
if __name__ == '__main__':
    unittest.main()

