import unittest
import os.path

from logilab.common.testlib import TestCase
from logilab.devtools.lgp.utils import get_distributions
from logilab.devtools.lgp.exceptions import DistributionException



class DistributionTC(TestCase):

    def setUp(self):
        self.suites = os.path.abspath('data/suites')
        self.basetgz = os.path.abspath('data/basetgz')
        self.known = set(['hardy', 'intrepid', 'gutsy', 'lenny', 'oldstable',
                         'stable', 'breezy', 'edgy', 'feisty', 'jaunty',
                         'testing', 'sid', 'unstable', 'etch', 'squeeze',
                         'dapper'])

    def test_default_distribution(self):
        self.assertUnorderedIterableEquals(get_distributions(suites=self.suites),
                                           self.known)

    def test_valid_distribution(self):
        for distrib in ['stable', 'testing', 'sid', 'unstable']:
            self.assertEquals(get_distributions([distrib,],
                                                self.basetgz, self.suites),
                              (distrib,))

    def test_several_valid_distributions(self):
        distrib = ['stable', 'testing', 'sid', 'unstable']
        self.assertUnorderedIterableEquals(get_distributions(distrib,
                                                             self.basetgz,
                                                             self.suites),
                                           distrib)

    def test_all_distribution_keyword(self):
        self.assertUnorderedIterableEquals(get_distributions("all", basetgz=self.basetgz),
                                           set(["hardy", "intrepid", "jaunty", "lenny", "sid", "squeeze"]))
        self.assertRaises(DistributionException, get_distributions, ['unknown'],
                         basetgz=self.basetgz)

    def test_one_unvalid_distribution(self):
        distrib = ['unknown']
        self.assertRaises(DistributionException, get_distributions, distrib, self.basetgz)
        distrib = get_distributions(basetgz=self.basetgz, suites=self.suites) + \
                  tuple(distrib,)
        self.assertRaises(DistributionException, get_distributions, distrib, self.basetgz)

if __name__  == '__main__':
    unittest.main()
