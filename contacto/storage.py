"""The data layer containing all contact data.

Contains objects forming the contact hierarchy: Group, Entity, Attribute; and
the top-most storage container, Storage.

The contact storage is a tree, rooted at the Storage object, and branching
through Groups, Entities and Attributes.
The tree members have parent references towards the root, which wraps
around an SQLite database connection.

Storage manipulation is transactional. For all transformations a safe
variant is provided, `<transform>_safe`, which handles a single transaction.
Unsafe transformations should be wrapped in a transaction manually.
"""
import sqlite3
import pkgutil
from abc import ABC, abstractmethod
from .helpers import DType, bytes_to_attrdata, attrdata_to_bytes, validate_img
from .helpers import Scope, refspec_scope, print_error


DML_SCRIPT = 'resources/dml.sql'


class StorageElement(ABC):
    """An abstract class generalizing Groups, Entities and Attributes.

    These tree elements have scope-unique names and parent references.
    Traversal through the tree is based on names.
    """

    def __init__(self, parent, name):
        """Constructs a tree element from a name and a parent element.
        """
        super().__init__()
        self.parent = parent

        if type(name) is not str or name == '':
            raise Exception("Name must be a non-empty string")
        if '/' in name:
            raise Exception("Illegal character '/' in name")
        self.name = name

    def __str__(self):
        """String representation using scoped name (element refspec).
        """
        return f"{self.parent}/{self.name}"

    @abstractmethod
    def read(self):
        """Loads all element data from the database.
        """
        pass

    @abstractmethod
    def update(self):
        """Saves all element data to the database.

        May modify other (linked) elements.
        """
        pass

    @abstractmethod
    def delete(self):
        """Recursively deletes the subtree rooted at this element.
        """
        pass

    @abstractmethod
    def merge(self, other):
        """Merges another element of the same type into self.

        This deletes the other element and updates self.
        """
        pass

    def get_storage(self):
        """Gets the tree root using upward traversal.

        :return: tree root
        :rtype:  class:`contacto.storage.Storage`
        """
        p = self.parent
        while type(p) is not Storage:
            p = p.parent
        return p

    def get_conn(self):
        """Gets database connection from the root.

        :return: database connection
        :rtype:  class:`sqlite3.Connection`
        """
        return self.get_storage().db_conn

    def update_safe(self):
        """Single-transaction update.

        :return: success
        :rtype:  bool
        """
        try:
            with self.get_conn():
                self.update()
                return True
        except Exception as e:
            print_error(e)
            self.read()
            return False

    def delete_safe(self):
        """Single-transaction delete.

        :return: success
        :rtype:  bool
        """
        try:
            with self.get_conn():
                self.delete()
                return True
        except Exception as e:
            print_error(e)
            # in case of cascade, in-memory data may be corrupt
            self.get_storage().reload()
            return False

    def merge_safe(self, other):
        """Single-transaction merge.

        :return: success
        :rtype:  bool
        """
        try:
            with self.get_conn():
                self.merge(other)
                return True
        except Exception as e:
            print_error(e)
            # in case of cascade, in-memory data may be corrupt
            self.get_storage().reload()
            return False


