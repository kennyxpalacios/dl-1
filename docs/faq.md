# faq

## what is dl-1?

a free, open-source (mit) media downloader for the mac, by palace studios. paste a link, pick mp4 or mp3, press run. it runs on your mac. no website, no account, no ads, no watermark.

## is it safe?

here is what that means: it runs on your own mac, it's open source so anyone can read the code, there are no ads, and nothing is uploaded. that's all it claims.

## what is it for?

references, a clip for the timeline, audio for an edit, your own posts and b-roll. download things you have the rights to. the sites' terms of service still apply to you.

## which sites work?

whatever yt-dlp supports, about a thousand. no promise any one site works forever. sites change. updating yt-dlp fixes most breakage.

## mp4 or mp3?

mp4 is h.264 video with aac audio. it plays everywhere and cuts in premiere, resolve and final cut. mp3 is 320 kbps with title, artist and cover art.

## why is my mp4 not 4k?

the mp4 preset picks the best h.264 video the site offers, because that plays everywhere. on youtube that tops out at 1080p. 4k there is av1 or vp9. if you want max resolution regardless of codec, one selector in `FORMATS["mp4"]` in `downloader.py` changes it. the comment next to it says what to paste.

## where do my files go?

in the mac app: `~/Downloads`. from source in a browser: your browser's downloads folder.

## macos says it can't verify the app

the app isn't signed with an apple developer id yet. open **System Settings**, **Privacy & Security**, click **Open Anyway** next to dl-1. once. steps in [setup-guide.md](setup-guide.md).

## does it work on intel macs?

yes, from source. see [from-source.md](from-source.md). the downloadable app is apple silicon only.

## do i need to install python or ffmpeg?

no. the app has both inside. from source, `bash run.sh` sets python up inside the dl-1 folder if needed, and ffmpeg is bundled.

## does it upload anything?

no. everything runs on your mac.

## can i download a whole playlist?

not right now. a playlist link downloads only the linked video.

## it says it needs a login

see [troubleshooting.md](troubleshooting.md). it needs the terminal route with `DL1_COOKIES_FROM_BROWSER`. only use your own accounts.

## how do i update it?

[check: how the mac app gets updated, and how to update yt-dlp inside it]. from source, run `.venv/bin/python -m pip install -U yt-dlp`.

## how do i remove it?

drag dl-1 from applications to the trash. from source, delete the folder.

## something broke

[open an issue](https://github.com/kennyxpalacios/dl-1/issues/new/choose) with the log line and the yt-dlp version from the top bar.
