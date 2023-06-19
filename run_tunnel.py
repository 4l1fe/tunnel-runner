#!/usr/bin/python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass

import urwid
import tomli
from sh import ssh
from typer import Typer, Argument, Option


CMD_TCP = '-{verbose} -NL {local_address}:{local_port}:{remote_address}:{remote_port} {ssh_host}'
CMD_UNX = '-{verbose} -NL {local_sock}:{remote_sock} {ssh_host}'
cli = Typer()


@dataclass
class TUIHeaderInfo:
    local: str
    local_name: str
    remote: str
    remote_name: str


config = """
# The list of HostName in a ssh_config file.
[[ssh_hosts]]
name = "miniserver.local"
description = "Local network connection. A ssh config has to be available."

[[ssh_hosts]]
name = "miniserver.remote"
description = "Public network connection. Only a key has to be on a server."

# The list of named targets for establishing a tunnel connection
[[targets]]
name = "analytics-web"
local_address = "127.0.0.1"
local_port = 8080
remote_address = "127.0.0.1"
remote_port = 8080
description = "Analytics http server."

[[targets]]
name = "analytics-db"
local_address = "127.0.0.1"
local_port = 5432
remote_address = "172.18.0.2"
remote_port = 5432
description = "Analytics DB server."

[[targets]]
name = "monitoring-web"
local_address = "127.0.0.1"
local_port = 8180
remote_address = "127.0.0.1"
remote_port = 8180
description = "Monitoring http server."

[[targets]]
name = "dashboards-web"
local_address = "127.0.0.1"
local_port = 8380
remote_address = "127.0.0.1"
remote_port = 8380

[[targets]]
name = "docker-sock"
local_sock = "/tmp/docker.sock"
remote_sock = "/var/run/docker.sock"
description = "Docker Daemon Unix socket."

[[targets]]
name = "memo-web"
local_address = "127.0.0.1"
local_port = 8280
remote_address = "127.0.0.1"
remote_port = 8280
description = "Memo Cards http server."

[[targets]]
name = "memo-broker"
local_address = "127.0.0.1"
local_port = 6379
remote_address = "172.23.0.3"
remote_port = 6379
"""


class Autocompletion:
    """Extract name and help text from the config."""

    ARG_HOST = 'ssh-host'
    ARG_TARGET = 'target'

    def __init__(self, argument):
        config_dict = tomli.loads(config)
        if argument == self.ARG_HOST:
            self.autocomplete_records = config_dict['ssh_hosts']
        elif argument == self.ARG_TARGET:
            self.autocomplete_records = config_dict['targets']
        else:
            raise ValueError('Wrong `argument` value of autocompletion.')
            
    def do(self, incomplete: str):
        """Instead of the method __call_() as it raises
        TypeError: <__main__.Autocompletion> is not a module, class, method, or function."""

        completion = []

        for record in self.autocomplete_records:
            if record['name'].startswith(incomplete):
                help = record.get('description', '...')  # Default str for printing as a row
                completion.append((record['name'], help))

        return completion


