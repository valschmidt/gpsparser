#!/usr/bin/env python
'''
setup.py script for gpsparser.py
'''

from setuptools import setup, find_packages

setup(name = 'gpsparser',
      version = '0.0.5',      
      author = "Val Schmidt",
      maintainer = "Val Schmidt",
      maintainer_email = "vschmidt@ccom.unh.edu",
      author_email = "vschmidt@ccom.unh.edu",
      description = "gpsparser is a package for the parsing of GPS NMEA strings.",
      license = "GPL",
      zip_safe = True,
      packages = ['gpsparser']
)
