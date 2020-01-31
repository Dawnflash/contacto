""" This plugin keeps attributes up to date using URLs
A) Keeping thumbnail up to date:
    Add a text attribute "thumbnail_source"
B) Keeping a binary attribute <ATTR> up to date:
    Add a text attribute "<ATTR>_source"
C) Keeping a text attribute <ATTR> up to date:
    Add a text attribute "<ATTR>_textsource"

The plugin may back up old attribute data using logrotate-like rotation
This history creates attributes like <ATTR>_1, <ATTR>_2, etc.
This feature is enabled per-attribute:
    Append an asterisk to the source attribute.
    MYATTR_source  <- history disabled
    MYATTR_source* <- history enabled
"""


import sys
from contacto.helpers import DType, print_error
from urllib.request import urlopen


binsrc_id = '_source'
txtsrc_id = '_textsource'


def plugin_init(storage):
    for entity, attrs in attr_filter(storage.groups):
        try:
            with entity.get_conn():
                for attr_data in attrs:
                    attr_process(*attr_data)
        except Exception as e:
            msg = f"Watchdog: failed processing entity {entity}\n{str(e)}"
            print_error(msg)
            return False
    return True


# yields attribute data per entity
def attr_filter(groups):
    for group in groups.values():
        for entity in group.entities.values():
            data = []
            for attribute in entity.attributes.values():
                if attribute.type is not DType.TEXT:
                    continue
                name = attribute.name
                history, text = False, False
                if name.endswith('*'):
                    name = name[:-1]
                    history = True
                if name.endswith(binsrc_id):
                    # binary source identifier
                    name = name[:-len(binsrc_id)]
                elif name.endswith(txtsrc_id):
                    # text source identifier
                    name = name[:-len(txtsrc_id)]
                    text = True
                else:
                    # not applicable
                    continue
                data.append((attribute, name, text, history))
            if len(data) > 0:
                yield entity, data


def attr_process(attribute, name, text, history):
    ent = attribute.parent
    mode = 'r' if text else 'rb'
    dtype = DType.TEXT if text else DType.BIN
    with urlopen(attribute.data, mode) as f:
        data = f.read()

    if name not in ent.attributes:
        ent.create_attribute(name, dtype, data)
        return

    attr = ent.attributes[name]
    if attr.type == dtype and attr.data == data:
        # nothing changed, do not update
        return

    if history:
        attr.rotate()
    attr.type, attr.data = dtype, data
    attr.update()
