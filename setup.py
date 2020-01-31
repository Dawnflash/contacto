#! /usr/bin/env python
from setuptools import setup

with open("README.rst", "r") as f:
    long_description = f.read()

setup(
    name='contacto',
    version='0.2.1',
    description='A robust contact manager for social engineering.',
    long_description=long_description,
    long_description_content_type="text/x-rst",
    keywords='contacts, social engineering, Qt, cli',
    author='Adam Zahumensky',
    author_email='zahumada@fit.cvut.cz',
    license='GNU General Public License v3 (GPLv3)',
    url='https://github.com/Dawnflash/contacto',
    packages=['contacto'],
    package_data={'contacto': ['resources/*']},
    entry_points={
        'console_scripts': [
            'contacto = contacto.cli:main',
        ],
        'gui_scripts': [
            'qcontacto = contacto.gui:main',
        ],
    },
    python_requires='>=3.6',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Environment :: Console',
        'Environment :: X11 Applications :: Qt'
    ],
    install_requires=['PyQt5', 'click', 'pyyaml', 'pillow'],
    extras_require={
        'dev': ['sphinx', 'pytest'],
    },
    zip_safe=False,
)
