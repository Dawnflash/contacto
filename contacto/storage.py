import sqlite3
import pkgutil
from abc import ABC, abstractmethod
from .helpers import DType, bytes_to_attrdata, attrdata_to_bytes


DML_SCRIPT = 'resources/dml.sql'


class StorageElement(ABC):


    def __init__(self, parent):
        super().__init__()
        self.parent = parent


    @abstractmethod
    def read(self):
        pass


    @abstractmethod
    def update(self):
        pass


    @abstractmethod
    def delete(self):
        pass


    def get_conn(self):
        p = self.parent
        while type(p) is not Storage:
            p = p.parent
        return p.db_conn


    def update_safe(self):
        try:
            with self.get_conn():
                return self.update()
        except sqlite3.Error:
            self.read()
            return None


    def delete_safe(self):
        try:
            with self.get_conn():
                return self.delete()
        except sqlite3.Error:
            return None


class Group(StorageElement):


    def __init__(self, gid, name, parent):
        super().__init__(parent)
        self.id = gid
        self.name = name
        self.entities = {}


    def create_entity(self, name, thumbnail=None):
        cur = self.get_conn().cursor()
        sql = 'INSERT INTO entity VALUES (NULL, ?, ?, ?)'
        cur.execute(sql, (name, thumbnail, self.id))
        eid = cur.lastrowid

        ent = Entity(eid, name, thumbnail, self)
        self.entities[name] = ent
        return ent


    def create_entity_safe(self, name, thumbnail=None):
        try:
            with self.get_conn():
                return self.create_entity(name, thumbnail)
        except sqlite3.Error:
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
        sql = 'DELETE FROM "group" WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        del self.parent.groups[self.name]


    def merge(self, other):
        for name, oentity in other.entities.items():
            if name in self.entities:
                self.entities[name].merge(oentity)
            else:
                self.create_entity(name, oentity.thumbnail)


class Entity(StorageElement):


    def __init__(self, eid, name, thumbnail, parent):
        super().__init__(parent)
        self.id = eid
        self.name = name
        self.thumbnail = thumbnail
        self.attributes = {}


    def create_attribute(self, name, dtype, data):
        cur = self.get_conn().cursor()
        sql = 'INSERT INTO attribute VALUES (NULL, ?, ?, ?, ?)'
        bin_data = attrdata_to_bytes(dtype, data)
        cur.execute(sql, (name, dtype, bin_data, self.id))
        aid = cur.lastrowid

        attr = Attribute(aid, name, dtype, data, self)
        self.attributes[name] = attr
        return attr


    def create_attribute_safe(self, name, dtype, data):
        try:
            with self.get_conn():
                return self.create_attribute(name, dtype, data)
        except sqlite3.Error:
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
        sql = 'DELETE FROM entity WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        del self.parent.entities[self.name]


    # merge other into us
    def merge(self, other):
        if other.thumbnail and not self.thumbnail:
            self.thumbnail = other.thumbnail
            self.update()
        for name, oattr in other.attributes.items():
            if name in self.attributes:
                attr = self.attributes[name]
                attr.type = oattr.type
                attr.data = oattr.data
                attr.update()
            else:
                self.create_attribute(name, oattr.type, oattr.data)
        other.delete()



class Attribute(StorageElement):


    def __init__(self, aid, name, dtype, data, parent):
        super().__init__(parent)
        self.id = aid
        self.name = name
        self.type = dtype
        self.data = data


    def read(self):
        cur = self.get_conn().cursor()
        sql = 'SELECT name, type, data FROM attribute WHERE id=?'
        cur.execute(sql, [self.id])
        self.name, int_type, bin_data = cur.fetchone()
        self.type = DType(int_type)
        self.data = bytes_to_attrdata(self.type, bin_data)


    def update(self):
        sql = 'UPDATE attribute SET name=?, type=?, data=? WHERE id=?'
        bin_data = attrdata_to_bytes(self.type, self.data)
        self.get_conn().execute(sql, (self.name, self.type, bin_data, self.id))


    def delete(self):
        sql = 'DELETE FROM attribute WHERE id=?'
        self.get_conn().execute(sql, [self.id])
        del self.parent.attributes[self.name]


    def get(self, stop=None):
        if self.type is DType.EXREF:
            return self.data.name
        elif self.type is DType.AXREF:
            if stop is self:
                apath = f"{self.parent.parent.name}/{self.parent.name}/{self.name}"
                raise Exception(f'AXREF loop detected, deleting attribute {apath}')
            elif stop is None:
                stop = self
            try:
                return self.data.get(stop)
            except Exception as e:
                self.delete()
                raise e
        return self.data


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

        # indexed by name
        self.groups = {}

        # load everything from db
        self.load_all()


    def __del__(self):
        self.db_conn.close()


    def load_all(self):
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
            elif dtype is DType.AXREF:
                axref_attributes.append(attribute)

        # replace AXREFs using actual data
        for attribute in axref_attributes:
            attribute.data = attributes_by_id[attribute.data]


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
        except sqlite3.Error:
            return None
