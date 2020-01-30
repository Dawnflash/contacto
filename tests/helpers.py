import os
import re
import pathlib
import atexit
from contacto.serial import Serial
from contacto.storage import Storage


def fixture(name=None):
    path = pathlib.Path(__file__).parent / 'fixtures'
    if name:
        path = path / name
    return path


def yml_fixture(name):
    return fixture(f"_{name}.yml")


def mkyaml():
    for yml in yamls:
        if not fixture(f"{yml}.yml").exists():
            continue
        ydata = fixture(f"{yml}.yml").read_text()
        ydata = ydata.replace('<FIXTURES_PATH>', str(fixture().absolute()))
        yml_fixture(yml).write_text(ydata)


def mkdb(name):
    rmdb()
    stor = Storage(str(db))
    ser = Serial(stor)
    with open(yml_fixture(name), 'r') as f:
        ser.import_yaml(f)


def rmdb():
    path = fixture(db)
    if os.path.exists(path):
        path.unlink()


def mkstor():
    return Storage(':memory:')


def cleanup():
    for yml in yamls:
        path = yml_fixture(yml)
        if os.path.exists(path):
            path.unlink()
    rmdb()


db = fixture('data.db')
yamls = [
    'test',
    'temp'
]

mkyaml()
atexit.register(cleanup)
