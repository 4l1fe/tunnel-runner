#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
from pathlib import Path
from dataclasses import dataclass

import urwid
import tomli
import sh
from typer import Typer, Argument, Option


CMD_TEMPLATE = '-{verbose} -NL {local_unit}:{remote_unit} {ssh_host}'
CONFIG_FILE = Path(os.getenv('XDG_CONFIG_HOME') or os.getenv('HOME')) / '.config' / 'tunnel-runner.toml'
cli = Typer(pretty_exceptions_enable=False)


@dataclass
class TUIHeaderInfo:
    local_unit: str
    local_name: str
    remote_unit: str
    remote_name: str


class Autocompletion:
    """Extract name and help text from the config."""

    SECTION_HOSTS = 'ssh_hosts'
    SECTION_TARGETS = 'targets'

    def __init__(self, cfg_section):
        self.cfg_section = cfg_section
            
    def do(self, ctx, args, incomplete):
        """Instead of the method __call_() as it raises
        TypeError: <__main__.Autocompletion> is not a module, class, method, or function."""

        config_option = Path(ctx.params.get('config', CONFIG_FILE))
        autocomplete_records = self._extract_config_records(self.cfg_section, config_option)

        for record in autocomplete_records:
            if record['name'].startswith(incomplete):
                help = record.get('description', '')
                yield (record['name'], help)

    def _extract_config_records(self, cfg_section, config_file: Path) -> list[dict]:
        assert cfg_section in {self.SECTION_HOSTS, self.SECTION_TARGETS}, \
               'Wrong `cfg_section` value of autocompletion.'

        if not config_file.exists():
            # raise FileExistsError(config_file)
            return []
        elif not config_file.is_file():
            # TypeError('Cofig must be a toml file')
            return []
            
        with config_file.open('rb') as file:
            config_dict = tomli.load(file)

        records = config_dict[cfg_section]
        return records 


