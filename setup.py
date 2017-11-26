#!/usr/bin/env python

from __future__ import division

from setuptools import setup
from glob import glob
import ast
import re

__author__ = "The Clemente Lab"
__copyright__ = "Copyright (c) 2016 The Clemente Lab"
__credits__ = ["David S. Wallach", "Jose C. Clemente"]
__license__ = "GPL"
__maintainer__ = "David S. Wallach"
__email__ = "d.s.t.wallach@gmail.com"

# https://github.com/mitsuhiko/flask/blob/master/setup.py
_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('mmeds/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

setup(name='mmeds',
      version=version,
      description='',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
          'Programming Language :: Python :: 3.6',
          'Topic :: Scientific/Engineering :: Bio-Informatics',
      ],
      url='http://github.com/clemente-lab/mmeds-meta',
      author=__author__,
      author_email=__email__,
      license=__license__,
      packages=['mmeds'],
      scripts=glob('scripts/*py'),
      install_requires=[
          'numpy',
          'cherrypy'
      ],
      zip_safe=False)
