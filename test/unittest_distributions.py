import os.path

from logilab.common.testlib import TestCase, unittest_main
from logilab.devtools.lgp.utils import get_distributions
from logilab.devtools.lgp.exceptions import DistributionException



class DistributionTC(TestCase):

    def setUp(self):
        self.suites = os.path.abspath('../etc/lgp/suites')
        self.basetgz = os.path.abspath('data/basetgz')
        self.defined = ['hardy', 'intrepid', 'jaunty', 'lenny', 'sid', 'squeeze']
        self.known = set(['hardy', 'intrepid', 'gutsy', 'lenny', 'oldstable',
                          'stable', 'breezy', 'edgy', 'feisty', 'jaunty',
                          'testing', 'sid', 'unstable', 'etch', 'squeeze',
                          'dapper', 'lucid', 'karmic'])

    def test_default_distribution(self):
        self.assertItemsEqual(get_distributions(suites=self.suites),
                              self.known)

    def test_valid_distribution(self):
        for distrib in self.defined:
            self.assertEqual(get_distributions([distrib,], self.basetgz, self.suites),
                              (distrib,))

    def test_several_valid_distributions(self):
        self.assertItemsEqual(get_distributions(self.defined,
                                               self.basetgz,
                                               self.suites),
                             self.defined)

    def test_all_distribution_keyword(self):
        self.assertItemsEqual(get_distributions("all", self.basetgz, self.suites),
                              self.defined)

    def test_one_unvalid_distribution(self):
        distrib = ['unknown']
        self.assertRaises(DistributionException, get_distributions, distrib,
                         basetgz=self.basetgz, suites=self.suites)
        distrib = self.defined + distrib
        self.assertRaises(DistributionException, get_distributions, distrib, self.basetgz)

if __name__  == '__main__':
    unittest_main()
