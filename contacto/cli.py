"""CLI interface using Click.
"""

import click
import sys
from .storage import Storage
from .helpers import parse_refspec, parse_valspec
from .helpers import DType, Scope, dump_lscope, refspec_scope
from .helpers import print_warning, print_error, get_plugins, run_plugins
from .view import View
from .serial import Serial


def group_set(storage, gname):
    """Creates or update a group.

    :param storage: used storage
    :type  storage: class:`contacto.storage.Storage`
    :param gname: group name
    :type  gname: str
    :return: created group
    :rtype:  class:`contacto.storage.Group`
    """
    return storage.get_group(gname) or \
        storage.create_group_safe(gname) or sys.exit(1)


def entity_set(storage, gname, ename, recursive):
    """Creates or update an entity.

    :param storage: used storage
    :type  storage: class:`contacto.storage.Storage`
    :param gname: group name
    :type  gname: str
    :param ename: entity name
    :type  ename: str
    :param recursive: create group if non-existent
    :type  recursive: bool
    :return: created entity
    :rtype:  class:`contacto.storage.Entity`
    """
    ent = storage.get_entity(gname, ename)
    if ent:
        return ent
    if recursive:
        grp = group_set(storage, gname)
    else:
        grp = storage.get_group(gname)
        if not grp:
            print_error(f"Group {gname} does not exist.")
            sys.exit(1)
    return grp.create_entity_safe(ename) or sys.exit(1)


def validate_refspec(ctx, param, value):
    """Validates a generic refspec (without restrictions).

    :param ctx: Click context
    :type  ctx: class:`click.Context`
    :param param: Click params
    :type  param: dict
    :param value: refspec
    :type  value: str
    :return: parsed refspec
    :rtype:  list
    """
    try:
        return parse_refspec(value)
    except Exception as e:
        raise click.BadParameter(str(e))


def validate_full_refspec(ctx, param, value):
    """Validates a full refspec (specified from the left).

    :param ctx: Click context
    :type  ctx: class:`click.Context`
    :param param: Click params
    :type  param: dict
    :param value: refspec
    :type  value: str
    :return: parsed refspec
    :rtype:  list
    """
    p_rspec = validate_refspec(ctx, param, value)
    if refspec_scope(p_rspec):
        return p_rspec
    raise click.BadParameter('Fully-specified refspec required')


@click.group()
@click.option('-o', '--open', 'dbname', type=click.Path(exists=False),
              required=True, help='Path to storage file')
@click.pass_context
def main_cmd(ctx, dbname):
    """Contacto CLI: manage your contacts in the console."""

    ctx.ensure_object(dict)
    ctx.obj['storage'] = Storage(dbname)


@main_cmd.command(name='get')
@click.option('-s', '--scope', help='Desired output scope.',
              type=click.Choice(['attr', 'ent', 'grp']),
              default='attr', show_default=True)
@click.option('-f', '--fuzzy', callback=validate_refspec,
              help='Refspec for fuzzy element matching.')
@click.option('-v', '--value', help='Match attributes by value TEXT.')
@click.option('-V', 'val_fuzzy', is_flag=True,
              help='Fuzzy match attributes by value (use with -v).')
@click.option('-r', '--raw', is_flag=True,
              help='Dump raw data. Full REFSPEC must be given.')
@click.option('-y', '--yaml', help='Output data in YAML format.', is_flag=True)
@click.argument('refspec', callback=validate_refspec, required=False)
@click.pass_context
def get_cmd(ctx, scope, fuzzy, value, val_fuzzy, raw, yaml, refspec):
    """Fetch and print matching elements"""

    scope = Scope.from_str(scope)
    if val_fuzzy and not value:
        print_warning('-V must be used with -v')

    view = View(ctx.obj['storage'])
    view.set_index_filters(refspec)
    view.set_name_filters(fuzzy)
    view.set_attr_value_filter(value, val_fuzzy)
    view.filter()

    serial = Serial(view)
    if yaml:
        serial.export_yaml(sys.stdout, max_scope=scope)
    else:
        serial.dump(raw, dump_lscope(refspec), scope)


@main_cmd.command(name='set')
@click.option('-r', '--recursive',
              help='Create elements recursively.', is_flag=True)
@click.option('-b', '--binary',
              help='Read binary data (use with -i).', is_flag=True)