def create_tui_loop(info: TUIHeaderInfo):

    def exit_on_q(key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    palette = [
        # structure: name, foreground, background, mono, foreground_high, background_high
        ('header', 'black', 'white'),
        # ('footer', 'white', ''),
        ('footer', 'black', 'white'),
        ('prm', 'light red,bold', 'white'),
        ('out', 'light green', ''),
        ('err', 'light red', ''),
    ]

    list_walker = urwid.SimpleFocusListWalker([])
    tunnel_output = urwid.ListBox(list_walker)
    tunnel_info = urwid.Text(['SSH Forward Tunnel ',
                              ('prm', info.local_unit),
                              '[',
                              ('prm', info.local_name),
                              ']',
                              ' => ',
                              ('prm', info.remote_unit),
                              '[',
                              ('prm', info.remote_name),
                              ']',
                              ])
    tui_help = urwid.Text('Navigation `Up`, `Down`, `PageUp`, `PageDown`, `Home`, `End`. Press `q` or `Q` to quit.',
                          wrap='clip')
    frame = urwid.Frame(header=urwid.AttrMap(tunnel_info, 'header'),
                        body=tunnel_output,
                        footer=urwid.AttrMap(tui_help, 'footer'))

    def update_body(data, style):
        text = data.decode().strip()
        # list_walker.append(urwid.Text((style, text)))
        list_walker.append(urwid.Text(text))
        try:
            # list_walker.set_focus(list_walker.get_next(list_walker.get_focus()[1])[1])
            list_walker.set_focus(len(list_walker) - 1)
        except TypeError:
            pass  # First run, an empty list error

    loop = urwid.MainLoop(frame, palette, unhandled_input=exit_on_q)
    write_from_out = loop.watch_pipe(lambda data: update_body(data, 'out'))
    write_from_err = loop.watch_pipe(lambda data: update_body(data, 'err'))

    return loop, write_from_out, write_from_err


@cli.command()
def run(ssh_host: str = Argument(None, show_default=False, autocompletion=Autocompletion('ssh_hosts').do,
                                 help="A ssh_host name from the util's config. "
                                      "Has to be a valid HostName in an ssh config file"),
        target: str = Argument(None, show_default=False, autocompletion=Autocompletion('targets').do,
                               help="A target name from the util's config"),
        verbose: str = Option('v', help='Ssh cli verbose mode. See `ssh --help`'),
        local_address: str = Option(None, show_default=False, help='Local addr to listen to.',
                                    rich_help_panel='Target options to replace'),
        local_port: int = Option(None, show_default=False, help='Local port to listen to.',
                                 rich_help_panel='Target options to replace'),
        remote_address: str = Option(None, show_default=False, help='Addr on a remote server to forward to.',
                                     rich_help_panel='Target options to replace'),
        remote_port: int = Option(None, show_default=False, help='Port on a remote server to forward to.',
                                  rich_help_panel='Target options to replace'),
        local_sock: str = Option(None, show_default=False, help='Local unix socket to listen to.',
                                 rich_help_panel='Target options to replace'),
        remote_sock: str = Option(None, show_default=False, help='Unix socket on a remote server to forward to.',
                                  rich_help_panel='Target options to replace'),
        config: Path = Option(CONFIG_FILE, rich_help_panel='Config options',
        help="""The `tunnel-runner.toml` config in the `XDG_CONFIG_HOME` or `HOME/.config` dir\n
                Config pattern of the TOML format:\n
                ```\n
                [[ssh_hosts]]\n
                name = "host.name"  # A valid ssh_config `Host` value\n
                description = "Helpful description to display in an autocompletion list."\n\n

                [[targets]]\n
                name = "service-name"  # An arbitrary name of valid TOML key\n
                local_address = "127.0.0.1"\n
                local_port = 8080\n
                remote_address = "127.0.0.1"\n
                remote_port = 8080\n
                description = "Helpful description to display in an autocompletion list."\n
                ```
        """),
        ):
    """Establish an SSH forward tunnel. Highlight the tunnel info.
    Track the tunnel logs. Navigate them up and down.
    Autocomplete the arguments from a config file.

    First of all, a target is taken from the known
    and its default value is replaced with an according option if provided.
    """
     
    with config.open('rb') as file:
        config_dict = tomli.load(file)

    for cfg_params in config_dict['targets']:
        if cfg_params['name'] == target:  # Take the predefined target's params
            break

    if local_address:
        cfg_params.update(local_address=local_address)
    if local_port:
        cfg_params.update(local_port=local_port)
    if remote_address:
        cfg_params.update(remote_address=remote_address)
    if remote_port:
        cfg_params.update(remote_port=remote_port)
    if local_sock:
        cfg_params.update(local_sock=local_sock)
    if remote_sock:
        cfg_params.update(remote_sock=remote_sock)

    # Generalize TCP or Unix to a unit
    local_unit = cfg_params['local_sock'] \
                 if cfg_params.get('local_sock') \
                 else f'{cfg_params["local_address"]}:{cfg_params["local_port"]}'
    remote_unit = cfg_params['remote_sock'] \
                  if cfg_params.get('remote_sock') \
                  else f'{cfg_params["remote_address"]}:{cfg_params["remote_port"]}'

    cmd_args = CMD_TEMPLATE.format(verbose=verbose, local_unit=local_unit,
                                   remote_unit=remote_unit, ssh_host=ssh_host) \
                           .split()
    cmd_args.extend(['-o', 'StreamLocalBindUnlink=yes'])  # Make ssh run with an existent unix socket

    tui_info = TUIHeaderInfo(local_unit=local_unit,
                             local_name=target,
                             remote_unit=remote_unit,
                             remote_name=ssh_host)

    loop, write_from_out, write_from_err = create_tui_loop(tui_info)

    def interact_with_loop(line, in_queue, pipe_end):
        os.write(pipe_end, line.encode())
        # print('Line: ', line)

        if line.startswith('Are you sure you want'):
            in_queue.put('yes\n')

        # elif line.startswith('This key is not known by'):
        #     text = 'Truncated...'.encode()
        #     os.write(pipe_end, text)

    # TODO reset or a normal quit without exception `ProcessLookupError: [Errno 3] No such process`
    cmd = sh.ssh(*cmd_args,
                 _out=lambda line, in_queue: interact_with_loop(line, in_queue, write_from_out),
                 _err=lambda line, in_queue: interact_with_loop(line, in_queue, write_from_err),
                 _bg=True,
                 _bg_exc=False,
                 _tty_in=True,
                 _tty_out=True,
                 _unify_ttys=True,
                 _no_out=True,
                 _no_err=True,
                 _no_pipe=True,
                 _out_bufsize=1,
                 _err_bufsize=1,
                 _in_bufsize=1,
                 _internal_bufsize=0
    )

    loop.run()
    try:
        cmd.terminate()
        cmd.wait()
    except sh.SignalException_SIGTERM:
        pass


if __name__ == '__main__':
    from unittest.mock import patch
    from rich.panel import Panel as _Panel
    from rich.box import SIMPLE

    class Panel(_Panel):
        """Replacer of the hardcoded Panel Box type for removing a border."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, box=SIMPLE, **kwargs)

    with patch('typer.rich_utils.Panel', Panel):
        cli()
