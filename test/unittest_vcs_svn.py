"""unittests for cvs management in OoBrother"""

__revision__ = '$Id: unittest_vcs_cvs.py,v 1.2 2005-01-12 14:20:44 syt Exp $'

import os, shutil
from logilab.common import testlib
from utest_utils import make_test_fs, delete_test_fs

from logilab.devtools.vcslib import svn

class SVNAgentTC(testlib.TestCase):
    """test case for SVNAgent"""

    def setUp(self):
        """make test SVN directory"""
        self.tmp1 = os.tempnam('/tmp')
        self.tmp2 = os.tempnam('/tmp')        
        os.system('svnadmin create %s' % self.tmp1)
        os.system('svn co file://%s %s' % (self.tmp1, self.tmp2))

    def test_status(self):
        """check that svn status correctly reports changes"""
        self.assertEquals(svn.SVNAgent.not_up_to_date(self.tmp2), [])
        f = os.path.join(self.tmp2, 'toto')
        file(f,'w').close()
        os.system('ls %s' % self.tmp2)
        self.assertEquals(len(svn.SVNAgent.not_up_to_date(self.tmp2)), 1)
        
    def tearDown(self):
        """deletes temp files"""
        shutil.rmtree(self.tmp1)
        shutil.rmtree(self.tmp2)

    
    

if __name__ == '__main__':
    testlib.unittest_main()
