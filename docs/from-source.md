# from source: intel macs and the terminal

for intel macs, or anyone who likes the terminal. the apple silicon app is easier: see [setup-guide.md](setup-guide.md).

you need a mac, a terminal, and an internet connection for the first run. you do not need to install python yourself.

---

## get the code

either clone the repo:

```bash
git clone https://github.com/kennyxpalacios/dl-1.git
cd dl-1
```

no git? on the [repo page](https://github.com/kennyxpalacios/dl-1), click **Code**, then **Download ZIP**. unzip it and `cd` into the folder.

## run it

```bash
bash run.sh
```

then open http://127.0.0.1:3300 in any browser. press ctrl+c in the terminal to stop it.

the first run takes a minute. the script makes a virtualenv in `.venv/` and installs the requirements. after that it starts in a second.

### python

current yt-dlp needs python 3.10 or newer. the python that ships with macos is 3.9. if the script can't find a newer one, it downloads `uv` and a standalone python 3.12 into `.tools/` inside the dl-1 folder. nothing is installed system-wide.

### ffmpeg

you don't need to install it. `requirements.txt` includes `imageio-ffmpeg`, which bundles a binary. if you already have ffmpeg on your path, dl-1 uses that instead. to point at a specific one, set `DL1_FFMPEG`.

## other ways to start it

```bash
bash run.sh --setup      # set up only, don't start
bash run.sh --reset      # delete .venv/ and .tools/, set up again, start
.venv/bin/python server.py
```

## make it a mac app

```bash
.venv/bin/python make_app.py
```

this builds `dl-1.app`, copies it to `/Applications` and puts it in the dock.

- the app points at this folder. if you move or rename the folder, run `make_app.py` again.
- `--no-dock` skips the dock.
- `--build-only` writes `dist/dl-1.app` and nothing else.

if you got the source zip from someone, the order is `bash run.sh --setup`, then `.venv/bin/python make_app.py`.

the first time you open the built app, macos may block it once. same fix as the setup guide: **System Settings**, **Privacy & Security**, **Open Anyway**.

## settings

all optional, all environment variables. put them in front of the command:

```bash
DL1_PORT=8080 bash run.sh
```

| variable | default | what |
| --- | --- | --- |
| `DL1_PORT` | `3300` | port it listens on |
| `DL1_HOST` | `127.0.0.1` | address it listens on. `0.0.0.0` reaches it from other devices on your wifi |
| `DL1_DOWNLOAD_DIR` | `./downloads` | where job folders go |
| `DL1_MAX_WORKERS` | `2` | parallel downloads |
| `DL1_RETENTION_MINUTES` | `120` | finished files are deleted from the server after this. save them from the browser |
| `DL1_FFMPEG` | auto | path to an ffmpeg binary |
| `DL1_JS_RUNTIME` | auto | `node:/path/to/node`, `deno:/path/to/deno`, `bun:...` or `quickjs:...` |
| `DL1_COOKIES_FROM_BROWSER` | off | `chrome`, `firefox`, `safari`, `brave`, `edge` |
| `DL1_COOKIES_FILE` | off | path to a netscape-format `cookies.txt` |

## keep yt-dlp current

sites change and yt-dlp keeps up. every few weeks:

```bash
.venv/bin/python -m pip install -U yt-dlp
```

if the script set you up with uv, use `.tools/uv pip install --python .venv/bin/python -U yt-dlp` instead. the version shows in the top bar.

## undo everything

delete the dl-1 folder. that includes `.venv/` and `.tools/`. if you built the app, also delete `/Applications/dl-1.app`.
