.. _section_examples:

Code examples
=============

In the following examples, consider the following ``my.yml`` file:

.. code:: yaml

    Family:
        Dad:
            catpic: REF:Family/Mom/catpic
            thumbnail: REF:Family/Dad/catpic
            real name: Matthew Logan
            spouse: REF:Family/Mom
        Mom:
            occupation: michelin cook
            real name: Anastasia Logan
            web: https://github.com
            catpic: FILE:path/to/cat.jpg
    Friends:
        Albatros:
            aliases: theunspoken, ninja
            relationship: friend
            url_bin: URL:file:path/to/bin.dat
        Nappo:
            aliases: Bappo
            relationship: special
            bin_source: file:path/to/bin.dat
        NoAttributesHere:
    NoEntitiesHere:

This is a functional YAML you may import.
Notice the **valspecs** determining attribute data types.

.. _section_cli_examples:

CLI examples
############

Let's jump-start from zero:

.. code:: bash

    $ contacto -o my.db set -r Friends/Albatros/age 18
    $ contacto -o my.db get
    > Friends
      - Albatros
        - age: 18

The above example recursively created the Albatros friend and set his age
in the ``my.db`` database.

Now let's import the ``my.yml`` file to expand our database:

.. code:: bash

    $ contacto -o my.db import my.yml
    $ contacto -o my.db get /Albatros
    > Friends
      - Albatros
        - age    : 18
        - aliases: theunspoken, ninja
        ...

Data from ``my.yml`` have been merged in.
Let's merge ``Nappo`` into ``Albatros`` and print the result:

.. code:: bash

    $ contacto -o my.db merge Friends/Nappo Friends/Albatros
    $ contacto -o my.db get Friends/Albatros
    > aliases     : Bappo
      relationship: special
      ...

As you can see, since the ``Friends/Albatros`` is a strict refspec,
Group and Entity information is not printed, it is assumed to be known.

.. _section_plugin_example:

Plugin example
--------------

Plugins may be run from the CLI.
The following example lists available plugins and then runs
``plug1`` and ``plug2``.

The example assumes that ``contacto_plug1`` and ``contacto_plug2`` are
reachable as top-level modules in the current context
(see :ref:`section_plugins`).

.. code:: bash

    $ contacto -o my.db plugins -l
    $ contacto -o my.db plugins plug1 plug2


API examples
############

This section illustrates the inner workings of Contacto.

We shall use an in-memory database:

.. testsetup::

    from contacto.storage import Storage
    from contacto.helpers import DType
    from contacto.view import View
    from contacto.serial import Serial

>>> stor = Storage(':memory:')

Creating a contact tree
-----------------------

Let's create a Friends/Albatros entity and set his ``age`` to 18:

>>> friends = stor.create_group_safe('Friends')
>>> albtrs = friends.create_entity_safe('Albatros')
>>> age = albtrs.create_attribute_safe('age', DType.TEXT, '18')
>>> age is stor.get_attribute('Friends', 'Albatros', 'age')
True

This shows how tree elements create their children.
The Storage object ``stor`` can then find the created attribute.

Merging entities
----------------

>>> nappo = friends.create_entity_safe('Nappo')
>>> _ = nappo.create_attribute_safe('age', DType.TEXT, '20')
>>> albtrs.merge(nappo)
>>> age.data
'20'

Notice that Albatros's age was replaced by Nappo's.

Filtering data
--------------

The ``View`` class lets us scope things out.
Let's add Nappo back with a different age (50):

>>> nappo = friends.create_entity_safe('Nappo')
>>> _ = nappo.create_attribute_safe('age', DType.TEXT, '50')

Now let's use ``View`` to only get 50-years-old friends:

>>> view = View(stor)
>>> view.set_attr_value_filter('50', False)
>>> view.filter()
>>> view.groups['Friends'].entities.keys()
dict_keys(['Nappo'])

Since Albatros isn't 50 years old, he is filtered out.

Exporting filtered data
-----------------------

The ``Serial`` class takes care of serialization:

>>> ser = Serial(view)
>>> ser.dump()
Friends
- Nappo
  - age: 50
