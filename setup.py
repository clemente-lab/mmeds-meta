#!/usr/bin/env python
from setuptools import setup
from glob import glob

__author__ = "The Clemente Lab"
__copyright__ = "Copyright (c) 2021 The Clemente Lab"
__credits__ = ["David S. Wallach", "Jose C. Clemente"]
__license__ = "GPL"
__maintainer__ = "David S. Wallach"
__email__ = "d.s.t.wallach@gmail.com"

setup(name='mmeds',
      version='0.6.0',
      description='',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
          'Programming Language :: Python :: 3.9',
          'Topic :: Scientific/Engineering :: Bio-Informatics',
      ],
      url='http://github.com/clemente-lab/mmeds-meta',
      author=__author__,
      author_email=__email__,
      license=__license__,
      packages=[
          'mmeds',
          'mmeds.tools',
          'mmeds.database'
      ],
      include_package_data=True,
      scripts=glob('scripts/*.py'),
      install_requires=[
          'cherrypy==18.6.0',
          'codecov==2.1.11',
          'setuptools>=46.4.0',
          'jupyter==1.0.0',
          'mongoengine==0.23.0',
          'numpy==1.19.4',
          'pandas==1.2.3',
          'pandoc==2.0a4',
          'pint==0.17',
          'pillow==8.1.1',
          'ppretty==1.3',
          'prettytable==2.1.0',
          'psutil==5.8.0',
          'pudb==2020.1',
          'pygments==2.8.1',
          'pymysql==1.0.2',
          'pytest-cov==2.11.1',
          'pytest-pudb==0.7.0',
          'pytidylib==0.3.2',
          'pyyaml==5.4.1',
          'rpy2==3.4.3',
          'six==1.15.0',
          'xlrd==2.0.1',
          'click==7.1.2',
          'jaraco.classes==3.2.1',
          'jaraco.text==3.5.0',
          'jaraco.functools==3.3.0',
          'tempora==4.0.2'
      ],
      zip_safe=False)
