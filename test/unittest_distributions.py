import unittest

from logilab.common.testlib import TestCase
from logilab.devtools.lgp.utils import get_distributions, KNOWN_DISTRIBUTIONS
from logilab.devtools.lgp.exceptions import DistributionException


class DistributionTC(TestCase):

    def test_default_distribution(self):
        # important for help generation
        self.assertEquals(get_distributions("known"), tuple(set(KNOWN_DISTRIBUTIONS.keys())))
        self.assertEquals(get_distributions(), tuple(set(KNOWN_DISTRIBUTIONS.keys())))
        self.assertEquals(get_distributions("known"), tuple(set(KNOWN_DISTRIBUTIONS)))
        self.assertEquals(get_distributions(), tuple(set(KNOWN_DISTRIBUTIONS)))

    def test_one_valid_distribution(self):
        distrib = ['testing']
        self.assertEquals(get_distributions(distrib), tuple(distrib))

    def test_several_valid_distributions(self):
        distrib = ["unstable","testing"]
        self.assertEquals(sorted(get_distributions(distrib)), sorted(distrib))

    def test_one_unvalid_distribution(self):
        distrib = ['winnie the pooh']
        self.assertRaises(DistributionException, get_distributions, distrib)

    def test_codename_distribution(self):
        distrib = ['sid']
        self.assertNotEquals(get_distributions(distrib), distrib)

    def test_mixed_unvalid_distributions(self):
        distrib = get_distributions() + ('winnie the pooh',)
        self.assertRaises(DistributionException, get_distributions, distrib)

    def test_all_distribution_keyword(self):
        pass

if __name__  == '__main__':
    unittest.main()
