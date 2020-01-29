import yaml
import click
import os
import sys
from urllib.request import urlopen
from .helpers import DType, Scope, parse_valspec, attr_val_str

class Serial:
    def __init__(self, storage):
        self.storage = storage


    def export_yaml(self, file, max_scope=Scope.ATTRIBUTE, max_bin_size=0):
        data = {}
        try:
            # group scope
            for gname, group in self.storage.groups.items():
                d_group = {}
                data[gname] = d_group
                # entity scope
                if max_scope <= Scope.GROUP:
                    continue
                for ename, entity in group.entities.items():
                    d_entity = {}
                    d_group[ename] = d_entity
                    # attribute scope
                    if max_scope <= Scope.ENTITY:
                        continue
                    for aname, attribute in entity.attributes.items():
                        value = attribute.data
                        if attribute.type.is_xref():
                            value = f"REF:{value}"
                        elif (attribute.type is DType.BIN
                            and max_bin_size > 0
                            and len(value) > max_bin_size):
                            # dump data to file and reference it
                            dirp = os.path.dirname(os.path.realpath(file.name))
                            fname = os.path.join(dirp, f"{attribute.id}.dat")
                            with open(fname, 'wb') as f:
                                f.write(value)
                            value = f"FILE:{fname}"
                        d_entity[aname] = value

            yaml.safe_dump(data, file)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return False
        return True


    def dump(self, direct=False, lscope=Scope.GROUP, rscope=Scope.ATTRIBUTE):
        if rscope < Scope.ATTRIBUTE and lscope > rscope:
            lscope = rscope
        # don't output directly unless a direct scope is used
        direct &= lscope is Scope.ATTR_VAL

        scope = 0
        def prefix():
            return '' if scope == 0 else f"{(scope - 1) * '  '}- "

        for gname, group in sorted(self.storage.groups.items()):
            if lscope <= Scope.GROUP:
                click.echo(f"{prefix()}{gname}")
                if rscope == Scope.GROUP:
                    continue
                else:
                    scope += 1
            for ename, entity in sorted(group.entities.items()):
                if lscope <= Scope.ENTITY:
                    click.echo(f"{prefix()}{ename}")
                    if rscope == Scope.ENTITY:
                        continue
                    else:
                        scope += 1
                max_len = 0
                for aname in entity.attributes.keys():
                    max_len = max(max_len, len(aname))
                for aname, attr in sorted(entity.attributes.items()):
                    val = attr_val_str(attr, direct)
                    if lscope <= Scope.ATTRIBUTE:
                        pad = (max_len - len(aname)) * ' '
                        click.echo(f"{prefix()}{aname}{pad}: {val}")
                    else:
                        click.echo(val)
                if lscope <= Scope.ENTITY:
                    scope -= 1
            if lscope <= Scope.GROUP:
                scope -= 1


    def import_yaml(self, file):
        data = None
        try:
            data = yaml.safe_load(file)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return False

        try:
            with self.storage.db_conn:
                self.__import_yamldata(data)
        except Exception as e:
            # import error, reload in-memory data
            self.storage.reload()
            print(str(e), file=sys.stderr)
            return False
        return True


    def __import_yamldata(self, data):
        xref_queue = []
        for gname, d_group in data.items():
            group = self.storage.get_group(gname) or \
                    self.storage.create_group(gname)
            if d_group is None:
                continue
            for ename, d_entity in d_group.items():
                entity = self.storage.get_entity(gname, ename) or \
                         group.create_entity(ename)
                if d_entity is None:
                    continue
                for aname, d_attr in d_entity.items():
                    atype, adata = self.__parse_yaml_attr(d_attr)
                    # XREFs may not resolve yet, bypass saving them for now
                    isXREF = atype.is_xref()
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
            attr.data = self.storage.get_from_rspec(ref_data)
            attr.update()


    def __parse_yaml_attr(self, d_attr):
        if type(d_attr) is bytes:
            return DType.BIN, d_attr
        if type(d_attr) is str:
            return parse_valspec(d_attr)
        return DType.TEXT, str(d_attr)