@click.option('-i', '--stdin', help='Read VALUE from stdin.', is_flag=True)
@click.option('-R', '--rotate', help='Rotate attribute value.', is_flag=True)
@click.argument('refspec', callback=validate_full_refspec)
@click.argument('value', required=False)
@click.pass_context
def set_cmd(ctx, recursive, binary, stdin, rotate, refspec, value):
    """Create or update a REFSPEC-specified element.

    VALUE sets thumbnails of entities and values of attributes."""

    if binary and not stdin:
        print_warning('Warning: -b must be used with -i')

    stor = ctx.obj['storage']
    if not stdin:
        try:
            vtype, vdata = parse_valspec(value)
        except Exception as e:
            print_error(e)
            sys.exit(1)
        if vtype and vtype.is_xref():
            vdata = stor.get_from_rspec(vdata)
            if not vdata:
                print_error("Invalid reference")
                sys.exit(1)
    elif not binary:
        vtype, vdata = DType.TEXT, sys.stdin.read()
    else:
        vtype, vdata = DType.BIN, sys.stdin.buffer.read()

    scope = refspec_scope(refspec)
    if scope == Scope.GROUP:
        group_set(stor, refspec[0])
    if scope == Scope.ENTITY:
        entity_set(stor, *refspec[:2], recursive)
    if scope == Scope.ATTRIBUTE:
        if not vtype:
            print_error(f'Attributes require supplied value.')
            sys.exit(1)
        attr = stor.get_attribute(*refspec)
        if attr:
            if vtype == attr.type or vdata == attr.data:
                return
            if rotate:
                attr.rotate_safe() or sys.exit(1)
            attr.type, attr.data = vtype, vdata
            attr.update_safe() or sys.exit(1)
            return
        entp = refspec[:2]
        if recursive:
            ent = entity_set(stor, *entp, recursive)
        else:
            ent = stor.get_entity(*entp)
            if not ent:
                print_error(f"Entity {'/'.join(entp)} does not exist.")
                sys.exit(1)
        ent.create_attribute_safe(refspec[2], vtype, vdata) or sys.exit(1)


@main_cmd.command(name='del')
@click.argument('refspec', callback=validate_full_refspec)
@click.pass_context
def del_cmd(ctx, refspec):
    """Delete a REFSPEC-specified element."""

    stor = ctx.obj['storage']
    elem = stor.get_from_rspec(refspec) or sys.exit(1)
    elem.delete_safe() or sys.exit(1)


@main_cmd.command(name='merge')
@click.argument('refspec_src', callback=validate_full_refspec)
@click.argument('refspec_dst', callback=validate_full_refspec)
@click.pass_context
def merge_cmd(ctx, refspec_src, refspec_dst):
    """Merge entity/group specified by REFSPEC_SRC into REFSPEC_DST."""

    stor = ctx.obj['storage']
    src = stor.get_from_rspec(refspec_src) or sys.exit(1)
    dst = stor.get_from_rspec(refspec_dst) or sys.exit(1)

    if type(src) != type(dst) or not hasattr(src, 'merge'):
        print_error('You can only merge 2 entities or 2 groups.')
        sys.exit(1)
    dst.merge_safe(src) or sys.exit(1)


@main_cmd.command(name='import')
@click.argument('file', type=click.File('r'), required=False)
@click.pass_context
def import_cmd(ctx, file):
    """Import YAML data from FILE or stdin."""

    serial = Serial(ctx.obj['storage'])
    serial.import_yaml(file or sys.stdin) or sys.exit(1)


@main_cmd.command(name='export')
@click.argument('file', type=click.File('w'), required=False)
@click.pass_context
def export_cmd(ctx, file):
    """Export YAML data to FILE or stdout. Similar to 'get -y'"""

    serial = Serial(ctx.obj['storage'])
    serial.export_yaml(file or sys.stdout) or sys.exit(1)


@main_cmd.command(name='plugin')
@click.option('-l', '--list', help='List available plugins', is_flag=True)
@click.argument('whitelist', nargs=-1)
@click.pass_context
def plugin_cmd(ctx, list, whitelist):
    """Run Contacto plugins, optionally specify which by name"""

    if list:
        click.echo(', '.join(get_plugins().keys()))
        return

    ok, nok = run_plugins(ctx.obj['storage'], whitelist)
    s_ok = '' if len(ok) == 0 else f" ({', '.join(ok)})"
    s_nok = '' if len(nok) == 0 else f" ({', '.join(nok)})"

    click.echo(f"Plugin summary: {len(ok)} successful{s_ok}, \
               {len(nok)} failed{s_nok}.")
    if len(nok) > 0:
        sys.exit(1)


def main():
    """CLI entrypoint, initializes the Click main command"""

    main_cmd(prog_name='contacto')
