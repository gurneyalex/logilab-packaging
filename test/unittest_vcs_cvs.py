# -*- coding: utf-8 -*-
"""unittests for cvs management in OoBrother"""

from logilab.common import testlib

import shutil, tempfile, os, os.path as osp
from time import localtime, time, sleep
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


class GetInfoTC(testlib.TestCase):
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



class CVSAgentTC(testlib.TestCase):
    """test case for CVSAgent"""

    def setUp(self):
        """make test CVS directory"""
        self.tmp1 = tempfile.mkdtemp(dir='/tmp')
        os.system('cvs -d %s init' % self.tmp1)
        os.mkdir(osp.join(self.tmp1, 'module'))
        self.tmp2 = tempfile.mkdtemp(dir='/tmp')
        os.system(('cvs -d %s co -d %s module'
                  +' >/dev/null 2>/dev/null') % (self.tmp1, self.tmp2))
        f = os.path.join(self.tmp2, 'README')
        stream = file(f,'w')
        stream.write('hop')
        stream.close()
        os.system( ('(cd %s && cvs add README &&'
                   +' cvs ci -m "add readme file") >/dev/null 2>/dev/null')
                    % self.tmp2
                 )
        sleep(0.001) # added to avoid misterious missing ci
        stream = file(f,'w')
        stream.write('hop hop')
        stream.close()
        os.system(('(cd %s && cvs ci -m "update readme file")'
                  +' >/dev/null 2>/dev/null') % self.tmp2)
        #os.system('cd %s && cvs log' % self.tmp2)

    def tearDown(self):
        """deletes temp files"""
        shutil.rmtree(self.tmp1)
        shutil.rmtree(self.tmp2)

    def test_status(self):
        """check that cvs status correctly reports changes"""
        self.assertEquals(cvs.CVSAgent.not_up_to_date(self.tmp2), [])
        f = os.path.join(self.tmp2, 'README')
        stream = file(f,'w')
        stream.write('hoooooooo')
        stream.close()
        self.assertEquals(len(cvs.CVSAgent.not_up_to_date(self.tmp2)), 1)

    def test_log_info(self):
        try:
            login = os.getlogin()
        except OSError:
            import pwd
            login = pwd.getpwuid(os.getuid())[0]
        from_date = localtime(time() - 60*60*24)
        # add some minutes since it seems to be cvs log resolution
        to_date = localtime(time() + 1200)
        log_info = cvs.CVSAgent.log_info(self.tmp1, from_date, to_date, 'module/README')
        log_info = [str(cii) for cii in log_info]

        expected_result = ['%s: update readme file (1.2)' % login,
                           '%s: add readme file (1.1)' % login]
        self.assertEquals(log_info, expected_result)


if __name__ == '__main__':
    testlib.unittest_main()
