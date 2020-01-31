import contacto.helpers as hlp
from helpers import fixture
import pytest


def test_refspec_parse():
    with pytest.raises(Exception):
        hlp.parse_refspec('///')
        hlp.parse_refspec('/Group/Entity/Attribute')
    assert hlp.parse_refspec('Group') == ('Group', None, None)


def test_ref_parse():
    assert hlp.parse_ref('Group/Entity')[0] is hlp.DType.EXREF
    assert hlp.parse_ref('Group/Entity/Attribute')[0] is hlp.DType.AXREF
    with pytest.raises(Exception):
        hlp.parse_ref('Group')
        hlp.parse_ref('///')


def test_valspec_parse():
    fix = fixture('tinybin.dat')
    t, d =  hlp.parse_valspec(f"FILE:{fix}")
    assert t == hlp.DType.BIN and d == fix.read_bytes()
    t, d = hlp.parse_valspec(f"URL:file:{fix}")
    assert t == hlp.DType.BIN and d == fix.read_bytes()
    t, d = hlp.parse_valspec("REF:G/E/A")
    assert t == hlp.DType.AXREF and d == ('G', 'E', 'A')
    with pytest.raises(Exception):
        hlp.parse_valspec("REF:Group/Entity//")
        hlp.parse_valspec("REF:Group")
