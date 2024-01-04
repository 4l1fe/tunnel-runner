## Description

The smart TUI for establishing an [ssh tunnel](https://www.ssh.com/academy/ssh/tunneling-example#what-is-ssh-port-forwarding,-aka-ssh-tunneling?).

Features:

- CLI autocompletion from a config.
- Highlighting tunnel addresses.
- Navigation with a keyboard.
- Resizing automatically with terminal or tmux panel size.

## Dependencies

- [typer](https://github.com/tiangolo/typer)
- [urwid](https://github.com/urwid/urwid)
- [sh](https://github.com/amoffat/sh)
- [dynaconf](https://github.com/dynaconf/dynaconf)

## Usage

Create a config as described in the help text. Add as many sections `[ssh_hosts]`, `[targets]` as you need to autocomplete.

```
$ run_tunnel.py --help 

   Config options
  --config        PATH  The `tunnel-runner.toml` config in the `XDG_CONFIG_HOME` or `HOME/.config` dir
                        Config pattern of the TOML format:
                    ```
                    [ssh_hosts."host.name"]  # A valid ssh_config `Host` value prefixed with `ssh_hosts`
                    description = "Helpful description to display in an autocompletion list."
    
                    [targets.service-name]  # An arbitrary name of valid TOML key prefixed with `targets`
                    local_address = "127.0.0.1"
                    local_port = 8080
                    remote_address = "127.0.0.1"
                    remote_port = 8080
                    description = "Helpful description to display in an autocompletion list."
                    
                    
                    [default: /home/user/.config/tunnel-runner.toml]
```


Run using autocompletion `run_tunnel.py [TAB][TAB] [TAB][TAB]`

`$ run_tunnel.py miniserver.local docker-sock`


## Screenshots

- Running

  ![](demo-running.png)

- Autocompletion

  ![](autocomplete-host.gif)

  ![](autocomplete-target.gif)

- Resizing

  ![](demo-resizing.png)
