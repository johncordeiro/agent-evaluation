import os
from distutils.core import setup

from setuptools import find_packages

DIST_NAME = "weni-agenteval"
VERSION = "1.0.4"
DESCRIPTION = "A generative AI-powered framework for testing virtual agents."
AUTHOR = "Weni"
EMAIL = "john.cordeiro@vtex.com"
URL = "https://github.com/weni-ai/agent-evaluation"
PACKAGE_DIR = "src"
REQUIRES_PYTHON = ">=3.9"
PACKAGE_DATA = {
    "": [
        "templates/**/*",
    ],
}


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()


setup(
    packages=find_packages(where=PACKAGE_DIR),
    package_dir={"": PACKAGE_DIR},
    package_data=PACKAGE_DATA,
)