def create_tui_loop(info: TUIHeaderInfo):

    def exit_on_q(key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    palette = [
        # structure: name, foreground, background, mono, foreground_high, background_high
        ('header', 'black', 'white'),
        ('footer', 'white', ''),
        ('prm', 'light red,bold', 'white')
    ]

    list_walker = urwid.SimpleFocusListWalker([])
    tunnel_output = urwid.ListBox(list_walker)
    tunnel_info = urwid.Text(['SSH Forward Tunnel ',
                              ('prm', info.local),
                              '[',
                              ('prm', info.local_name),
                              ']',
                              ' => ',
                              ('prm', info.remote),
                              '[',
                              ('prm', info.remote_name),
                              ']',
                              ])
    tui_help = urwid.Text('Navigation `Up`, `Down`, `PageUp`, `PageDown`, `Home`, `End`. Press `q` or `Q` to quit.',
                          wrap='clip')
    frame = urwid.Frame(header=urwid.AttrMap(tunnel_info, 'header'),
                        body=tunnel_output,
                        footer=urwid.AttrMap(tui_help, 'footer'))

    def update_body(data):
        list_walker.append(urwid.Text(data.decode().strip()))
        try:
            list_walker.set_focus(list_walker.get_next(list_walker.get_focus()[1])[1])
        except TypeError:
            pass  # First run, the empty list error

    loop = urwid.MainLoop(frame, palette, unhandled_input=exit_on_q)
    write_fd = loop.watch_pipe(update_body)

    return loop, write_fd


@cli.command()
def run(ssh_host: str = Argument(None, show_default=False, autocompletion=Autocompletion('ssh-host').do,
                                 help="A ssh_host name from the util's config. Has to be a valid HostName in an ssh config file"),
        target: str = Argument(None, show_default=False, autocompletion=Autocompletion('target').do,
                               help="A target name from the util's config"),
        verbose: str = Option('v', help='Ssh cli verbose mode. See `ssh --help`'),
        local_address: str = Option(None, show_default=False, help='Local addr to listen to.', rich_help_panel='Target parameters'),
        local_port: str = Option(None, show_default=False, help='Local port to listen to.', rich_help_panel='Target parameters'),
        remote_address: str = Option(None, show_default=False, help='Addr on a remote server to forward to.', rich_help_panel='Target parameters'),
        remote_port: str = Option(None, show_default=False, help='Port on a remote server to forward to.', rich_help_panel='Target parameters'),
        local_sock: str = Option(None, show_default=False, help='Local unix socket to listen to.', rich_help_panel='Target parameters'),
        remote_sock: str = Option(None, show_default=False, help='Unix socket on a remote server to forward to.', rich_help_panel='Target parameters')
        ):
    """Establish an SSH forward tunnel. Highlight the tunnel info.
    Track the tunnel logs. Navigate them up and down.

    First of all, a target is taken from the known
    and its default value is replaced with an according parameter if provided.\n\n

    Config pattern of the TOML format:\n
    ```\n
    [[ssh_hosts]]\n
    name = "host.name"  # A valid ssh HostName\n
    description = "Helpful description to list in autocompletion.."\n\n

    [[targets]]\n
    name = "service-foo"  # An arbitrary name of valid TOML key\n
    local_address = "127.0.0.1"\n
    local_port = 8080\n
    remote_address = "127.0.0.1"\n
    remote_port = 8080\n
    description = "Helpful description to list in autocompletion."\n
    ```
    """
     
    params = {'ssh_host': ssh_host,
              'target': target}

    config_dict = tomli.loads(config)
    for record in config_dict['targets']:
        if record['name'] == target:
            params.update(**record)
            break

    if local_address:
        params.update(local_address=local_address)
    if local_port:
        params.update(local_port=local_port)
    if remote_address:
        params.update(remote_address=remote_address)
    if remote_port:
        params.update(remote_port=remote_port)

    if local_sock:
        params.update(local_sock=local_sock)
    if remote_sock:
        params.update(remote_sock=remote_sock)

    cmd_template = CMD_TCP if target != 'dock_sock'  else CMD_UNX
    cmd = cmd_template.format(verbose=verbose, **params).split()

    tui_info = TUIHeaderInfo(local=params['local_sock']
                                   if params.get('local_sock')
                                   else f'{params["local_address"]}:{params["local_port"]}',
                             local_name=target,
                             remote=params['remote_sock']
                                    if params.get('remote_sock')
                                    else f'{params["remote_address"]}:{params["remote_port"]}',
                             remote_name=ssh_host)
    loop, tui_output = create_tui_loop(tui_info)
    cmd = ssh(*cmd, _out=tui_output, _err_to_out=True, _bg_exc=False, _bg=True)

    loop.run()
    cmd.terminate()
    cmd.wait()


if __name__ == '__main__':
    from unittest.mock import patch
    from rich.panel import Panel as _Panel
    from rich.box import SIMPLE

    class Panel(_Panel):
        """Replacer of the hardcoded Panel Box type removing border."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, box=SIMPLE, **kwargs)

    with patch('typer.rich_utils.Panel', Panel):
        cli()
