Testing
#######


The project has PyTest-powered unit tests in the ``tests`` directory.
These are distributed with the package and also run on CI.

In order to run these tests, PyTest must be installed.

Either install PyTest from the package's development dependencies:

.. code:: bash

    $ pip install contacto.[dev]

Or install PyTest directly (to skip any unwanted extra dev dependencies):

.. code:: bash

    $ pip install pytest

Then run the tests as follows:

.. code:: bash

    $ python -m pytest -v
