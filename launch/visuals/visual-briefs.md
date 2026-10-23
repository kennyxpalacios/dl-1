# visual briefs // dl-1 launch

owner: visuals. hands to: content. status: draft, nothing posted.

## the idea

dl-1 is software. the renders show it as an object, the thing you'd want on your desk if it were one. that gap is the hook, so we say it out loud: "it's a mac app. it just looks like this." never let a render imply it's hardware for sale.

## house rules for every image

- off-white studio sweep (#f4f4f4), black hairlines, one orange (#ff3300). orange goes only on the run key, the mp4 key or the led.
- studio light, soft key from upper left, one contact shadow. no people, no hands.
- lowercase everywhere. readable words are limited to: dl–1, paste a link. pick a format. press run., mp4, mp3, run, the 01–05 labels.
- no platform names on anything bound for instagram or facebook. the panel's site strip gets left out of renders. real screenshots for meta get cropped to the controls and the display.
- no logos, no brand marks, no apple logo on laptops. hardware-inspired, not anyone's hardware.
- ui truth comes from real screenshots and screen recordings. renders are for mood. if a render's small text is gibberish, crop it or use it out of focus.

## the five prompts (the canonical set)

each uses the real panel screenshot (`screenshot.png` in the repo) as an image reference. model used today: higgsfield gpt image 2.5, high quality, 2k. full prompt text lives in `visual_prompts.json` inside the visuals zip.

1. **hero // three-quarter.** the panel as a slim, low off-white chassis, three-quarter from slightly above, mp4 and run keys orange, recessed black display on the right. the default image for everything. (`hf-01-hero`, also `hf-09-hero-wide` 16:9, `hf-10-hero-tall` 9:16)
2. **run key // macro.** extreme close-up of the orange run key with "03 action" above it, raking light, shallow focus. the "press run." beat. (`hf-03-runkey`)
3. **display // macro.** the black lcd showing real log lines: "dl–1 online", "stream 1 complete // video 1080p", "codec check // h264 + aac // plays everywhere", "done.", big "100 %". the "it just works" beat. (`hf-07-lcd`)
4. **low-key // night desk.** same object on charcoal, one strip light, the run key and led glowing. the mood image, the one people save. (`hf-08-lowkey`)
5. **exploded // how it's made.** axonometric layers labelled 01 source // url through 05 output // file, a board marked yt-dlp + ffmpeg underneath. for hn, product hunt and the readme. (`hf-06-exploded`)

extras generated: flat-lay with headphones, sd card, pencil (`hf-02`), the app icon as an object (`hf-05`), laptop on an oak desk (`hf-04`, `hf-12`), a nano banana alternate hero (`hf-11`).

## what was generated today

| file | use | verdict |
| --- | --- | --- |
| hf-01-hero | carousel slide 1, product hunt thumbnail, x post | lead pick |
| hf-08-lowkey | carousel closer, instagram story, x header | lead pick |
| hf-03-runkey | carousel "press run." slide, reel cover | lead pick |
| hf-07-lcd | carousel "plays everywhere" slide | strong, text is accurate |
| hf-06-exploded | show hn comment link, product hunt gallery 4, readme | strong |
| hf-05-icon | product hunt gallery 5, avatar tests | good |
| hf-02-flatlay | carousel "lives on your desk" slide | good |
| hf-09 / hf-10 | wide and tall hero variants for banners and stories | good |
| hf-04 / hf-12 | laptop context shots. check for any logo before use | ok |
| hf-11 | alternate hero, flatter angle | backup |

video loops (hyperagent veo 3.1, 8s, 1080p): a 9:16 dolly-in where the run key presses once (reel b-roll, story), and a 16:9 lateral track (product hunt gallery video, x). audio is room tone. mute it if the edit has its own sound.

## asset map for content

- carousel: 01 hero → 03 run key → real screenshot (cropped) → 07 display → 02 flat-lay → 08 low-key. type-only slides in between, off-white with black text, orange used once.
- reel: real screen recording is the body. the 9:16 loop is the first and last 1.5 seconds. cover frame: 03 run key.
- product hunt gallery: 1 hero wide, 2 real screenshot, 3 16:9 loop, 4 exploded, 5 icon.
- show hn: no images in the post. link the repo. the readme screenshot does the work.
- x / threads: 01 hero, or the 16:9 loop.

## spend log

- higgsfield: 31.5 credits. 10 × gpt image 2.5 high 2k at 2.75, 2 × nano banana 2.1 2k at 2. no higgsfield video.
- hyperagent: 2 × veo 3.1 standard 8s 1080p.
- rule from here: kenny hears about every higgsfield spend before it happens, with the credit count.
