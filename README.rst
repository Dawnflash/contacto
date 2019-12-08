Contacto
########

A robust contact manager written in Python.
Manage a contact list and keep it synced across service providers.
The tool helps one link virtual identities to real-world entities and describe relationships between them.

Proposed feature set
--------------------

* fully per-entity configurable contact properties (text, xref or binary)
* CRUD data model + search over properties
* SQLite-backed data storage
* import configuration from YAML
* CLI interface
* GUI read-only interface (RW-enabled GUI is a possible extension)
* Plugin support to enable interaction with custom services

Contact property types
----------------------

* text value ("my_email@my_domain.tld", "+420123456789")
* binary value (JPEG, DER)
* property xref (thumbnail -> image_123, name -> twitter_handle)
* entity xref (father -> ent_ID=32)

Example entity model (twitter identity known)
---------------------------------------------

* name -> prop_xref:"twitter_handle"
* avatar -> prop_xref:"twitter_avatar"
* twitter_handle -> text:"johndoe123"
* twitter_avatar -> data:"<JPEG>"
* twitter\_* (other twitter fields)
* known_associate -> ent_xref:27

Plugin model
------------

Plugins must be registered and implement a proposed API.
They shall be used to bring in more data from external sources and for keeping contacts up to date.

Proposed plugin API
^^^^^^^^^^^^^^^^^^^

A plugin returns entities from a source.
The entities have plugin-defined properties (eg. avatar, handle, email).
These properties get prefixed by the plugin name before saving ("twitter_handle").

* get_entities(filter={}) : list - obtain entities whose properties match a filter
* get_default_properties(): dict - get properties corresponding to name, avatar, etc ({name: 'handle'})

Functionality
-------------

1. Basic display
    Avatar and display name implementation possible via property xrefs and well-known property names (name, avatar).
    The remaining properties may be printed (in text form) and exported to files (binary form).

2. Creating entities
    a) YAML import file containing references to binary files if needed
    b) Plugin import
    c) manual via CLI (later possibly via GUI)

3. Updating entities
    Assign or remove properties of entities specified by property values or ID.
    Two identical entities with different IDs are thus possible.

    a) YAML diff file (filter: name='xyz', set: email='xyz@abc.tld')
    b) Plugin update: requires plugin index (eg. index = handle for twitter plugin) to ID entities
    c) manual via CLI, later possibly via GUI

    Use case: import Twitter data based on obtained handle:
    
    1. CLI: set twitter_handle='myhandle' to contact ID 52
    2. Plugin update: get_entities({ID=52}) -> uses index "twitter_handle" to update Twitter properties

4. Deleting entities
    Via CLI or GUI

5. Merging entities
    Creating entities always spawns new entities, a merge mechanism is necessary.

    a) Explicit merge: eg. YAML, CLI: merge ID=24 with ID=78, later also possible via GUI
    b) Automerge: find merge candidates based on identical properties or identical values across selected properties.
        Automerge could also accept check constraints (only merge with ID=50 or higher, only merge with label "Twitter" etc.)
        
        **Important**: automerge wouldn't commit directly but instead export proposed changes to YAML or query user for each change via CLI

        Examples:
            i) merge on (email, \*_email), (name, \*_handle)
            ii) merge on [] => only merge on identical property names and values
