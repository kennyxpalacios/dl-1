# troubleshooting

find the line you see in the log on the panel. each heading is that line, as dl-1 prints it.

before anything else: the number one fix is an out-of-date yt-dlp. the version is printed in the top bar. in the mac app, yt-dlp comes built in, so the fix arrives with a new dl-1 release: download it from the [releases page](https://github.com/kennyxpalacios/dl-1/releases/latest) and replace the app. from source, see [from-source.md](from-source.md).

if your line isn't here, [open an issue](https://github.com/kennyxpalacios/dl-1/issues/new/choose) with the log line and the yt-dlp version from the top bar.

---

## macos won't open the app

not a dl-1 line, but the first thing most people hit. macos says it "could not verify" dl-1. open **System Settings**, **Privacy & Security**, scroll to the line about dl-1, click **Open Anyway**, confirm. details in [setup-guide.md](setup-guide.md).

## this one needs a login. set DL1_COOKIES_FROM_BROWSER=chrome (see readme) and retry.

the site wants you to be signed in. dl-1 can borrow your browser's login. this needs the terminal route:

```bash
DL1_COOKIES_FROM_BROWSER=chrome bash run.sh
```

use the browser you're signed in with: `chrome`, `firefox`, `safari`, `brave` or `edge`. macos may ask chrome for keychain access the first time. safari needs full disk access for terminal. only use your own accounts.

the mac app you open from the dock can't take browser cookies in v1.0. for login-only content, run dl-1 from source with the line above. see [from-source.md](from-source.md).

## age-restricted — needs a logged-in session. set DL1_COOKIES_FROM_BROWSER (see readme).

same fix as above.

## the site wants proof you're not a bot. wait a minute and retry, or pass browser cookies (see readme).

the site is rate-limiting you. wait a minute and try again. if it keeps happening, use the cookies fix above.

## this video is private. the owner has to make it public or unlisted.

dl-1 can't open private videos. if it's yours, change its visibility and try again.

## unavailable — removed, region-locked, or the link is wrong.

check the link opens in your browser. if it does, the video may be blocked in your region.

## no downloadable formats found for this link.

the site gave dl-1 nothing to download. update yt-dlp first. if it still fails, open an issue.

## unsupported url. yt-dlp doesn't know how to read this one.

dl-1 only reads sites yt-dlp supports, about a thousand of them. no promise every site works, or keeps working. check the link points at a video page, not a homepage.

## that's not a valid url.

paste the full link, starting with https://

## nothing at that url (404).

the link is wrong or the page is gone.

## the site refused the request (403). retry, or pass browser cookies.

retry once. then try the cookies fix.

## rate-limited (429). give it a few minutes.

too many requests. wait a few minutes.

## network error — can't reach the site.

check your internet connection and try again.

## ffmpeg is missing — needed for mp3 + merged video. see readme.

the mac app has ffmpeg inside, so this shouldn't show up there. if you run from source and removed `imageio-ffmpeg`, either reinstall requirements (`bash run.sh --reset`) or install ffmpeg and set `DL1_FFMPEG` to its path.

## finished, but no output file was produced. check the log above.

the download ran but nothing came out. read the lines above it in the log, they usually say why. open an issue with them.

## codec check lines (not errors)

- `codec check // ... plays everywhere`: the video was already h.264 + aac. nothing to do.
- `re-encoding to h.264`: the site served a format quicktime and most editors can't play, so dl-1 converts it. this takes longer on long videos.
- `re-encode failed ... keeping the original file`: the original is kept. it may not play in quicktime.
- `a post-processing step failed ... keeping the file anyway`: usually cover art on an mp3. the file is fine.

## youtube warnings about javascript

youtube wants a javascript runtime to unlock all its formats. dl-1 looks for `deno`, `node` or `bun`. without one, youtube still works but may show fewer formats. fix: install [deno](https://deno.com) and restart dl-1.

## a playlist link only gave me one video

on purpose. a playlist link downloads just the linked video.

## my file disappeared

files are kept on the server for two hours after they finish, then swept. save from the browser. in the mac app, files go to `~/Downloads`.

---

download things you have the rights to. the sites' terms of service still apply to you.
