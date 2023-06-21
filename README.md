## Description

The smart tui for establishing an [ssh tunnel](https://www.ssh.com/academy/ssh/tunneling-example#what-is-ssh-port-forwarding,-aka-ssh-tunneling?).

Features:

- CLI autocompletion from a config.
- Highlighting tunnel addresses.
- Navigation with a keyboard.
- Resizing automatically with terminal or tmux panel size.

## Dependencies

- [typer](https://github.com/tiangolo/typer)
- [urwid](https://github.com/urwid/urwid)
- [sh](https://github.com/amoffat/sh)

## Usage

Create a config as described in the help text. Add as many sections `[[ssh_hosts]]`, `[[targets]]` as you need to autocomplete.

```
$ run_tunnel.py --help 

   Config options
  --config        PATH  The `tunnel-runner.toml` config in the XDG_CONFIG_HOME or HOME/.config dir [default: /home/vol/.config/tunnel-runner.toml]
                        Config pattern of the TOML format:
                        ```
                        [[ssh_hosts]]
                        name = "host.name"  # A valid ssh `HostName`
                        description = "Helpful description to display in an autocompletion list."

                        [[targets]]
                        name = "service-name"  # An arbitrary name of valid TOML key
                        local_address = "127.0.0.1"
                        local_port = 8080
                        remote_address = "127.0.0.1"
                        remote_port = 8080
                        description = "Helpful description to display in an autocompletion list."
```
Run using autocompletion `run_tunnel.py [TAB][TAB] [TAB][TAB]`

`$ run_tunnel.py miniserver.local docker-sock`


## Screenshots

- Running

  ![](demo-running.png)

- Autocompletion

  ![](demo-autocompletion.png)

- Resizing

  ![](demo-resizing.png)