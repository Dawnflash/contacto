
How it works
============

Contacto organizes contact data into a tree structure.

The tree root is a wrapper around an SQLite database which holds the data.
The rest of the tree consists of Groups_, Entities_ and Attributes_.

Tree elements
#############

Groups
------

Groups are just a collection of entities with a unique name.

Entities
--------

Entities hold attributes and may have an associated thumbnail.

Setting the thumbnail is usually done by setting a binary ``thumbnail`` attribute.
See Thumbnails_ for more info.

Attributes
----------

Attributes are the tree leaves and hold arbitrary contact data.

There are 4 types:

* **Text**: contains text data, may be searched in
* **Binary**: contains binary data such as images
* **Entity reference**: refers to an entity in the same tree
* **Attribute reference**: refers to an attribute in the same tree

The latter two types are tree cross-references, also called **XREFs**.
These are used to track relationships within the tree.

Entity references may be used to indicate entity relationships and
attribute references allow attributes to track each other.

Attribute references may form reference chains which must ultimately
terminate at an entity or a non-reference attribute.

If a loop would form at any point during tree transformation, the program
will reject that transformation.

.. _specifiers:

Specifiers
##########

In this section I describe the terms **refspec** and **valspec** used
throughout the documentation.

Group names are globally unique, entity names are unique within a group and
attribute names are unique within an entity.
Names are non-empty and must not include a slash (`/`) character.

While this is a functional limitation, it allows describing contact data using
only their named path!

This named path called **refspec** (reference specifier) is used throughout
the project for matching contact tree members from groups to attributes.

A **refspec** has the form ``GROUP/ENTITY/ATTRIBUTE``.

There are two types of refspecs used throughout the project:

* **Fully-specified (strict)**:
    Uniquely defines a group (``GROUP``), entity (``GROUP/ENTITY``)
    or attribute (``GROUP/ENTITY/ATTRIBUTE``).

    Examples: ``Family/Dad``, ``Friends/Jack/favorite_color``.
* **Generic**
    Defines a set of tree elements matching name criteria.
    Any refspec part may be omitted. Useful for searching within the tree.

    Examples:

    * ``/Jack`` matches ``Jack`` entities in any group
    * ``//tag`` matches ``tag`` attributes in any entity
    * ``Friends//tag`` matches ``tag`` attributes in the ``Friends`` group

Attribute values also have a specifier called **valspec** which determines
their source and type.
These are used when setting new attributes in :ref:`section_cli`
and in export YAML files.


* ``FILE:<filename>`` specifies **binary** data read from a file
* ``URL:<url>`` specifies **binary** data read from an URL
* ``REF:<strict_refspec>`` specifies a tree reference
* Anything else is considered direct **text** data


Special operations
##################

Besides the common operations such as ``get``, ``set``, ``search``, etc.
Contacto provides a few non-trivial ones:

* **Merge**
    Merges two tree elements of the same type, recursively
    merging their children, if any.

    This also attempts to re-target XREFs and fails in case of loop induction.
* **Rotate**
    Attributes may be rotated in a logrotate-like fashion,
    letting users maintain history of their values.

    This is very useful when tracking live changes such as avatar updates.


Import / Export
###############

Contacto supports the YAML format for importing and exporting tree data.

An example YAML file may be found in :ref:`section_examples`.


Thumbnails
##########

Entity thumbnails may be set directly using the Group API but the method
preferred in external use is setting a ``thumbnail`` attribute.

This attribute may be **binary** or an **AXREF** resolving to a binary one.

If the ``thumbnail`` attribute of an entity does not contain a valid image,
it is not loaded and the thumbnail does not update.

.. _section_plugins:

Plugins
#######

Contacto supports external plugins by naming convention.

Plugins are not run automatically but are called when specified
(for example using a CLI command, see :ref:`section_plugin_example`).

Contacto requires all plugins to be available as top-level modules and be
named ``contacto_<plugin_name>`` in order to be discovered.

An example plugin, ``watchdog``, is included in the ``plugins`` directory
of the project.
If you wish to experiment with it, put it in your current directory or
otherwise make it available as top-level module.

**Warning**: the ``plugins`` directory is not a plugin storage, it's there to
demonstrate what a Contacto plugin looks like.
Plugins may be simply distributed via PyPI.

Plugin interface
----------------

Contacto plugins must have a ``plugin_init`` function which receives
a Storage object (see :ref:`section_module_storage`).

The plugin may then freely modify the database.

Plugin design
-------------

Plugins may take action based on data already found in the database.

Since Contacto places minimal restraints on what may be saved as an
attribute, plugins may take advantage of acting on attributes with
specific names or values.

They may be used to maintain data, provide analysis, track upstream
sources for new data and more.

The provided ``watchdog`` plugin provides source tracking, for example.
