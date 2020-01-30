import contacto.storage as storage
from contacto.helpers import DType
from helpers import mkstor, fixture
import pytest


@pytest.fixture
def stor():
    return mkstor()


def __test_storage_elem(stor, elem):
    assert elem.get_storage() is stor
    assert elem.get_conn() is stor.db_conn
    s, elem.name = elem.name, ''
    elem.read()
    assert s == elem.name


def test_group(stor):
    grp_name = 'MYGROUP'
    assert not stor.get_group(grp_name)
    grp = stor.create_group_safe(grp_name)
    assert grp and grp is stor.get_group(grp_name)
    assert grp_name in stor.groups
    assert str(grp) == grp_name
    __test_storage_elem(stor, grp)
    
    grp2_name = 'MYGROUP2'
    grp2 = stor.create_group_safe(grp2_name)
    assert stor.get_group(grp2_name)
    assert grp.merge_safe(grp2)
    assert not stor.get_group(grp2_name)


def test_entity(stor):
    gname, ename = 'MYGROUP', 'MYENTITY'
    grp = stor.create_group_safe(gname)
    ent = grp.create_entity_safe(ename)
    assert ent and ent is stor.get_entity(gname, ename)
    assert ename in grp.entities
    __test_storage_elem(stor, ent)
    
    thumb = fixture('cat.jpg').read_bytes()
    ent.thumbnail = thumb
    ent.update()

    gname2 = 'MYGROUP2'
    grp2 = stor.create_group_safe(gname2)
    ent2 = grp2.create_entity_safe(ename)
    assert grp2.merge_safe(grp)

    assert ent2.thumbnail == thumb


def test_attribute(stor):
    gn, en = 'MYGROUP', 'MYENTITY'
    adata = 'MYATTR', DType.TEXT, 'MYVALUE'
    grp = stor.create_group_safe(gn)
    ent = grp.create_entity_safe(en)
    att = ent.create_attribute_safe(*adata)
    assert att and att is stor.get_attribute(gn, en, att.name)
    __test_storage_elem(stor, att)

    # thumb test
    thumb = fixture('cat.jpg').read_bytes()
    adata2 = 'thumbnail', DType.BIN, thumb
    att2 = ent.create_attribute_safe(*adata2)
    assert att2
    assert ent.thumbnail == thumb

    # AXREF test
    adata3 = 'areference', DType.AXREF, att2
    att3 = ent.create_attribute_safe(*adata3)
    assert att3
    assert att2 is stor.elem_from_refid(att3.type, att3.data.id)

    # EXREF test
    adata4 = 'ereference', DType.EXREF, ent
    att4 = ent.create_attribute_safe(*adata4)
    assert att4
    assert ent is stor.elem_from_refid(att4.type, att4.data.id)

    # cascade thumb delete test
    assert att2.delete_safe()
    assert not stor.get_attribute(gn, en, att2.name)
    assert not stor.get_attribute(gn, en, att3.name)
    assert not ent.thumbnail

    # EXREF merge tests
    assert att.merge_safe(att4)
    assert att.type is DType.EXREF

    en2 = 'MYENTITY2'
    ent2 = grp.create_entity_safe(en2)
    assert ent2.merge_safe(ent)
    att5 = stor.get_attribute(gn, en2, att.name)
    assert att5 and att5.data == ent2


def test_storage(stor):
    names = [str(i) for i in range(50)]
    for name in names:
        assert stor.create_group_safe(name)
    stor.groups = {}
    stor.reload()
    for name in names:
        assert stor.get_group(name)