class Group(StorageElement):
    """An entity group with unique name and pointer to the root storage.

    A Group hosts Entities in a name-indexed dictionary.
    """

    def __init__(self, gid, name, parent):
        """Initialize using DB id, name and parent(Storage)
        """
        super().__init__(parent, name)
        self.id = gid
        self.entities = {}

    def __str__(self):
        return f"{self.name}"

    def create_entity(self, name):
        """Creates a new Entity in this Group.

        Note that Entity names are unique in a Group.

        :param name: Entity name
        :type name:  str
        :return: created Entity
        :rtype:  class:`contacto.storage.Entity`
        """
        cur = self.get_conn().cursor()
        sql = 'INSERT INTO entity VALUES (NULL, ?, NULL, ?)'
        cur.execute(sql, (name, self.id))
        eid = cur.lastrowid

        ent = Entity(eid, name, None, self)
        self.entities[name] = ent
        return ent

    def create_entity_safe(self, name):
        """A single-transaction variant of create_entity.
        """
        try:
            with self.get_conn():
                return self.create_entity(name)
        except Exception as e:
            print_error(e)
            return None

    def read(self):
        """Reads Group from DB.
        """
        cur = self.get_conn().cursor()
        sql = 'SELECT name FROM "group" WHERE id=?'
        cur.execute(sql, [self.id])
        self.name = cur.fetchone()[0]

    def update(self):
        """Saves Group data to DB.
        """
        sql = 'UPDATE "group" SET name=? WHERE id=?'
        self.get_conn().execute(sql, (self.name, self.id))

    def delete(self):
        """Deletes Group (and its Entities) from tree and DB.
        """
        for entity in self.entities.copy().values():
            entity.delete()
        sql = 'DELETE FROM "group" WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        self.parent.groups.pop(self.name, None)

    def merge(self, other):
        """Merges another Group into self.
        """
        for name, oentity in other.entities.copy().items():
            if name in self.entities:
                self.entities[name].merge(oentity)
            else:
                e = self.create_entity(name)
                e.merge(oentity)
        other.delete()


class Entity(StorageElement):
    """The Entity tree element that carries Attributes.

    Entity hosts an Attribute dictionary, its name
    and an optional binary thumbnail (image).
    """

    def __init__(self, eid, name, thumbnail, parent):
        """Initialize using DB data and parent(Group).
        """
        super().__init__(parent, name)
        self.id = eid
        self.thumbnail = thumbnail
        self.attributes = {}
        self.refs = set()

    def create_attribute(self, name, dtype, data):
        """Creates a new Attribute for this Entity.

        Note that Attribute names are unique in an Entity.

        :param name: Attribute name
        :type  name: str
        :param dtype: data type
        :type dtype:  class:`contacto.helpers.DType`
        :return: created thumbnail
        :rtype:  class:`contacto.storage.Attribute`
        """
        cur = self.get_conn().cursor()
        sql = 'INSERT INTO attribute VALUES (NULL, ?, ?, ?, ?)'
        bin_data = attrdata_to_bytes(dtype, data)
        cur.execute(sql, (name, dtype, bin_data, self.id))
        aid = cur.lastrowid

        attr = Attribute(aid, name, dtype, data, self)
        self.attributes[name] = attr

        attr.ref_register()  # blows up if loop is detected
        if name == 'thumbnail':
            self.thumbnail_from_attr()
        return attr

    def create_attribute_safe(self, name, dtype, data):
        """A single-transaction variant of create_attribute.
        """
        try:
            with self.get_conn():
                return self.create_attribute(name, dtype, data)
        except Exception as e:
            print_error(e)
            return None

    def read(self):
        """Reads Entity data from DB.
        """
        cur = self.get_conn().cursor()
        sql = 'SELECT name, thumbnail FROM entity WHERE id=?'
        cur.execute(sql, [self.id])
        self.name, self.thumbnail = cur.fetchone()

    def update(self):
        """Saves Entity data to DB.
        """
        sql = 'UPDATE entity SET name=?, thumbnail=? WHERE id=?'
        self.get_conn().execute(sql, (self.name, self.thumbnail, self.id))

    def delete(self):
        """Deletes Entity (and its Attributes) from DB and tree.
        """
        for attr in self.attributes.copy().values():
            attr.delete()
        sql = 'DELETE FROM entity WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        self.parent.entities.pop(self.name)
        # delete refs pointing to me
        for ref in self.refs.copy():
            ref.delete()

    def merge(self, other):
        """Merges another Entity into self.
        """
        if other.thumbnail and not self.thumbnail:
            self.thumbnail = other.thumbnail
            self.update()
        # redirect all pointers to us
        for attr in other.refs.copy():
            attr.data = self
            attr.update()
        for name, oattr in other.attributes.copy().items():
            if name in self.attributes:
                self.attributes[name].merge(oattr)
            else:
                # create a dummy attribute and merge oattr into it
                attr = self.create_attribute(name, DType.TEXT, '<MERGE>')
                attr.merge(oattr)
        other.delete()

    def thumbnail_from_attr(self):
        """Sets a thumbnail from a "thumbnail" attribute.

        For convenience, a "thumbnail" attribute may carry an entity's
        thumbnail. This is a notification hook to try querying it for data.
        """
        if 'thumbnail' not in self.attributes:
            if self.thumbnail:
                self.thumbnail = None
                self.update()
            return
        thumb = self.attributes['thumbnail']
        ttype, tdata = thumb.get()
        if ttype is DType.BIN and validate_img(tdata):
            if self.thumbnail != tdata:
                self.thumbnail = tdata
                self.update()


