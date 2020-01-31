.. contacto documentation master file, created by
   sphinx-quickstart on Thu Jan 30 19:08:44 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Contacto
========

.. image:: https://circleci.com/gh/Dawnflash/contacto.svg?style=shield&circle-token=6bac0991f94ce79de3df4510ec4e11258c29531f
    :target: https://circleci.com/gh/Dawnflash/contacto

.. image:: https://readthedocs.org/projects/contacto/badge/?version=latest
    :target: https://contacto.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. toctree::
   :maxdepth: 2
   :caption: Contents

   contacto
   description
   usage
   testing
   examples

* Repository: https://github.com/Dawnflash/contacto
* Documentation: https://contacto.readthedocs.io/en/latest/

Introduction
############

**Contacto** is a somewhat different take on contact managers.
It focuses on simplicity, modularity and expressiveness.

It is intended for use by tech-savvy people who need order in the sheer ocean of virtual entities they meet daily.

With the sea of services and accounts, people tend to develop various aliases which make it harder to track who is who.
Contacto helps with this problem by providing cross-referencing mechanics and robust search to accumulate and process identity info.

Contacto comes with a :ref:`section_cli` interface suitable for script automation and a more user-friendly :ref:`section_gui` (TBD).

Why Contacto?
#############

Contacto was built with the idea of expressiveness.

Contacts may have attributes with any names and any content.
There are no pre-defined properties and no pre-formatted fields.

This lets you set up your own classification system, custom tags, anything you need.

Contacto lets you store binary data such as images or keys,
features an expressive search, lets you draw relationships
between identities using cross-references and more.

Installation
############

Contacto requires Python 3.6.

You can easily install it from PyPI using pip

.. code:: bash

    $ pip install contacto

Alternatively you can clone the repository and run

.. code:: bash

    $ pip install .

.. _assignment_strategy:

Assignment strategy
###################

GHIA supports 3 assignment strategies:

* **append**: add matching users to existing assignees
* **set**: only process unassigned issues
* **change**: replace existing assignees with matching users

The default strategy is always ``append``.

.. _building_docs:

Building docs
#############

Install the package with the ``dev`` extras. Docs are in the ``docs`` directory.

.. code:: bash

    $ pip install .[dev]
    $ cd docs
    $ make html

License
#######

GHIA is distributed under the GNU GPLv3 license, see LICENSE.

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
