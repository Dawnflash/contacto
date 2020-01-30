from click.testing import CliRunner
from contacto.cli import main_cmd
from helpers import fixture, db, mkdb, rmdb, yml_fixture
from os.path import exists
import pytest


@pytest.fixture
def runner():
    mkdb('test')
    return CliRunner()


@pytest.fixture
def tinybin():
    return fixture('tinybin.dat').read_bytes()


def run(runner, arg, set_db=True):
    if set_db:
        arg = f"-o {db} {arg}"
    return runner.invoke(main_cmd, arg)


def test_no_db(runner):
    rmdb()
    result = run(runner, 'get', False)
    assert result.exit_code == 2

    result = run(runner, 'get')
    assert not result.exit_code and exists(db)


def test_get(runner, tinybin):
    result = run(runner, 'get Does/Not/Exist')
    assert not result.exit_code and not result.output

    result = run(runner, 'get Main/TestEntity/Age')
    assert not result.exit_code and result.output == '25\n'

    result = run(runner, 'get //occupation')
    assert not result.exit_code and 'michelin' in result.output

    result = run(runner, 'get -s grp /Albatros/')
    assert not result.exit_code and result.output == 'Friends\n'

    result = run(runner, 'get -s ent -f fam //relationship')
    assert not result.exit_code and 'Dad' in result.output

    result = run(runner, 'get -v 25')
    assert not result.exit_code and 'TestEntity' in result.output

    result = run(runner, 'get -Vv Matthew')
    assert not result.exit_code and 'Logan' in result.output

    result = run(runner, 'get -f /dad/ -Vv logan')
    assert not result.exit_code and result.output.count('Logan') == 1

    result = run(runner, 'get Friends/Albatros/url_bin -r')
    assert not result.exit_code and result.stdout_bytes[:-1] == tinybin


def test_set(runner):
    result = run(runner, 'set -r Family/Sister/Age 18')
    assert not result.exit_code
    result = run(runner, 'get -r Family/Sister/Age')
    assert not result.exit_code and result.output == '18\n'

    result = run(runner, 'set Family/Brother/Age 18')
    assert result.exit_code and result.output.startswith('ERROR')

    catref = 'REF:Family/Dad/catpic'
    result = run(runner, f'set -R Friends/Albatros/url_bin {catref}')
    assert not result.exit_code
    result = run(runner, 'get -f Friends/Albatros/url_bin')
    assert not result.exit_code and result.output.count('BINARY') == 2

    assert run(runner, 'set //url_bin 123').exit_code == 2

    # ref tests
    result = run(runner, 'set Family/Mom/newattr REF:Family/Dad/catpic')
    assert not result.exit_code
    result = run(runner, 'set Family/Mom/catpic REF:Family/Dad/catpic')
    assert result.exit_code and 'REF loop' in result.output



def test_del(runner):
    assert not run(runner, 'del Family/Dad/web').exit_code
    assert not run(runner, 'get Family/Dad/web').output
    assert run(runner, 'del Family/Dad/web').exit_code

    assert not run(runner, 'del Family/Mom/catpic').exit_code
    assert not run(runner, 'del Family/Mom').exit_code
    assert not run(runner, 'del Family').exit_code

    mkdb('test')
    assert not run(runner, 'del Family').exit_code


def test_merge(runner):
    assert not run(runner, 'merge BareEntGrp BareGrp').exit_code
    assert run(runner, 'get BareGrp').output == 'BareEnt\n'

    assert not run(runner, 'merge Family/Mom Family/Dad').exit_code
    result = run(runner, 'get -r Family/Dad/spouse')
    assert not result.exit_code and result.output == 'Family/Dad\n'

    mkdb('test')
    result = run(runner, 'merge Family/Dad Family/Mom')
    assert result.exit_code and 'REF loop' in result.output
    assert not run(runner, 'merge Friends Family').exit_code


def test_import(runner):
    cmd = f"import {yml_fixture('test')}"

    assert not run(runner, cmd).exit_code
    assert not run(runner, 'del Family').exit_code
    assert not run(runner, cmd).exit_code

    rmdb()
    assert not run(runner, cmd).exit_code


def test_export(runner):
    tmp = yml_fixture('temp')
    assert not run(runner, f'export {tmp}').exit_code
    rmdb()
    assert not run(runner, f'import {tmp}').exit_code
    result = run(runner, 'get Family/Dad/age')
    assert not result.exit_code and result.output == '45\n'


def test_plugin_cmd(runner):
    assert not run(runner, 'plugin -l').exit_code
    result = run(runner, 'plugin')
    assert not result.exit_code and result.output.startswith('Plugin summary')