class Attribute(StorageElement):
    """The leaf of the storage tree containing contact data.

    An Attribute has a name, data and data type.

    There are 4 types of Attribute data, listed in `contacto.helpers.DType`:
    BIN(ary), TEXT, A(ttribute) X-REF(erence) and E(ntity) X-REF(erence).

    AXREF attributes may form an oriented graph which **must not** form loops.
    Operations Create, Update and Merge are checked for loop induction.

    X-REF attributes register at their targets and are deleted when their
    target is deleted. Hence deleting an Entity or Attribute may cascade.
    These registrations are properly handled on mutations.
    """

    def __init__(self, aid, name, dtype, data, parent):
        """The constructor linking to a parent(Entity).
        """
        super().__init__(parent, name)
        self.__thumb = name == 'thumbnail'
        self.id = aid
        self.type = dtype
        self.data = data
        self.refs = set()

    def ref_register(self):
        """ Registers a reference to its target.
        """
        if self.type.is_xref():
            self.__loop_detect()
            self.data.refs.add(self)

    def ref_unregister(self):
        """ Unregisters a reference from its target.
        """
        if self.type.is_xref():
            self.data.refs.discard(self)

    def __thumb_hook(self):
        """Notifies the Entity for thumbnail update (if applicable).
        """
        if self.__thumb:
            self.parent.thumbnail_from_attr()
        else:
            # propagate thumbnail update recursively
            for ref in self.refs:
                ref.__thumb_hook()

    def read(self):
        """Updates Attribute data from the DB.
        """
        cur = self.get_conn().cursor()
        sql = 'SELECT name, type, data FROM attribute WHERE id=?'
        cur.execute(sql, [self.id])
        self.name, int_type, bin_data = cur.fetchone()
        self.type = DType(int_type)
        self.data = bytes_to_attrdata(self.type, bin_data)
        if self.type.is_xref():
            storage = self.get_storage()
            self.data = storage.elem_from_refid(self.type, self.data)

    def update(self):
        """Saves Attribute data into the DB, checked for loops.
        """
        # check previous data for obsolete XREF registration
        t, d = self.type, self.data
        self.read()  # read original data
        t, self.type = self.type, t  # swap back new data
        d, self.data = self.data, d

        sql = 'UPDATE attribute SET name=?, type=?, data=? WHERE id=?'
        bin_data = attrdata_to_bytes(self.type, self.data)
        self.get_conn().execute(sql, (self.name, self.type, bin_data, self.id))
        # unregister old ref is applicable
        if t.is_xref():
            d.refs.discard(self)
        self.ref_register()
        self.__thumb_hook()

    def delete(self):
        """Deletes Attribute from tree and DB (may cascade!)
        """
        sql = 'DELETE FROM attribute WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        self.parent.attributes.pop(self.name, None)
        # unregister and delete refs pointing to me
        self.ref_unregister()
        for ref in self.refs.copy():
            ref.delete()
        self.__thumb_hook()

    def merge(self, other):
        """Merges another Attribute into self, checked for loops.
        """
        # loop prevention
        self.ref_unregister()
        other.ref_unregister()

        # redirect all pointers to us
        for attr in other.refs.copy():
            attr.data = self
            attr.update()

        self.type = other.type
        self.data = other.data
        self.update()
        other.delete()

    def get(self):
        """Gets the actual data the Attribute references.

        For non-XREF Attributes this returns own data.
        For XREFs, the REF chain is traced to a non-REF source.
        This may be an Entity or a non-XREF Attribute.

        :return: resolved type and data
        :rtype:  (class:`contacto.helpers.DType`, Union[str, bytes])
        """
        if self.type is DType.EXREF:
            return DType.TEXT, str(self.data)
        elif self.type is DType.AXREF:
            return self.data.get()
        return self.type, self.data

    def rotate(self):
        """Rotates the attribute in a logrotate way.

        A single Attribute named "A" is copied into one named "A_1".
        If "A_1" already exists, it is copied into "A_2" and so on.
        This helps maintain an attribute value history.
        """
        self.__rotate(f"{self.name}_1")

    def rotate_safe(self):
        """A single-transaction variant of rotate.
        """
        try:
            with self.get_conn():
                self.rotate()
                return True
        except Exception as e:
            print_error(e)
            return False

    def __rotate(self, nxt_name):
        """Recursive rotate, next Attribute name is passed as accumulator.
        """
        ent = self.parent
        # recursively rotate until end of rotate-chain is found
        if nxt_name in ent.attributes:
            nxt_attr = ent.attributes[nxt_name]
            nxt_name_toks = nxt_name.split('_')
            base = '_'.join(nxt_name_toks[:-1])
            sfx = int(nxt_name_toks[-1]) + 1

            nxt_attr.__rotate(f"{base}_{sfx}")

            nxt_attr.type = self.type
            nxt_attr.data = self.data
            nxt_attr.update()
        else:
            ent.create_attribute(nxt_name, self.type, self.data)

    def __loop_detect(self, stop=None):
        """Traverses reflinks recursively and detects loops.
        """
        if self.type is DType.EXREF:
            return
        elif self.type is DType.AXREF:
            if stop is self:
                raise Exception(f'REF loop detected at {self}')
            elif stop is None:
                stop = self
            self.data.__loop_detect(stop)


