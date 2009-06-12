"""unittests for svn management"""


from logilab.common import testlib

import os, shutil, tempfile
from time import localtime, time

from logilab.devtools.vcslib import svn

class SVNAgentTC(testlib.TestCase):
    """test case for SVNAgent"""

    def setUp(self):
        """make test SVN directory"""
        self.tmp1 = tempfile.mkdtemp(dir='/tmp')
        self.tmp2 = tempfile.mkdtemp(dir='/tmp')
        os.system('svnadmin create %s' % self.tmp1)
        os.system('svn co file://%s %s > /dev/null' % (self.tmp1, self.tmp2))
        f = os.path.join(self.tmp2, 'README')
        stream = file(f,'w')
        stream.write('hop')
        stream.close()
        os.system('(cd %s && svn add README && svn ci -m "add readme file") >/dev/null' % self.tmp2)
        stream = file(f,'w')
        stream.write('hop hop')
        stream.close()
        os.system('(cd %s && svn ci -m "update readme file") >/dev/null' % self.tmp2)
        os.system('(cd %s && svn up) >/dev/null' % self.tmp2)

    def tearDown(self):
        """deletes temp files"""
        shutil.rmtree(self.tmp1)
        shutil.rmtree(self.tmp2)

    def test_status(self):
        """check that svn status correctly reports changes"""
        self.assertEquals(svn.SVNAgent.not_up_to_date(self.tmp2), [])
        f = os.path.join(self.tmp2, 'README')
        stream = file(f,'w')
        stream.write('hoooooooo')
        stream.close()
        self.assertEquals(len(svn.SVNAgent.not_up_to_date(self.tmp2)), 1)

    def test_log_info(self):
        try:
            login = os.getlogin()
        except OSError:
            import pwd
            login = pwd.getpwuid(os.getuid())[0]
        from_date = localtime(time() - 60*60*24)
        # add 1 minute since it seems to be svn log resolution
        to_date = localtime(time() + 60)
        self.assertEquals([str(cii) for cii in svn.SVNAgent.log_info('file://'+self.tmp1, from_date, to_date,
                                                                     'README')],
                          ['%s: update readme file (r2)' % login,
                           '%s: add readme file (r1)' % login])




if __name__ == '__main__':
    testlib.unittest_main()
