# Using the BO2 Emblem Toolkit

This assumes you've already finished the one-time [install](INSTALL.md), [pointed your console at the proxy](CONSOLES.md), and have the control panel open in your browser.

## The three modes

| Mode | What it does |
|---|---|
| Off | Normal internet. Nothing is captured or changed. |
| Capture | Saves the emblem of any player whose profile or channel you open. |
| Show | Loads your selected emblem into your own emblem editor. |

Only one mode runs at a time.

## Capturing an emblem

1. Click Capture.
2. On your console, open the profile or channel of the player you want to copy from.
3. Their emblem shows up under "Your captured emblems" within a few seconds. Nothing else to do.
4. A player can have more than one saved emblem. If so, each one shows up as its own card.

Click the text under a card to rename it to something you'll recognize later, like "Sam's dragon emblem," instead of the default.

## Copying an emblem onto your own account

1. Click the emblem card you want. A checkmark shows which one is selected. Only one can be selected at a time.
2. Click Show.
3. Open your own emblem editor on your console, not another player's profile. The captured emblem loads there instead of your usual saved emblem.
4. Save it from the editor, the same way you'd save anything you built yourself. It's now permanently on your account.

You can change your selection at any point, in any mode. It takes effect as soon as you're in Show mode and reopen the editor.

## Two things to know before you start

**The editor only checks the server once per game session.** The first time you open your emblem editor, Black Ops II caches whatever it loads and won't ask again after that, even if you pick a different emblem in the control panel. If you need to load a second or third emblem, you have to clear that cache first: either fully restart the game, or switch to Zombies and back to Multiplayer, then open the editor again. Just backing out of the editor and going back in isn't enough.

**It won't work if the emblem uses a shape you haven't unlocked.** Emblems are built from shapes, ranks, and weapon-qualification icons that Black Ops II normally only lets you use once you've earned them. If a captured emblem includes something your own account hasn't unlocked, the game may fail to load it, show it incorrectly, or refuse to save it. There's no way around this from the toolkit's side, since the game itself is enforcing it, not the proxy.

**Nothing is being captured at all.**
Open the "Console setup" section of the control panel. It says whether emblem
traffic is reaching the proxy, and names the endpoint and console it detected.
[docs/CONSOLES.md](CONSOLES.md#troubleshooting) walks through what each state means.

## Questions

**Do I need to keep the terminal window open?**
Yes. Closing it stops the proxy and the control panel. You can minimize it. The packaged macOS app has no terminal window — use the Quit button in the control panel to stop that one.

**Does this affect signing in or matchmaking?**
No. Only the plain-HTTP emblem-storage requests are touched. Everything else, including all HTTPS traffic like PSN sign-in, passes through unmodified and is never decrypted.

**Can I run this for more than one console?**
Yes. The proxy setting is per-console, so any number of consoles on your network can point at the same running toolkit, and they can be different models — a PS4 and a PS5 can share one toolkit and one pool of captures.

**I switched back to Off but I still see the captured emblem somewhere. Why?**
That's the console's own local cache still showing what it last loaded, not something the toolkit is still doing. Switching modes only changes what the proxy would serve on the next request, it doesn't force the console to ask again.
