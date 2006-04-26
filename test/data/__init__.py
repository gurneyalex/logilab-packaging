""" Copyright (c) 2003 LOGILAB S.A. (Paris, FRANCE).
http://www.logilab.fr/ -- mailto:contact@logilab.fr

Logilab's developpment tools
"""

__revision__ = '$Id: __init__.py,v 1.1 2003-09-15 06:27:40 syt Exp $'

from os.path import join
TEMPLATE_DIR = join(__path__[0], 'templates')
del join
