# veyra-tv — red/black Android TV over the network

Control an Android TV from the Arch desktop with ADB. No root. The TV's dashboard stays in place;
this applies the system **dark (black)** theme, **high-contrast** text, and a **neon-red wallpaper**.

## One-time, on the TV
1. Settings → System → About → click **Android TV OS build** 7× (become a developer).
2. Settings → System → **Developer options** → turn on **USB debugging** (and **Network/Wireless
   debugging** if present).
3. Settings → Network → your Wi-Fi → note the **IP address**.

## From the Arch box
```bash
ln -sf ~/Tarot/tv/veyra-tv ~/.local/bin/veyra-tv      # once
veyra-tv connect 192.168.1.XX                          # approve "Allow debugging" on the TV
veyra-tv theme                                         # red/black + neon wallpaper
```
`veyra-tv status` checks the link, `veyra-tv restore` puts it back, `veyra-tv shell <cmd>` runs
anything on the TV.

## Later (phase 2): a truly red *dashboard*
The stock launcher can't be recolored by settings. To make the home screen itself red, install a
themeable launcher (e.g. Projectivy) as an APK and set it as home — then we theme it red/black and,
if you want, drop Veyra's chat on it. That's the "custom dashboard saved for later" step.
