# -*- coding: ISO-8859-1 -*-
"""unittests for cvs management in OoBrother"""

__revision__ = '$Id: unittest_vcs_cvs.py,v 1.2 2005-01-12 14:20:44 syt Exp $'

import unittest
from utest_utils import make_test_fs, delete_test_fs

from logilab.devtools.vcslib import cvs

ENTRIES = """D/doc////
D/plugins////
D/test////
/registry.py/1.6/Thu Oct  7 11:11:11 2004//
/editors.py/1.2/Fri Oct  8 11:11:11 2004//
/__init__.py/1.11/Fri Oct  8 11:11:11 2004//
/oobrowser.py/1.21/Fri Oct  8 11:11:11 2004//
/sysutils.py/1.5/Fri Oct  8 11:11:11 2004//
/MANIFEST.in/1.1/Fri Oct  8 11:11:11 2004//
/setup.py/1.1/Fri Oct  8 11:11:11 2004//
/config_tools.py/1.9/Fri Oct  8 11:11:11 2004//
/TODO/1.15/Fri Oct  8 11:11:11 2004//
/__pkginfo__.py/1.3/Mon Oct 11 11:11:11 2004//
/uiutils.py/1.21/Tue Oct 12 11:11:11 2004//
/oobrowser.glade/1.7/Fri Oct  8 11:11:11 2004//
"""

ARCH = [('generated', ()),
        ('generated/CVS', ()),
        ]


class CVSAgentTC(unittest.TestCase):
    """test case for CVSAgent"""
    def setUp(self):
        """make test CVS directory"""
        make_test_fs(ARCH)
        entries = file('generated/CVS/Entries', 'w')
        entries.write(ENTRIES)
        entries.close()
        
    def test_get_info(self):
        d = cvs.get_info('generated')
        self.assertEquals(d,
                          {'MANIFEST.in': (4, '1.1', '', ''),
 'TODO': (4, '1.15', '', ''),
 '__init__.py': (4, '1.11', '', ''),
 '__pkginfo__.py': (4, '1.3', '', ''),
 'config_tools.py': (4, '1.9', '', ''),
 'doc': (4, '', '', ''),
 'editors.py': (4, '1.2', '', ''),
 'oobrowser.glade': (4, '1.7', '', ''),
 'oobrowser.py': (4, '1.21', '', ''),
 'plugins': (4, '', '', ''),
 'registry.py': (4, '1.6', '', ''),
 'setup.py': (4, '1.1', '', ''),
 'sysutils.py': (4, '1.5', '', ''),
 'test': (4, '', '', ''),
 'uiutils.py': (4, '1.21', '', '')}
)
        
    def tearDown(self):
        """deletes temp files"""
        delete_test_fs(ARCH)

    
    

if __name__ == '__main__':
    unittest.main()
