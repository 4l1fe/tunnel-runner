#!/usr/bin/python3
# -*- coding: utf-8 -*-
from enum import Enum
from dataclasses import dataclass

import urwid
from sh import ssh
from typer import Typer, Argument, Option


CMD_TCP = '-{verbose} -NL {local_host}:{local_port}:{remote_host}:{remote_port} {ssh_host}'
CMD_UNX = '-{verbose} -NL {local_sock}:{remote_sock} {ssh_host}'
cli = Typer()


class TargetNameEnum(str, Enum):
    als_web = 'analytics-web'
    als_db = 'analytics-db'
    mon_web = 'monitoring-web'
    dash_web = 'dashboards-web'
    dock_sock = 'docker-sock'
    memo_web = 'memo-web'
    memo_broker = 'memo-broker'


class SSHHostEnum(str, Enum):
    local = 'miniserver.local'
    remote = 'miniserver.remote'


@dataclass
class TUIHeaderInfo:
    local: str
    local_name: str
    remote: str
    remote_name: str


TargetParams = {
    TargetNameEnum.als_web: dict(local_host='127.0.0.1',
                                 local_port=8080,
                                 remote_host='127.0.0.1',
                                 remote_port=8080),
    TargetNameEnum.als_db: dict(local_host='127.0.0.1',
                                local_port=5432,
                                remote_host='172.18.0.2',
                                remote_port=5432),
    TargetNameEnum.mon_web: dict(local_host='127.0.0.1',
                                 local_port=8180,
                                 remote_host='127.0.0.1',
                                 remote_port=8180),
    TargetNameEnum.dash_web: dict(local_host='127.0.0.1',
                                  local_port=8380,
                                  remote_host='127.0.0.1',
                                  remote_port=8380),
    TargetNameEnum.dock_sock: dict(local_sock='/tmp/docker.sock',
                                   remote_sock='/var/run/docker.sock'),
    TargetNameEnum.memo_web: dict(local_host='127.0.0.1',
                                  local_port=8280,
                                  remote_host='127.0.0.1',
                                  remote_port=8280),
    TargetNameEnum.memo_broker: dict(local_host='127.0.0.1',
                                     local_port=6379,
                                     remote_host='172.23.0.3',
                                     remote_port=6379),
}


class Autocompletion:
    """Extract name and help text from variables"""

    ARG_HOST = 'ssh-host'
    ARG_TARGET = 'target'
    HELP_TEXT = {
        SSHHostEnum.local: "Local network connection. A ssh config has to be available.",
        SSHHostEnum.remote: "Public network connection. Only a key has to be on a server.",
        TargetNameEnum.als_web: "Analytics http server.",
        TargetNameEnum.als_db: "Analytics DB server.",
        TargetNameEnum.mon_web: "Monitoring http server.",
        TargetNameEnum.dash_web: "Dashboards http server.",
        TargetNameEnum.memo_web: "Memo Cards http server.",
        TargetNameEnum.memo_broker: "Memo Cards Redis server.",
        TargetNameEnum.dock_sock: "Docker Daemon Unix socket.",
    }

    def __init__(self, argument):
        if argument == self.ARG_HOST:
            self.autocomplete_enum = SSHHostEnum
        elif argument == self.ARG_TARGET:
            self.autocomplete_enum = TargetNameEnum

    def do(self, incomplete: str):
        """Instead of the method __call_() as it raises
        TypeError: <__main__.Autocompletion> is not a module, class, method, or function."""

        completion = []

        for enum in self.autocomplete_enum:
            if enum.value.startswith(incomplete):
                help = self.HELP_TEXT[enum]
                completion.append((enum.value, help))

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
def run(ssh_host: SSHHostEnum = Argument(None, show_default=False, autocompletion=Autocompletion('ssh-host').do,
                                         help='Host name in ssh config file'),
        target: TargetNameEnum = Argument(None, show_default=False, autocompletion=Autocompletion('target').do,
                                          help="List of target names from the util's config"),
        verbose: str = Option('v', help='Ssh cli verbose mode. See `ssh --help`'),
        local_host: str = Option(None, help='Local addr to listen to.'),
        local_port: str = Option(None, help='Local port to listen to.'),
        remote_host: str = Option(None, help='Addr on a remote server to forward to.'),
        remote_port: str = Option(None, help='Port on a remote server to forward to.'),
        local_sock: str = Option(None, help='Local unix socket to listen to.'),
        remote_sock: str = Option(None, help='Unix socket on a remote server to forward to.')
        ):
    """Establish an SSH forward tunnel. Highlight the tunnel info.
    Track the tunnel logs. Navigate them up and down.

    First of all, a target is taken from the known
    and its default value is replaced with an according parameter if provided.
    """
     
    params = {'ssh_host': ssh_host,
              'target': target}
    params.update(TargetParams[target])

    if local_host:
        params.update(local_host=local_host)
    if local_port:
        params.update(local_port=local_port)
    if remote_host:
        params.update(remote_host=remote_host)
    if remote_port:
        params.update(remote_port=remote_port)

    if local_sock:
        params.update(local_sock=local_sock)
    if remote_sock:
        params.update(remote_sock=remote_sock)

    cmd_template = CMD_TCP if target != TargetNameEnum.dock_sock  else CMD_UNX
    cmd = cmd_template.format(verbose=verbose, **params).split()

    info = TUIHeaderInfo(local=params['local_sock']
                               if params.get('local_sock')
                               else f'{params["local_host"]}:{params["local_port"]}',
                         local_name=target.value,
                         remote=params['remote_sock']
                               if params.get('remote_sock')
                               else f'{params["remote_host"]}:{params["remote_port"]}',
                         remote_name=ssh_host)
    loop, write_fd = create_tui_loop(info)
    cmd = ssh(*cmd, _out=write_fd, _err_to_out=True, _bg_exc=False, _bg=True)

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