class Storage:
    """The root of the storage tree and wrapper of the DB connection.

    Provides communication with an SQLite database and reads the tree from it.
    A Storage object is needed for all of Contacto's functionality.

    Access its Group children with the "groups" name-indexed dictionary.
    """

    def __init__(self, db_file):
        """Initializes the database with a path to the database.

        Optionally, provide a ":memory:" string to create DB in-memory.

        :param db_file: path to the database (or :memory:)
        :type db_file:  str
        """
        self.db_file = db_file
        # connection
        self.db_conn = sqlite3.connect(db_file)
        # executor
        self.db_cur = self.db_conn.cursor()
        self.create_db()
        self.set_foreign_keys(True)

        # load everything from db
        self.reload()

    def __del__(self):
        """Closes the DB connection on deletion.
        """
        self.db_conn.close()

    def set_foreign_keys(self, on):
        """Turns foreign keys ON or OFF.

        :param on: FK mode
        :type on:  bool
        """
        sql = f"PRAGMA foreign_keys = {'ON' if on else 'OFF'}"
        self.db_conn.execute(sql)

    def reload(self):
        """Discards any existing storage tree and reads it anew from DB.

        Constructs the entire tree including Attributes.
        """
        # NAME-indexed group dict
        self.groups = {}
        # ID-indexed helper dicts
        groups_by_id = {}
        entities_by_id = {}
        attributes_by_id = {}

        # attributes to set AXREFs on
        axref_attributes = []

        # load groups
        self.db_cur.execute('SELECT * FROM "group"')
        for gid, name in self.db_cur.fetchall():
            group = Group(gid, name, self)
            groups_by_id[gid] = group
            self.groups[name] = group

        # load entities
        self.db_cur.execute('SELECT * FROM entity')
        for eid, name, thb, gid in self.db_cur.fetchall():
            entity = Entity(eid, name, thb, groups_by_id[gid])
            entities_by_id[eid] = entity
            groups_by_id[gid].entities[name] = entity

        # load attributes
        self.db_cur.execute('SELECT * FROM attribute')
        for aid, name, dtype, data, eid in self.db_cur.fetchall():
            dtype = DType(dtype)
            attr_data = bytes_to_attrdata(dtype, data)
            ent = entities_by_id[eid]

            attribute = Attribute(aid, name, dtype, attr_data, ent)
            attributes_by_id[aid] = attribute
            entities_by_id[eid].attributes[name] = attribute

            if dtype is DType.EXREF:
                attribute.data = entities_by_id[attribute.data]
                attribute.ref_register()
            elif dtype is DType.AXREF:
                axref_attributes.append(attribute)

        # replace AXREFs using actual data
        for attribute in axref_attributes:
            attribute.data = attributes_by_id[attribute.data]
            attribute.ref_register()

    def get_group(self, name):
        """Gets a Group by its name.

        :param name: Group name
        :type name:  str
        :return: found Group or None, if one isn't found
        :rtype:  Union[class:`contacto.storage.Group`, None]
        """
        if name not in self.groups:
            return None
        return self.groups[name]

    def get_entity(self, group_name, name):
        """Gets an Entity by its name and Group name.

        :param group_name: Group name
        :type group_name:  str
        :param name: Entity name
        :type name:  str
        :return: found Entity or None, if one isn't found
        :rtype:  Union[class:`contacto.storage.Entity`, None]
        """
        group = self.get_group(group_name)
        if not group or name not in group.entities:
            return None
        return group.entities[name]

    def get_attribute(self, group_name, entity_name, name):
        """Gets an Attribute by its name and the names of its parents.

        :param group_name: Group name
        :type group_name:  str
        :param entity_name: Entity name
        :type entity_name:  str
        :param name: Attribute name
        :type name:  str
        :return: found Attribute or None, if one isn't found
        :rtype:  Union[class:`contacto.storage.Attribute`, None]
        """
        entity = self.get_entity(group_name, entity_name)
        if not entity or name not in entity.attributes:
            return None
        return entity.attributes[name]

    def create_db(self):
        """Creates DB structure using the prepared DML
        """
        script = pkgutil.get_data(__name__, DML_SCRIPT).decode('utf-8')
        self.db_cur.executescript(script)
        self.db_conn.commit()

    def create_group(self, name):
        """Creates a new Group.
        Mind that Group names are unique in a DB.

        :param name: Group name
        :type name:  str
        :return: created Group
        :rtype:  class:`contacto.storage.Group`
        """
        sql = 'INSERT INTO "group" VALUES (NULL, ?)'
        self.db_cur.execute(sql, [name])
        gid = self.db_cur.lastrowid

        group = Group(gid, name, self)
        self.groups[name] = group
        return group

    def create_group_safe(self, name):
        """A single-transaction variant of the create_group method
        """
        try:
            with self.db_conn:
                return self.create_group(name)
        except Exception as e:
            print_error(e)
            return None

    def get_from_rspec(self, p_rspec):
        """Gets a tree element from a parsed refspec.
        Parsed refspec is a triplet of None|element names scoping the tree.

        :param p_rspec: parsed refspec
        :type  p_rspec: tuple
        :return: tree element if one is found
        :rtype:  Union[None, class:`contacto.storage.StorageElement`]
        """
        scope = refspec_scope(p_rspec)
        g, e, a = p_rspec
        if scope == Scope.GROUP:
            return self.get_group(g)
        if scope == Scope.ENTITY:
            return self.get_entity(g, e)
        if scope == Scope.ATTRIBUTE:
            return self.get_attribute(g, e, a)
        return None

    def elem_from_refid(self, dtype, elem_id):
        """Returns an Entity or Attribute from its database ID.

        The type of element is decided by a DType XREF specifier.
        This method is used to find the target of a XREF from ID only.

        :param dtype: type of element (XREF spec)
        :type dtype:  class:`contacto.helpers.DType`
        :param elem_id: ID of the element
        :type elem_id:  int
        :return: tree element if one is found
        :rtype:  Union[None, class:`contacto.storage.StorageElement`]
        """
        if not dtype.is_xref():
            return None
        if dtype == DType.EXREF:
            sql = 'SELECT g.name, e.name FROM entity as e \
                   LEFT JOIN "group" as g ON (g.id=e.group_id) WHERE e.id=?'
            self.db_cur.execute(sql, [elem_id])
            return self.get_entity(*self.db_cur.fetchone())
        sql = 'SELECT g.name, e.name, a.name FROM attribute as a \
               LEFT JOIN entity as e ON (e.id=a.entity_id) \
               LEFT JOIN "group" as g ON (g.id=e.group_id) WHERE a.id=?'
        self.db_cur.execute(sql, [elem_id])
        return self.get_attribute(*self.db_cur.fetchone())
