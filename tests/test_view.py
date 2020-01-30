from helpers import mkstor, yml_fixture
from contacto.serial import Serial
from contacto.view import View
import pytest


@pytest.fixture
def view():
    stor = mkstor()
    ser = Serial(stor)
    with open(yml_fixture('test'), 'r') as f:
        assert ser.import_yaml(f)
    return View(stor)


def test_index_filters(view):
    assert view.empty()

    ifilts = 'Family', None, 'web'
    view.set_index_filters(ifilts)
    assert not view.empty()

    view.filter()
    assert 'Family' in view.groups
    assert 'Friends' not in view.groups
    grp = view.groups['Family']
    assert len(grp.entities) == 2
    for ent in grp.entities.values():
        assert 'web' in ent.attributes
        assert len(ent.attributes) == 1


def test_name_filters(view):
    nfilts = 'f', None, 'elationship'
    view.set_name_filters(nfilts)
    assert not view.empty()

    view.filter()
    assert len(view.groups) == 2 and 'Family' in view.groups
    fam = view.groups['Family']
    assert 'Mom' not in fam.entities and 'Dad' in fam.entities


def test_value_filters(view):
    view.set_attr_value_filter('Logan', True)
    assert not view.empty()

    view.filter()
    assert 'Family' in view.groups and len(view.groups) == 1
    grp = view.groups['Family']
    assert len(grp.entities) == 2

    view.reset()
    assert view.empty()
    view.set_attr_value_filter('45', False)
    view.filter()
    assert 'Family' in view.groups


def test_all(view):
    view.set_index_filters((None, None, 'relationship'))
    view.set_name_filters((None, 'B', None))
    view.set_attr_value_filter('ial', True)
    view.filter()
    assert 'Friends' in view.groups and len(view.groups) == 1
    assert 'Nappo Bappo' in view.groups['Friends'].entities
