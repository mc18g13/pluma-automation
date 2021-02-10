import os
from typing import Optional
import setuptools
import subprocess
import sys


def git_is_installed() -> bool:
    try:
        subprocess.check_call(['which', 'git'], stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return False
    else:
        return True


def get_version() -> Optional[str]:
    ''' Find the current pluma version from git tags using git-describe '''
    if not git_is_installed():
        raise EnvironmentError(
            f'{os.linesep*2}Git must be installed on the system.{os.linesep} See: '
            f'https://git-scm.com/book/en/v2/Getting-Started-Installing-Git{os.linesep}'
        )

    version_str = None
    try:
        version = subprocess.check_output(
            ['git', 'describe', '--tags', '--always', '--match', 'v*.*.*'])
        version_str = version.decode('utf-8').strip()
    except Exception as e:
        print('Failed to read Git version, possibly because not .git repository'
              f' is present in this folder:{os.linesep*2}{str(e)}')
    finally:
        return version_str


readme_file = 'README.md'
long_description = None
long_description_content_type = None
with open(readme_file, 'r') as fh:
    long_description = fh.read()
    long_description_content_type = 'text/markdown'

requires = [
    'pyserial',
    'setuptools',
    'pyudev',
    'pexpect>=4.6',
    'pyftdi',
    'pyroute2',
    'pandas',
    'pygal',
    'cairosvg',
    'graphviz',
    'nanocom',
    'requests',
    'pytest',
    'pytest-xdist',
    'coverage',
    'pyyaml>=5.1',
    'atlassian-python-api',
    'deprecated'
]

# dataclasses backport for 3.6
if sys.version_info[:2] == (3, 6):
    requires.append('dataclasses')

setuptools.setup(
    name='pluma',
    version=get_version(),
    author='Witekio',
    author_email='ext.eng-plumadev@witekio.com',
    description=('Pluma Automation is a test and automation framework for'
                 'embedded devices, with a focus on ease of use.'),
    long_description=long_description,
    long_description_content_type=long_description_content_type,
    url='https://github.com/Witekio/pluma-automation/',
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': ['pluma=pluma.__main__:main'],
    },
    python_requires='>=3.6',
    install_requires=requires,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX :: Linux'
    ],
)
