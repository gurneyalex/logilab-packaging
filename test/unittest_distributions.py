import unittest
from subprocess import Popen, PIPE

from logilab.common.testlib import TestCase
from logilab.devtools.buildpackage import get_distributions, KNOWN_DISTRIBUTIONS
from logilab.devtools.exceptions import DistributionException


class DistributionTC(TestCase):

    def test_default_distribution(self):
        self.assertEquals(get_distributions(), KNOWN_DISTRIBUTIONS)
        self.assertEquals(get_distributions('all'), KNOWN_DISTRIBUTIONS)

    def test_one_valid_distribution(self):
        distrib = 'lenny'
        self.assertEquals(get_distributions(distrib), [distrib])
        self.assertEquals(get_distributions([distrib]), [distrib])

    def test_several_valid_distributions(self):
        distrib = ['lenny', 'sid']
        self.assertEquals(get_distributions(distrib), distrib)
        distrib_str = "lenny,sid"
        self.assertEquals(get_distributions(distrib_str), distrib)

    def test_one_unvalid_distribution(self):
        distrib = ['winnie the pooh']
        self.assertRaises(DistributionException, get_distributions, distrib)

    def test_mixed_unvalid_distributions(self):
        distrib = KNOWN_DISTRIBUTIONS + ['winnie the pooh']
        self.assertRaises(DistributionException, get_distributions, distrib)

if __name__  == '__main__':
    unittest.main()
