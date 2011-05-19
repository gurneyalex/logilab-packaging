import os.path

from logilab.common.testlib import TestCase, unittest_main
from logilab.devtools.lgp.utils import get_distributions
from logilab.devtools.lgp.exceptions import DistributionException



class DistributionTC(TestCase):

    def setUp(self):
        self.basetgz = os.path.join(os.path.dirname(__file__), 'data/basetgz')
        self.defined = ['hardy', 'intrepid', 'jaunty', 'lenny', 'sid', 'squeeze']
        self.known = set(['potato', 'sarge', 'lenny', 'woody', 'squeeze',
                          'stable', 'oldstable', 'breezy', 'edgy', 'feisty',
                          'jaunty', 'testing', 'sid', 'unstable', 'etch',
                          'etch-m68k', 'dapper', 'lucid', 'karmic', 'hoary',
                          'maverick', 'natty', 'oneiric', 'hardy', 'intrepid',
                          'gutsy', 'warty', 'wheezy'])
        self.suites = os.path.join(os.path.dirname(__file__), 'data/suites')

    def test_default_distribution(self):
        self.assertItemsEqual(get_distributions(suites=self.suites), self.known)

    def test_distribution_from_changelog(self):
        self.skipTest('not implemented')
        self.assertItemsEqual(get_distributions('changelog'), ['unstable'], suites=self.suites)

    def test_valid_distribution(self):
        for distrib in self.defined:
            self.assertEqual(get_distributions([distrib,], self.basetgz, suites=self.suites),
                              (distrib,))

    def test_several_valid_distributions(self):
        self.assertItemsEqual(get_distributions(self.defined,
                                               self.basetgz, suites=self.suites),
                             self.defined)

    def test_all_distribution_keyword(self):
        self.assertItemsEqual(get_distributions("all", self.basetgz, suites=self.suites),
                              self.defined)

    def test_one_unvalid_distribution(self):
        distrib = ['unknown']
        self.assertRaises(DistributionException, get_distributions, distrib,
                         basetgz=self.basetgz)
        distrib = self.defined + distrib
        self.assertRaises(DistributionException, get_distributions, distrib, self.basetgz)


if __name__  == '__main__':
    unittest_main()
