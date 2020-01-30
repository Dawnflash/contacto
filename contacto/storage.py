import sqlite3
import pkgutil
from abc import ABC, abstractmethod
from .helpers import DType, bytes_to_attrdata, attrdata_to_bytes, validate_img
from .helpers import Scope, refspec_scope, print_error


DML_SCRIPT = 'resources/dml.sql'


class StorageElement(ABC):


    def __init__(self, parent, name):
        super().__init__()
        self.parent = parent

        if type(name) is not str or name == '':
            raise Exception("Name must be a non-empty string")
        if '/' in name:
            raise Exception("Illegal character '/' in name")
        self.name = name


    def __str__(self):
        return f"{self.parent}/{self.name}"


    @abstractmethod
    def read(self):
        pass


    @abstractmethod
    def update(self):
        pass


    @abstractmethod
    def delete(self):
        pass


    @abstractmethod
    def merge(self, other):
        pass


    def get_storage(self):
        p = self.parent
        while type(p) is not Storage:
            p = p.parent
        return p

    def get_conn(self):
        return self.get_storage().db_conn


    def update_safe(self):
        try:
            with self.get_conn():
                self.update()
                return True
        except Exception as e:
            print_error(e)
            self.read()
            return False


    def delete_safe(self):
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


    def __init__(self, gid, name, parent):
        super().__init__(parent, name)
        self.id = gid
        self.entities = {}


    def __str__(self):
        return f"{self.name}"


    def create_entity(self, name):
        cur = self.get_conn().cursor()
        sql = 'INSERT INTO entity VALUES (NULL, ?, NULL, ?)'
        cur.execute(sql, (name, self.id))
        eid = cur.lastrowid

        ent = Entity(eid, name, None, self)
        self.entities[name] = ent
        return ent


    def create_entity_safe(self, name):
        try:
            with self.get_conn():
                return self.create_entity(name)
        except Exception as e:
            print_error(e)
            return None


    def read(self):
        cur = self.get_conn().cursor()
        sql = 'SELECT name FROM "group" WHERE id=?'
        cur.execute(sql, [self.id])
        self.name = cur.fetchone()[0]


    def update(self):
        sql = 'UPDATE "group" SET name=? WHERE id=?'
        self.get_conn().execute(sql, (self.name, self.id))


    def delete(self):
        for entity in self.entities.copy().values():
            entity.delete()
        sql = 'DELETE FROM "group" WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        self.parent.groups.pop(self.name, None)


    def merge(self, other):
        for name, oentity in other.entities.copy().items():
            if name in self.entities:
                self.entities[name].merge(oentity)
            else:
                e = self.create_entity(name)
                e.merge(oentity)
        other.delete()


