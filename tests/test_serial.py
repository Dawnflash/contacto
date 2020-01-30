from helpers import mkstor, yml_fixture
from contacto.serial import Serial

def test_import_export():
    stor = mkstor()
    ser = Serial(stor)
    with open(yml_fixture('test'), 'r') as f:
        assert ser.import_yaml(f)
    assert stor.get_attribute('Family', 'Dad', 'age')

    with open(yml_fixture('temp'), 'w') as f:
        assert ser.export_yaml(f)
    
    # reimport our export
    stor2 = mkstor()
    ser2 = Serial(stor2)
    with open(yml_fixture('temp'), 'r') as f:
        assert ser2.import_yaml(f)
    
    for gname in stor.groups.keys():
        assert gname in stor2.groups
