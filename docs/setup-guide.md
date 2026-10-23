# setup guide: the mac app

this is for apple silicon macs (m1 and newer). no terminal needed. about five minutes.

not sure which mac you have? click the apple menu, then **About This Mac**. if the chip line says "apple m1" or newer, this page is for you. if it says "intel", go to [from-source.md](from-source.md).

dl-1 runs on your mac. nothing is uploaded. no account, no ads.

---

## the shortcut

if you're fine pasting one line into terminal, this does steps 1 to 3 for you and skips the macos warning entirely. open terminal (cmd + space, type terminal, press return), paste this, press return:

```bash
curl -fsSL https://raw.githubusercontent.com/kennyxpalacios/dl-1/main/install.sh | bash
```

it downloads the same dl-1-mac.zip from the releases page, puts dl-1 in applications and opens it. why no warning: macos only flags apps downloaded through a browser. the script is short, [read it](../install.sh) before you run it if you like.

rather not use terminal? the steps below take about five minutes.

---

## 1. download it

go to the [releases page](https://github.com/kennyxpalacios/dl-1/releases/latest) and download **dl-1-mac.zip**. it's about 75 mb.

> screenshot: the releases page with dl-1-mac.zip highlighted

## 2. unzip it and move it

1. open your downloads folder and double-click **dl-1-mac.zip**. a file called **dl-1** appears.
2. drag **dl-1** into your **Applications** folder.

> screenshot: dl-1 being dragged into applications

## 3. open it the first time

the first time you open dl-1, macos stops you. it says it "could not verify" the app. this is expected. the app isn't signed with an apple developer id yet, so macos asks you to confirm once.

1. try to open dl-1 from applications. when the warning shows, click **Done**.
2. open **System Settings**, then **Privacy & Security**.
3. scroll down to the line that says dl-1 was blocked.
4. click **Open Anyway**.
5. confirm. you may need your mac password or touch id.

after that it opens like any other app. you only do this once.

> screenshot: the privacy & security page with the open anyway button
> screenshot: the confirm dialog

if you'd rather use terminal for this one step: `xattr -dr com.apple.quarantine /Applications/dl-1.app`

## 4. your first download

1. dl-1 opens a window with the front panel.
2. paste a link.
3. pick **mp4** or **mp3**.
4. press run.

mp4 plays everywhere and cuts in premiere, resolve and final cut. mp3 is 320 kbps with cover art.

the finished file is saved to your **Downloads** folder.

> screenshot: the front panel with a link pasted and mp4 selected
> screenshot: the finished file in downloads

## 5. if something goes wrong

the log on the panel says why in plain words. find that line in [troubleshooting.md](troubleshooting.md).

where the app keeps its own files:

- log: `~/Library/Logs/dl-1.log`
- working files: `~/Library/Caches/dl-1/`
- your downloads: `~/Downloads`

## to remove it

drag dl-1 out of applications into the trash. optionally delete the log and cache paths above.

---

download things you have the rights to. the sites' terms of service still apply to you.