class Entity(StorageElement):


    def __init__(self, eid, name, thumbnail, parent):
        super().__init__(parent, name)
        self.id = eid
        self.thumbnail = thumbnail
        self.attributes = {}
        self.refs = set()


    def create_attribute(self, name, dtype, data):
        cur = self.get_conn().cursor()
        sql = 'INSERT INTO attribute VALUES (NULL, ?, ?, ?, ?)'
        bin_data = attrdata_to_bytes(dtype, data)
        cur.execute(sql, (name, dtype, bin_data, self.id))
        aid = cur.lastrowid

        attr = Attribute(aid, name, dtype, data, self)
        self.attributes[name] = attr

        attr.ref_register() # blows up if loop is detected
        if name == 'thumbnail':
            self.thumbnail_from_attr()
        return attr


    def create_attribute_safe(self, name, dtype, data):
        try:
            with self.get_conn():
                return self.create_attribute(name, dtype, data)
        except Exception as e:
            print_error(e)
            return None


    def read(self):
        cur = self.get_conn().cursor()
        sql = 'SELECT name, thumbnail FROM entity WHERE id=?'
        cur.execute(sql, [self.id])
        self.name, self.thumbnail = cur.fetchone()


    def update(self):
        sql = 'UPDATE entity SET name=?, thumbnail=? WHERE id=?'
        self.get_conn().execute(sql, (self.name, self.thumbnail, self.id))


    def delete(self):
        for attr in self.attributes.copy().values():
            attr.delete()
        sql = 'DELETE FROM entity WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        self.parent.entities.pop(self.name)
        # delete refs pointing to me
        for ref in self.refs.copy():
            ref.delete()


    def merge(self, other):
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


    def __init__(self, aid, name, dtype, data, parent):
        super().__init__(parent, name)
        self.__thumb = name == 'thumbnail'
        self.id = aid
        self.type = dtype
        self.data = data
        self.refs = set()


    """ Registers a reference to its target
    """
    def ref_register(self):
        if self.type.is_xref():
            self.__loop_detect()
            self.data.refs.add(self)


    """ Unregisters a reference to its target
    """
    def ref_unregister(self):
        if self.type.is_xref():
            self.data.refs.discard(self)


    def __thumb_hook(self):
        if self.__thumb:
            self.parent.thumbnail_from_attr()
        else:
            # propagate thumbnail update recursively
            for ref in self.refs:
                ref.__thumb_hook()


    def read(self):
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
        # check previous data for obsolete XREF registration
        t, d = self.type, self.data
        self.read() # read original data
        t, self.type = self.type, t # swap back new data
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
        sql = 'DELETE FROM attribute WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        self.parent.attributes.pop(self.name, None)
        # unregister and delete refs pointing to me
        self.ref_unregister()
        for ref in self.refs.copy():
            ref.delete()
        self.__thumb_hook()


    def merge(self, other):
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
        if self.type is DType.EXREF:
            return DType.TEXT, str(self.data)
        elif self.type is DType.AXREF:
            return self.data.get()
        return self.type, self.data


    def rotate(self):
        self.__rotate(f"{self.name}_1")


    def rotate_safe(self):
        try:
            with self.get_conn():
                self.rotate()
                return True
        except Exception as e:
            print_error(e)
            return False


    def __rotate(self, nxt_name):
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


    """Traverse reflinks recursively, detect loops
    """
    def __loop_detect(self, stop=None):
        if self.type is DType.EXREF:
            return
        elif self.type is DType.AXREF:
            if stop is self:
                raise Exception(f'REF loop detected at {self}')
            elif stop is None:
                stop = self
            self.data.__loop_detect(stop)


# manages the database
class Storage:


    def __init__(self, db_file):
        super().__init__()
        self.db_file = db_file
        # connection
        self.db_conn = sqlite3.connect(db_file)
        # executor
        self.db_cur  = self.db_conn.cursor()
        self.create_db()
        self.set_foreign_keys(True)

        # load everything from db
        self.reload()


    def __del__(self):
        self.db_conn.close()


    def set_foreign_keys(self, on):
        sql = f"PRAGMA foreign_keys = {'ON' if on else 'OFF'}"
        self.db_conn.execute(sql)


    def reload(self):
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
            attribute = Attribute(aid, name, dtype, attr_data, entities_by_id[eid])
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
        if name not in self.groups:
            return None
        return self.groups[name]


    def get_entity(self, group_name, name):
        group = self.get_group(group_name)
        if not group or name not in group.entities:
            return None
        return group.entities[name]


    def get_attribute(self, group_name, entity_name, name):
        entity = self.get_entity(group_name, entity_name)
        if not entity or name not in entity.attributes:
            return None
        return entity.attributes[name]


    def create_db(self):
        script = pkgutil.get_data(__name__, DML_SCRIPT).decode('utf-8')
        self.db_cur.executescript(script)
        self.db_conn.commit()


    def create_group(self, name):
        sql = 'INSERT INTO "group" VALUES (NULL, ?)'
        self.db_cur.execute(sql, [name])
        gid = self.db_cur.lastrowid

        group = Group(gid, name, self)
        self.groups[name] = group
        return group


    def create_group_safe(self, name):
        try:
            with self.db_conn:
                return self.create_group(name)
        except Exception as e:
            print_error(e)
            return None


    def get_from_rspec(self, p_rspec):
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
