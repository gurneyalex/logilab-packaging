"""unittests for mercurail management"""

__revision__ = '$Id: unittest_vcs_cvs.py,v 1.2 2005-01-12 14:20:44 syt Exp $'

import warnings
warnings.filterwarnings('ignore', "tempnam is a potential security risk to your program")

import os, shutil
from tempfile import mkdtemp
from logilab.common import testlib
from utest_utils import make_test_fs, delete_test_fs

from logilab.devtools.vcslib import hg

class HGAgentTC(testlib.TestCase):
    """test case for HGAgent"""

    def setUp(self):
        """make test HG directory"""
        self.tmp1 = mkdtemp(dir='/tmp')
        # self.tmp2 = mkdtemp(dir='/tmp')
        self.tmp2 = os.tempnam('/tmp')
        os.system('hg init %s' % self.tmp1)
        os.system('hg clone %s %s ' % (self.tmp1, self.tmp2))

    def test_status(self):
        """check that hg status correctly reports changes"""
        self.assertEquals(hg.HGAgent.not_up_to_date(self.tmp2), [])
        f = os.path.join(self.tmp2, 'toto')
        file(f,'w').close()
        # os.system('ls %s' % self.tmp2)
        self.assertEquals(len(hg.HGAgent.not_up_to_date(self.tmp2)), 1)
        
    def tearDown(self):
        """deletes temp files"""
        shutil.rmtree(self.tmp1)
        shutil.rmtree(self.tmp2)

    
    

if __name__ == '__main__':
    testlib.unittest_main()
