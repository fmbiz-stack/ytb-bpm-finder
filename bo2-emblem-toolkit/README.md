# BO2 Emblem Toolkit

A tool for copying another player's Black Ops II emblem onto your own account.

You capture the emblem while looking at that player's profile, then load it into your own in-game emblem editor and save it there. From that point it's yours, the same as anything else you made in the editor.

Works with the PS4 and PS5 releases and with an original PS3, from Windows, macOS or Linux. Built for personal use, on your own console and your own home network.

## How it works

Black Ops II fetches emblem data over plain HTTP from Treyarch's old Demonware servers. This tool runs a small proxy on your computer, and you point your console's network settings at it. Only emblem-storage requests are touched:

- In capture mode, the proxy saves a copy of whatever emblem data your console downloads.
- In show mode, it replaces the emblem data your console downloads with a captured emblem of your choosing.

Everything else, including PSN sign-in and matchmaking, passes through the proxy untouched. HTTPS traffic is tunneled through as-is and is never decrypted.

Emblem requests are recognised by the shape of the request path (`/u<hex>.slot_<n>`) on a Demonware host, not by a hardcoded hostname, so it doesn't need to be told which console or which release you're on. The control panel tells you what it detected once traffic starts arriving.

## The actual steps

1. Turn on capture mode in the control panel.
2. On your console, open the profile or channel of the player whose emblem you want. Their emblem gets saved automatically.
3. In the control panel, click the captured emblem to select it.
4. Turn on show mode.
5. Open your own emblem editor. The captured emblem loads in place of whatever you'd normally see there.
6. Save it, same as you would with anything you made yourself.

Two things worth knowing before you try this:

- The game only checks for a new emblem once per session. After you open the editor the first time, it caches what it loaded and won't ask again, even if you pick a different capture afterward. To load a different one, restart the game, or switch to Zombies and back to Multiplayer, before opening the editor again.
- It won't work if the emblem uses a shape you haven't unlocked on your own account. Black Ops II checks that itself, and there's nothing the proxy can do about it.

See [docs/USAGE.md](docs/USAGE.md) for the full walkthrough, [docs/INSTALL.md](docs/INSTALL.md) for setting the tool up on your computer, and [docs/CONSOLES.md](docs/CONSOLES.md) for pointing your console at it.

## Running it

**Windows**: download `BO2EmblemToolkit.exe` from the [Releases page](https://github.com/alexkotr1/bo2-emblem-toolkit/releases) and double-click it. Nothing else to install.

**macOS**: download `BO2EmblemToolkit.app` from the same page, or run it from source with `./start.command` (double-click it in Finder). See [docs/INSTALL.md](docs/INSTALL.md) for the Gatekeeper and firewall prompts you'll get the first time.

**From source, any OS**:

```
pip install -r requirements.txt
python run.py
```

Your browser opens to the control panel on its own. There are also `start.bat` (Windows), `start.command` (macOS) and `start.sh` (Linux) if you'd rather double-click something.

## Requirements

- Prebuilt app: nothing else needed
- From source: Windows, macOS, or Linux with Python 3.9 or newer, plus Pillow (installed automatically from `requirements.txt`)
- Either way: a console and a computer on the same network, or the computer's own hotspot / Internet Sharing with the console connected to it

## Project layout

```
emblemtool/
  config.py       ports and file paths
  consoles.py     console presets and how emblem traffic is recognised
  settings.py     the console you picked, remembered between runs
  state.py        current mode: off, capture, or show
  storage.py      captured emblems on disk, and their labels
  broadcast.py    which emblem is currently selected
  proxy.py        the proxy server
  shapes/         the calibrated shape data and the emblem renderer
  web/            the control panel: API plus static frontend
run.py            starts everything
tests/            python -m unittest discover -s tests
```

Details on the emblem file format and how it was worked out are in the module docstrings, mainly `emblemtool/shapes/render.py`.

## Contributing

Issues and pull requests are welcome. There's a test suite:

```
python -m unittest discover -s tests
```

## License

MIT, see [LICENSE](LICENSE). You can use, modify, and redistribute this however you like, as long as the copyright notice stays in and alexkotr1 is credited as the original author.

## A note on scope

This only intercepts Black Ops II's own emblem-storage requests. Everything else passes through unmodified, including PSN authentication, which stays encrypted the whole time. Emblem data isn't private information, it's the same thing you already see displayed on other players in-game. This project isn't affiliated with Activision, Treyarch, or Sony.
