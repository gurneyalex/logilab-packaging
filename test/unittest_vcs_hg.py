"""unittests for vcslib.hg"""

import os, shutil,pwd
from time import localtime, time, sleep
from tempfile import mkdtemp, mktemp

from logilab.common import testlib

from utest_utils import make_test_fs, delete_test_fs


class HGAgentTC(testlib.TestCase):
    """test case for HGAgent"""

    def setUp(self):
        """make test HG directory"""
        try:
            import mercurial
        except ImportError:
            self.skip('mercurial is not installed')
        from logilab.devtools.vcslib import hg
        self.agent = hg.HGAgent
        self.tmp1 = mkdtemp(dir='/tmp')
        self.tmp2 = mktemp(dir='/tmp')
        os.system('hg init %s' % self.tmp1)
        os.system('hg clone %s %s >/dev/null' % (self.tmp1, self.tmp2))
        f = os.path.join(self.tmp2, 'README')
        sleep(1) # added to avoid misterious missing ci
        stream = file(f,'w')
        stream.write('hop')
        stream.close()
        os.system(('(cd %s && hg add README && hg ci -m "add readme file")'
                  +' >/dev/null 2>/dev/null') % self.tmp2)
        sleep(1) # added to avoid misterious missing ci
        stream = file(f,'w')
        stream.write('hop hop')
        stream.close()
        os.system(('(cd %s && hg ci -m "update readme file" && hg push)'
                  +' >/dev/null 2>/dev/null') % self.tmp2)
        #os.system(('(cd %s && hg pull && hg log)') % self.tmp2)

    def tearDown(self):
        """deletes temp files"""
        shutil.rmtree(self.tmp1)
        shutil.rmtree(self.tmp2)

    def test_status(self):
        """check that hg status correctly reports changes"""
        self.assertEquals(self.agent.not_up_to_date(self.tmp2), [])
        filename = os.path.join(self.tmp2, 'toto')
        stream = file(filename, 'w')
        stream.write('hello')
        stream.close()
        os.system('hg add -q -R %s %s' % (self.tmp2, filename))
        self.assertEquals(self.agent.not_up_to_date(self.tmp2),
            [('added', 'toto')])
        self.assertEquals(len(self.agent.not_up_to_date(self.tmp2)), 1)
        os.system('hg commit -R %s -m "." %s' % (self.tmp2, filename))
        self.assertEquals(self.agent.not_up_to_date(self.tmp2),
            [('outgoing', 'toto')])
        os.system('hg status -R %s' % self.tmp2)
        self.assertEquals(self.agent.not_up_to_date(self.tmp2),
            [('outgoing', 'toto')])
        os.system('echo "modif" >> %s' % filename)
        self.assertEquals(self.agent.not_up_to_date(self.tmp2),
            [('outgoing', 'toto'), ('modified', 'toto')])

    def test_log_info(self):
        login, _,_,_,_,home,_ = pwd.getpwuid(os.getuid())
        from_date = localtime(time() - 60*60*24)
        # add 1 minute since it seems to be svn log resolution
        to_date = localtime(time())
        # .split(':', 1)[1] to remove user 'name'
        self.assertEquals([str(cii).split(':', 1)[1] for cii in self.agent.log_info(self.tmp2, from_date, to_date)],
                          [' update readme file (1)',
                           ' add readme file (0)'])




if __name__ == '__main__':
    testlib.unittest_main()
