import click


@click.group()
def main_cmd(strategy, dry_run, is_async, config_auth, config_rules):
    """Contacto CLI: manage your contacts in the console."""

    pass


@main_cmd.command(name='get')
@click.option('-s', '--scope', help='Desired output scope.',
              type=click.Choice(['attr', 'ent', 'grp']),
              default='attr', show_default=True)
@click.option('-f', '--fuzzy', help='Refspec for fuzzy element matching.')
@click.option('-v', '--value', help='Match text attributes containing value.')
@click.option('-V', 'val_exact', help='Match exact attribute value (use with -v).', is_flag=True)
@click.option('-y', '--yaml', help='Output data in YAML format.', is_flag=True)
@click.argument('refspec', required=False)
def get_cmd(scope, fuzzy, value, val_exact, yaml, refspec):
    """Fetch and print matching elements"""

    pass


@main_cmd.command(name='set')
@click.option('-r', '--recursive', help='Create elements recursively.', is_flag=True)
@click.option('-b', '--base64', help='VALUE contains base64-encoded binary data.', is_flag=True)
@click.option('-i', '--stdin', help='read VALUE from stdin.', is_flag=True)
@click.argument('refspec')
@click.argument('value', required=False)
def set_cmd(recursive, base64, stdin, refspec, value):
    """Create or update a REFSPEC-specified element.

    VALUE sets thumbnails of entities and values of attributes."""

    pass


@main_cmd.command(name='del')
@click.argument('refspec')
def del_cmd(refspec):
    """Delete a REFSPEC-specified element."""

    pass


@main_cmd.command(name='merge')
@click.argument('refspec_src')
@click.argument('refspec_dst')
def merge_cmd(refspec_src, refspec_dst):
    """Merge entity/group specified by REFSPEC_SRC into REFSPEC_DST."""

    pass


@main_cmd.command(name='import')
@click.argument('file', type=click.File('r'), required=False)
def import_cmd(file):
    """Import YAML data from FILE or stdin."""

    pass


@main_cmd.command(name='export')
@click.argument('file', type=click.File('w'), required=False)
def export_cmd(file):
    """Export YAML data to FILE or stdout. Similar to 'get -y'"""

    pass


def main():
    """CLI entrypoint, initializes the Click main command"""

    main_cmd(prog_name='contacto')
