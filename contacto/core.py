import sqlite3
import pkgutil
from .helpers import DType, bytes_to_attrdata, attrdata_to_bytes

DML_SCRIPT = 'resources/dml.sql'

class Group:
    def __init__(self, gid, name):
        self.id = gid
        self.name = name
        self.entities = {}

class Entity:
    def __init__(self, eid, name, thumbnail):
        self.id = eid
        self.name = name
        self.thumbnail = thumbnail
        self.attributes = {}

class Attribute:
    # data = bytes
    def __init__(self, aid, dtype, name, data):
        self.id = aid
        self.type = dtype
        self.name = name
        self.data = data

    def get(self):
        if self.type in (DType.EXREF, DType.AXREF):
            return self.data.data
        return self.data



# manages the database
class Core:
    def __init__(self, db_file):
        self.db_file = db_file
        # connection
        self.db_conn = sqlite3.connect(db_file)
        # executor
        self.db_cur  = self.db_conn.cursor()
        self.create_db()

        # keyed by name
        self.groups = {}

        # load everything from db
        self.load_all()
        # initialize data
        self.data_init()


    def __del__(self):
        self.db_conn.close()

    def data_init(self):
        pass

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
            group = Group(gid, name)
            groups_by_id[gid] = group
            self.groups[name] = group

        # load entities
        self.db_cur.execute('SELECT * FROM entity')
        for eid, name, thb, gid in self.db_cur.fetchall():
            entity = Entity(eid, name, thb)
            entities_by_id[eid] = entity
            groups_by_id[gid].entities[name] = entity

        # load attributes
        self.db_cur.execute('SELECT * FROM attribute')
        for aid, name, dtype, data, eid in self.db_cur.fetchall():
            dtype = DType(dtype)
            attr_data = bytes_to_attrdata(dtype, data)
            attribute = Attribute(aid, dtype, name, attr_data)
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
        if name in self.groups:
            return None

        sql = 'INSERT INTO "group" VALUES (NULL, ?)'
        self.db_cur.execute(sql, [name])
        gid = self.db_cur.lastrowid
        self.db_conn.commit()

        group = Group(gid, name)
        self.groups[name] = group
        return group

    def create_entity(self, group, name, thumbnail=None):
        if not group or name in group.entities:
            return None

        sql = 'INSERT INTO entity VALUES (NULL, ?, ?, ?)'
        self.db_cur.execute(sql, (name, thumbnail, group.id))
        eid = self.db_cur.lastrowid
        self.db_conn.commit()

        entity = Entity(eid, name, thumbnail)
        group.entities[name] = entity
        return entity

    def create_attribute(self, entity, name, dtype, data):
        if not entity or name in entity.attributes:
            return None

        sql = 'INSERT INTO attribute VALUES (NULL, ?, ?, ?, ?)'
        bin_data = attrdata_to_bytes(dtype, data)
        self.db_cur.execute(sql, (name, dtype, bin_data, entity.id))
        aid = self.db_cur.lastrowid
        self.db_conn.commit()

        attribute = Attribute(aid, dtype, name, data)
        entity.attributes[name] = attribute
        return attribute
