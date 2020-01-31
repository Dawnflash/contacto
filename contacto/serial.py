"""Serialization features: import, export, human-readable dumping.
"""

import yaml
import click
import os
from urllib.request import urlopen
from .helpers import DType, Scope, parse_valspec, attr_val_str, print_error


class Serial:
    """Serialization handler, accepts a data storage.
    """
    def __init__(self, storage):
        """Constructor, save provided storage
        """
        self.storage = storage

    def export_yaml(self, file, max_scope=Scope.ATTRIBUTE, max_bin_size=0):
        """Exports storage in YAML format into a file.

        Maximum scope may be provided to cut away attributes or even entities.
        If maximum binary size is set, binary data bigger than this limit will
        be dumped into files in the dump file's directory and linked by refs.

        :param file: file to dump to
        :type  file: class:`io.TextIOWrapper`
        :param max_scope: rightmost tree scope to export
        :type  max_scope: class:`contacto.helpers.Scope`, optional
        :param max_bin_size: maximum binary data size to inline
        :type  max_bin_size: int, optional
        :return: success
        :rtype:  bool
        """
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
            print_error(e)
            return False
        return True

    def dump(self, direct=False, lscope=Scope.GROUP, rscope=Scope.ATTRIBUTE):
        """Dumps storage in a human-readable form to stdout.

        This dump type may be scoped from the left if a specific element
        is directly requested (lscope), such as with a G/E refspec.

        Right scope (rscope) cuts data from the right (starting with attrs.).
        It is possible to dump entities only (<E, E>), entities and attributes
        (<E, A>) or just attribute values (<AV, A>)...

        Passing the direct flag causes attributes to be printed without names.
        Desirable when printing a single-scoped attr's value (<AV, A>).

        :param direct: do not print attribute names
        :type  direct: bool, optional
        :param lscope: leftmost tree scope to export
        :type  lscope: class:`contacto.helpers.Scope`, optional
        :param rscope: rightmost tree scope to export
        :type  rscope: class:`contacto.helpers.Scope`, optional
        """
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
        """Imports YAML data from a file into the storage.

        :param file: YAML file
        :type  file: class:`io.TextIOWrapper`
        :return: success
        :rtype:  bool
        """
        data = None
        try:
            data = yaml.safe_load(file)
        except Exception as e:
            print_error(e)
            return False

        try:
            with self.storage.db_conn:
                self.__import_yamldata(data)
        except Exception as e:
            # import error, reload in-memory data
            self.storage.reload()
            print_error(e)
            return False
        return True

    def __import_yamldata(self, data):
        """Imports extracted (and parsed) YAML data.
        """
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
                        atype, adata = DType.TEXT, '<XREF>'  # bypass XREFs
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
        """Infers attribute value and type from YAML-parsed data.
        """
        if type(d_attr) is bytes:
            return DType.BIN, d_attr
        if type(d_attr) is str:
            return parse_valspec(d_attr)
        return DType.TEXT, str(d_attr)
