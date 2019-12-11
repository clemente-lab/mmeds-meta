#!/usr/bin/env python
from setuptools import setup
from glob import glob

__author__ = "The Clemente Lab"
__copyright__ = "Copyright (c) 2016 The Clemente Lab"
__credits__ = ["David S. Wallach", "Jose C. Clemente"]
__license__ = "GPL"
__maintainer__ = "David S. Wallach"
__email__ = "d.s.t.wallach@gmail.com"

setup(name='mmeds',
      version='0.5.0',
      description='',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
          'Programming Language :: Python :: 3.7',
          'Topic :: Scientific/Engineering :: Bio-Informatics',
      ],
      url='http://github.com/clemente-lab/mmeds-meta',
      author=__author__,
      author_email=__email__,
      license=__license__,
      packages=['mmeds'],
      include_package_data=True,
      scripts=glob('scripts/*.py'),
      install_requires=[
          'numpy',
          'cherrypy',
          'pymysql',
          'pandas',
          'mongoengine',
          'prettytable',
          'pint',
          'jupyter',
          'six',
          'pillow',
          'rpy2',
          'locustio',
          'codecov',
          'pytest-cov',
          'pytidylib',
          'ppretty',
          'imapclient',
          'psutil',
          'xlrd',
          'multiprocessing_logging',
          'pyyaml',
          'pandoc'
      ],
      zip_safe=False)
