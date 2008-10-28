import unittest
from subprocess import Popen, PIPE

from logilab.common.testlib import TestCase
from logilab.devtools.lgp.utils import get_distributions, KNOWN_DISTRIBUTIONS
from logilab.devtools.lgp.exceptions import DistributionException


class DistributionTC(TestCase):

    def test_default_distribution(self):
        # important for help generation
        self.assertEquals(get_distributions("known"), tuple(set(KNOWN_DISTRIBUTIONS.keys())))

    def test_one_valid_distribution(self):
        distrib = 'lenny'
        self.assertEquals(get_distributions(distrib),    (distrib,))
        self.assertEquals(get_distributions((distrib,)), (distrib,))

    def test_several_valid_distributions(self):
        distrib = ('sid', 'lenny')
        self.assertEquals(sorted(get_distributions(distrib)), sorted(distrib))
        distrib_str = "sid,lenny"
        self.assertEquals(sorted(get_distributions(distrib_str)), sorted(distrib))

    def test_one_unvalid_distribution(self):
        distrib = ['winnie the pooh']
        self.assertRaises(DistributionException, get_distributions, distrib)

    def test_mixed_unvalid_distributions(self):
        distrib = get_distributions() + ('winnie the pooh',)
        self.assertRaises(DistributionException, get_distributions, distrib)

if __name__  == '__main__':
    unittest.main()
