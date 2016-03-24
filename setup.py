try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Handover notification and permission system for Duke Data Service',
    'author': 'Dan Leehr',
    'url': 'https://github.com/Duke-GCB/DukeDSHandoverService',
    'author_email': 'dan.leehr@duke.edu',
    'version': '0.1',
    'test_suite': 'tests',
    'packages': ['handover_api'],
    'scripts': [],
    'name': 'DukeDSHandoverService'
}

setup(**config)
