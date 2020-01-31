Contacto
========

.. image:: https://circleci.com/gh/Dawnflash/contacto.svg?style=shield&circle-token=6bac0991f94ce79de3df4510ec4e11258c29531f
    :target: https://circleci.com/gh/Dawnflash/contacto

.. image:: https://readthedocs.org/projects/contacto/badge/?version=latest
    :target: https://contacto.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

Welcome to the Contacto project!

This is an attempt to bring maximum flexibility to contact managers.

Contacto is targeted at developers and has a simple interface:

.. code:: bash

    $ pip install contacto
    $ contacto -o new.db set -r Family/Mom/age 48
    $ contacto -o new.db get
    > Family
      - Mom
        - age: 48

Links
-----

* `Documentation <https://ghia-zahumada.readthedocs.io/en/latest/>`_
* `PyPI project <https://pypi.org/project/contacto/>`_
* `Project assignment <ASSIGNMENT.rst>`_

CLI
---

Operate the manager from the command line.

.. code:: bash

    $ contacto
    $ python -m contacto

GUI
---

TBD. Coming soon!

Building docs
-------------

Install the package with the ``dev`` extras.
Docs are in the ``docs`` directory.

.. code:: bash

    $ pip install .[dev]
    $ cd docs
    $ make html

License
-------

Contacto is distributed under the GNU GPLv3 license, see `<LICENSE>`_.
