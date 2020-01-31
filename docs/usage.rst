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

TBD

This feature is planned.

Despite a read-only GUI being planned in the original assignment,
I deemed improving core functionality a higher priority task.

Planned features
----------------

Contacto has a Qt GUI displaying the contact hierarchy.

You can invoke it using the ``qcontacto`` entrypoint:

.. code:: bash

    $ qcontacto [<database>]
