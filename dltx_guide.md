## Veer's DLTX Guide
*Last updated: 2025-01-25*

This guide assumes:
- You have a BASIC understanding of the concepts of "variables", "parameters" and "values" in code
- You know what an Anomaly configuration file is (and therefore know what a section is)
- You know how to open and edit an LTX file (as in, you could literally do it in Notepad)
- You know what file structure is, as well as basic filepath notation

Additionally I assume you are modding using Mod Organizer 2. Since I primarily work on the GAMMA Modpack, I am also going to assume you care about figuring out DLTX conflicts, although everything I write here should work just fine for vanilla Anomaly.

### What you need

- **[Anomaly Modding Book - DLTX section](https://anomaly-modding-book.netlify.app/docs/tutorials/addons/dltx)** open and ready to reference, at all times
- Some sort of text editor for DLTX files. I recommend [Notepad++](https://notepad-plus-plus.org/downloads/) at a minimum
- Some way to figure out root files - the best would be using [LTXDiff](https://github.com/MerelyMezz/LTXDiff/releases/tag/1.4.2)
- Optional but recommended: unpack the Anomaly config and script files by running `Anomaly/tools/db_unpacker.bat` (pretend the `_unpacked` folder is called `gamedata` and you'll understand all of the file structures)

### I'm scared of reading (summary version)

- Figure out the root file for the LTX you are trying to change
- Within your mod folder, create a DLTX file in the format `mod_[root name]_[mod name].ltx` in the same location as the root file
- Write the contents using proper DLTX syntax
- Save it, load it, enjoy your changes.

## What is DLTX?

To drastically oversimplify: Configuration (config) files tell Anomaly what things *are* in the game - what an item is called, what properties it has, and so on. Script files tell Anomaly what to do about these properties and items. Config files always end in `.ltx`, and are fed into script files (always end in `.script`), and you can do a lot by simply editing config files without ever needing to touch a script.

DLTX is a method for allowing Anomaly modders to alter Anomaly configuration files without directly overwriting them. Anomaly stores its configs inside the `gamedata/configs` folder. Before DLTX, if modders wanted to edit configs, this would introduce all kinds of overwriting conflicts and the need to create manual merges. DLTX avoids all of this by allowing multiple modders to edit the same config files, without forcing them to overwrite each other.

Let's use an example. The Kiparis' config file, `gamedata/configs/items/weapons/w_kiparis.ltx`, has a section that looks like this:

```ini
[wpn_kiparis]
; a lot of parameters I am cutting to save space
hit_impulse                 = 20
hit_power                   = 0.46, 0.46, 0.46, 0.46
hit_type                    = fire_wound
fire_distance               = 300
bullet_speed                = 330
rpm                         = 850
```

Let us say there's some mod, Mod A, that wants to change its `rpm` (rounds-per-minute, firing speed) to 1000. And another mod, Mod B that wants to change its `hit_power` (damage, effectively) to `1.0, 1.0, 1.0, 1.0`. Without DLTX, you could not have the effects of both mod at the same time - Mod A would have one copy of `w_kiparis.ltx`, and Mod B would have its version of `w_kiparis.ltx`, and you would have to pick **one**.

However, with DLTX, you could have the effects of both mods at the same time without any extra work on your part. Mod A could use DLTX to tell the game, "only change the `rpm` value under `[wpn_kiparis]`"; Mod B could use DLTX to tell the game, "only change the `hit_power` value under `[wpn_kiparis]`". Much better for everyone involved.

## What is a root file and why is it important?

Every DLTX file must target **one** specific LTX file to edit. Sometimes this can be very simple: you want to edit the new game loadouts, the file that controls new game loadout configs is `new_game_loadouts.ltx`, so that must be your root file. Right? Well, it's not always that easy.

The way that Anomaly configs work is that they are "chained" together using `#include` chains. For example, let's look at the `configs/items/weapons/base.ltx` file:

```ini
#include "weapon_addons.ltx"
#include "weapon_silencers.ltx"
#include "weapon_scopes.ltx"
#include "weapon_sounds.ltx"
#include "weapon_ammo.ltx"
```

This tells the engine, "when you load the `base.ltx` file, include the `weapon_addons`, `weapon_silencers`, `weapon_scopes`, `weapon_sounds` and `weapon_ammo` LTX files as well". 

These chains can include wildcards. If we look a little further in the same `base.ltx` file, we will see:

```ini
;-- Weapons
#include "w_*.ltx"
```

That tells the engine, "include all LTX files in this folder that begin with `w_` and end in `.ltx`", which would cover basically all of the weapon files.

Often, the ultimate "end" of any given `#include` chain is the file that actually gets fed into the script. The config file that is actually read by the script, is our root file.

For example, if you wanted to make a DLTX file to target `w_kiparis.ltx`, the full chain of relevant LTX files looks like this:

> `w_kiparis` → `base.ltx` → `item_base.ltx` → `system.ltx`

Or if you prefer a full tree diagram:

```
gamedata/configs
├──system.ltx
├──items
|   ├──item_base.ltx
|   └──weapons
|       ├──base.ltx
|       └──w_kiparis.ltx
```

Therefore, if we wanted to make a DLTX file to change something in `w_kiparis.ltx`, our **root file** is `system.ltx`.

> **The root file is the LAST config file in the chain of `#includes`, which includes whatever config you're editing, that is actually fed into a script for the game to use.**

### How do I figure out what my root file is?
*LTXDiff section basically lifted from [the DLTX guide](https://anomaly-modding-book.netlify.app/docs/tutorials/addons/dltx/#ltxdiff-findroot).*

There's the quick way, the hard way, and the good way.

The quick way is to **look at some other DLTX mod** that changes the thing that *you* are trying to modify, and to copy its DLTX file structure and the `mod_rootname` part of its DLTX filename. So if you see some other DLTX mod that alters guns, and you notice that every single DLTX file in there is called `mod_system_something.ltx`, you can guess that your DLTX gun-mod file should also be called `mod_system_mygunmod.ltx`.

However, this can fail because modders get things wrong (gasp) and you can wind up copying a file that actually doesn't work. It could be more comical than that, you might be copying a broken file from someone who copied that broken file from someone who just didn't know it was broken at all. So it's always best to check, if possible.

The hard way is to **manually check the chain of #includes**. This is quite tricky because the names of parent LTX files aren't always obvious, and it's very possible to get lost when trying to trace them, and technically to do it properly, you also have to scour the script files to find the one that gets read into the game.

The best way to do this is to use **[LTXDiff](https://github.com/MerelyMezz/LTXDiff/releases/tag/1.4.2)**, which is why I told you to get it. It's a command-line tool that can automatically figure out the root file of any LTX file for you. In order to use it, you will need to have unpacked the Anomaly game configs and scripts.

To use it:
- Open a Powershell window in the folder where you installed LTXDiff (I put mine in `Anomaly/tools`). You can do `Shift + RMB` to get a context menu option to "Open Powershell Window Here".
- In that Powershell window, type the following then press Enter:
> `& LTXDiff findroot "[Base Folder]" "[Mod Folder]" "[Relative Path to File]"`

where:
- `[Base Folder]`: the filepath to the unpacked Anomaly folder (e.g. for me it's `G:\Anomaly/appdata/_unpacked`)
- `[Mod Folder]`: the filepath to **your mod's** folder (e.g. `G:\GAMMA\mods\whatever_your_mod_folder_is`)
- `[Relative path to file]`: the filepath to the LTX file that you are targeting, with the root file being `gamedata` (e.g. `config\items\weapons\w_kiparis.ltx` to use the Kiparis example)

Here's an example of a findroot I did for `w_kiparis.ltx`, along with its output:

> `& ".\LTXDiff" findroot "G:\Games\S.T.A.L.K.E.R. Anomaly\_unpacked" "E:\Downloads\GAMMA mods" "configs\items\weapons\w_kiparis.ltx"` <br/>
> `configs\system.ltx`

Just like I explained above, the root file for `w_kiparis.ltx` is `configs/system.ltx`. LTXDiff always assumes there's a `gamedata` folder at the root level. 

P.S. You need that first `&` to tell Powershell that you're running an executable file.

## Making your own DLTX mod

Great, now that you know all the important concepts, you can actually make your own mod. Let's make an example DLTX mod that changes the Kiparis' fire rate to 500, its cost to 42069, and makes it fit in the melee and vision slots.

First, go to your Mod Organizer 2 mods folder, then inside it make a new folder. This is where we're going to make our new mod. Give it a name, in this case we will call it `Example DLTX Mod`.

Inside this folder we need to re-create the same file structure as our root - which you will remember, is `[gamedata]/configs/system.ltx`. So our folder structure should now be:

```
Example DLTX Mod
└──gamedata
|   └──configs
|       └──mod_system_example_dltx_mod.ltx
```

Inside that `configs` folder, we make our DLTX file. 

### DLTX file naming

DLTX filenames **must always follow these rules**:

`mod_[root file name]_[mod name].ltx`

For our example mod, this means we will make `mod_system_example_DLTX_mod.ltx`. If your root file was `new_game_loadouts`, you'd be making `mod_new_game_loadouts_my_mod_name.ltx`. The number of `_` doesn't matter, what matters is the **order** of the name components, and the fact that each name component must be separated by an underscore `_`.

The mod name must be **unique**, that is, not the same as any other DLTX file.

### DLTX file contents and syntax

*The [full guide](https://anomaly-modding-book.netlify.app/docs/tutorials/addons/dltx/#4-syntax) is in the Modding Book*.

The inside of the file is relatively simple. We merely specify the section we want to edit (the part inside `[square brackets]`), then what we want to change underneath.

In order to change fire rate, cost, and "handedness", we want to change these parameters (refer to the [weapon config parameters](https://anomaly-modding-book.netlify.app/docs/references/configs/items/weapons/weapon-ammo) reference from the modding book)

* `rpm` for fire rate
* `cost` for cost
* `slot` and `single_handed` for ability to fit into melee/vision slot

Therefore, the *contents* of our DLTX file `mod_system_example_DLTX_mod.ltx` will be:

```ini
![wpn_kiparis]
rpm = 500
cost = 42069
slot = 1
single_handed = 1
```

The `!` before `[wpn_kiparis]` tells the game, "We want to edit the `[wpn_kiparis]` section". The lines afterward tell the game what parameters we want to add/change; in this case we are changing existing values rather than adding anything new.

For more details on what you can do with DLTX, including how to delete lines, or change comma-separated values (e.g. `hit_power` which comes as a list of four things, separated by `,`), **[read the full guide](https://anomaly-modding-book.netlify.app/docs/tutorials/addons/dltx/#4-syntax)**.

And that is it! Save the file, load your mod in MO2, see your changes.

## Solving DLTX Conflicts

Sometimes, different DLTX mods might wind up trying to apply the same edit to the same parameter of the same object. In this case, a  *conflict* is created: the game is being told to change a single value in two different ways. How is this resolved?

Simply put, DLTX files are loaded *alphabetically*, and the *last file loaded, wins*. What this means is that all DLTX files are fed in alphabetically, and whatever is the last - as in, comes last in the alphabet - "wins" the conflict, and its version of the change wins.

Let's say you have two mods that have a conflict, Mod A with `mod_system_kiparis_changes.ltx` and Mod B with `mod_system_change_kiparis.ltx`. If you sort these two files alphabetically, Mod A's `mod_system_kiparis_changes.ltx` comes *after* `mod_system_change_kiparis.ltx` (because K comes after C in the alphabet). Therefore, only Mod A's changes would be seen in-game.

> If your DLTX does not need to be in a specific order, you do not need to do anything extra to the name.

If your DLTX mod absolutely MUST be in a specific place in mod order, it's best to figure out what other DLTX files might be conflicting with it, and figuring out how to name your file so that it's loaded last/first/wherever it needs to go.

## DLTX FAQ

**Can you combine multiple section changes into one DLTX file?** Yes. So long as these sections all have the same root file, you can alter multiple sections in the same DLTX file. For example, since basically all weapons use the `system.ltx` root, you could add any number of gun sections to our example DLTX config.

**Should I make multiple DLTX files, even if I can put all my changes into one?** ***YES YOU SHOULD***. This keeps things clean and organized, making it easier for other people (and you) to remember which files change what aspects of the game.

**Why do I see people writing z in the filename all the time?** Because they either:

  * Want to force their DLTX to be in the bottom of the load order (and therefore win conflicts)
  * Don't actually understand how to write DLTX files and are copying filenames, not understanding that the `z` isn't what "makes it work"
  * Want to give me, veerserif, an aneurysm specifically

**How can I figure out if there are other mods that use DLTX to alter the section I'm working on?** The best way is to use something like Notepad++'s Find-in-Folder search, and search across all files for `![your_section_id]`. Remember that all DLTX sections have to start with `!`, `@` or `!!` before the section, so you can use this to find them.

**Do I have to make a new line for every single item?** Yes.

**Can I mass-change the same parameter across multiple items?** No.

### Advanced DLTX tips

* A small number of LTX files *cannot* be edited via DLTX because of the way they are loaded. One prominent example includes weather LTX files
* Technically, it is possible for a single LTX config to have more than one root, depending on the way in which it's loaded into the game (for example, it can be part of a chain of #includes that goes `your target ltx` → `config 1` → `config 2` → `root`, but the game might load both `config 1` and `root` in two separate scripts, meaning your target LTX now has two roots)
  * In this niche case, you would need to make two DLTX files, one for each root, both containing your changes


