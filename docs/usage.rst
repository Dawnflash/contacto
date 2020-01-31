Usage
#####

.. _section_cli:

CLI
===

Contacto's CLI features a simple and automatable access to all features.

Invoke it using the ``contacto`` entrypoint or by calling the module:

.. code:: bash

    $ contacto
    $ python -m contacto

The CLI makes use of **refspec** and **valspec** :ref:`specifiers`.

See :ref:`section_cli_examples` for various CLI examples.

.. _section_gui:

GUI
===

For now, GUI is a simple read-only Qt demonstration.
It can only display the contact tree and perform import/export.

Image display, sorting, binary data exporting and R/W support
are among the planned features for the future.

You can invoke it using the ``qcontacto`` entrypoint or by invoking the
module directly:

.. code:: bash

    $ qcontacto [<database>]
    $ python -m contacto.gui [<database>]
