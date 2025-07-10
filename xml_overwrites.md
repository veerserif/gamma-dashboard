Practical example: look at my [Simple Ammo Stats](https://drive.google.com/file/d/1VCinRtAqE5RPiT4MGnIODid5mkUuU8un/view?usp=drive_link) mod (look at `configs/text` for how I override the descriptions of ammo)

Written example:
Let's say you have some string ID `st_mystring`, and two files with it, `st_strings.xml` and `z_st_strings.xml`.

> st_strings.xml
```xml
<string id="st_mystring">
  <text>This is my string.</text>
</string>
<string id="st_mystring_2">
  <text>This is my other string.</text>
</string>
```
> z_st_strings.xml
```xml
<string id="st_mystring">
  <text>This is altered text!</text>
</string>
```
Because `z_st_strings` comes AFTER `st_strings` if you order it alphabetically, **the game will display "This is altered text!"** when it looks for `st_mystring`. However, when the game looks for `st_mystring_2`, it will still display "This is my other string."

**What's the benefit?** 
- By using an override xml, you **don't overwrite things that you don't include**. 
  - This means that, if the file you're overriding updates and *adds new string IDs*, they will display properly instead of breaking the display. 
  - This means less chances to introduce typos, less unnecessary overwriting, and overall a "cleaner" mod.
  - This also means if the mod you overwrite, has an update, you are under way less pressure to immediately update as well.
- It's easy for you, or anyone using your mod, to clearly see which XML files your mod edits and how. This makes it IMMENSELY easier to do troubleshooting or quick fixes like hiding specific files, etc.

The problem is that you run into the z-stacking war, but _for now_, since XML direct overrides are rare (and you can "beat" all of them with DXML) it's not too much of an issue.
