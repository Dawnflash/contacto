import yaml
import os
import sys
from urllib.request import urlopen
from .helpers import DType

class Serial:
    def __init__(self, storage):
        self.storage = storage
        self.__ref_delims = '/#*|[@_!$%^&()<>?}{~:]'

    def export_yaml(self, filename, max_bin_size=0):
        data = {}
        try:
            for gname, group in self.storage.groups.items():
                d_group = {}
                data[gname] = d_group
                for ename, entity in group.entities.items():
                    d_entity = {}
                    if entity.thumbnail is not None:
                        d_entity['thumbnail'] = entity.thumbnail
                    d_group[ename] = d_entity
                    for aname, attribute in entity.attributes.items():
                        value = attribute.data
                        if attribute.type is DType.EXREF:
                            path = (value.parent.name, value.name)
                            value = self.__xref_serialize(path)
                        elif attribute.type is DType.AXREF:
                            ent = value.parent
                            path = (ent.parent.name, ent.name, value.name)
                            value = self.__xref_serialize(path)
                        elif (attribute.type is DType.BIN
                            and max_bin_size > 0
                            and len(value) > max_bin_size):
                            # dump data do file and reference it
                            dirp = os.path.dirname(filename)
                            fname = os.path.join(dirp, aname.replace(' ', '_'))
                            with open(fname, 'wb') as f:
                                f.write(value)
                            value = f"FILE:{fname}"

                        d_entity[aname] = value
            with open(filename, 'w') as f:
                yaml.safe_dump(data, f)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return False
        return True


    def import_yaml(self, filename):
        data = None
        try:
            with open(filename, 'r') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return False

        try:
            with self.storage.db_conn:
                return self.__import_yamldata(data)
        except Exception as e:
            # import error, reload in-memory data
            self.storage.groups = {}
            self.storage.load_all()
            print(str(e), file=sys.stderr)
            return False
        return True


    def __import_yamldata(self, data):
        xref_queue = []
        for gname, d_group in data.items():
            group = self.storage.get_group(gname) or \
                    self.storage.create_group(gname)
            for ename, d_entity in d_group.items():
                entity = self.storage.get_entity(gname, ename) or \
                         group.create_entity(ename)
                for aname, d_attr in d_entity.items():
                    atype, adata = self.__parse_yaml_attr(d_attr)
                    if aname == 'thumbnail':
                        # set thumbnail (must be a binary value)
                        if atype is DType.BIN:
                            entity.thumbnail = adata
                            entity.update()
                            continue
                    # XREFs may not resolve yet, bypass saving them for now
                    isXREF = atype is DType.EXREF or atype is DType.AXREF
                    if isXREF:
                        ref_meta = atype, adata
                        atype, adata = DType.TEXT, '<XREF>' # bypass XREFs
                    attr = self.storage.get_attribute(gname, ename, aname)
                    if attr is None:
                        attr = entity.create_attribute(aname, atype, adata)
                    else:
                        attr.name, attr.type, attr.data = aname, atype, adata
                        attr.update()
                    # queue XREFs for proper processing
                    if isXREF:
                        xref_queue.append((*ref_meta, attr))
        # process XREFs
        for ref_type, ref_data, attr in xref_queue:
            attr.type = ref_type
            if ref_type is DType.EXREF:
                attr.data = self.storage.get_entity(*ref_data)
            else: # AXREF
                attr.data = self.storage.get_attribute(*ref_data)
            attr.update()


    def __parse_yaml_attr(self, d_attr):
        if type(d_attr) is bytes:
            return DType.BIN, d_attr
        if type(d_attr) is str:
            if d_attr.startswith('FILE:'):
                fname = d_attr.split('FILE:')[1]
                with open(fname, 'rb') as f:
                    return DType.BIN, f.read()
            if d_attr.startswith('URL:'):
                url = d_attr.split('URL:')[1]
                with urlopen(url) as f:
                    return DType.BIN, f.read()
            if d_attr.startswith('REF:'):
                # split references by the first character
                sref = d_attr.split('REF:')[1]
                lref = sref[1:].split(sref[0])
                if len(lref) == 2:
                    return DType.EXREF, lref
                if len(lref) == 3:
                    return DType.AXREF, lref
                raise Exception('Bad XREF signature')
        return DType.TEXT, str(d_attr)


    def __xref_serialize(self, tokens):
        for c in self.__ref_delims:
            present = False
            for tok in tokens:
                if c in tok:
                    present = True
                    break
            if not present:
                return f"REF:{c}{c.join(tokens)}"
        raise Exception('Unable to serialize XREF')
