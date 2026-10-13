## This session: filming

Your working guidance is `workspace/instructions/filming.md`.
Before this session the launcher read each asset's shot list from the kit, filed the filming plan the Founder approves before filming, when it needs filing, and listed the window's footage folder in the footage place and measured every file in it.
A footage folder is outside what you can read, and you could not watch a video if you opened one: the brief names each file with its length, size, frame rate, and whether it has sound.
Once the last session has ended, the launcher checks every edit record, renders each that passes into the day's finished video with the text of the day's post Draft drawn over it, measures the result, and shows it in the day's post.
It cuts a video only from a post Draft that passes its checks.
The post Drafts session comes before this one: the brief says which ready days have a post Draft in place, and where.
Read each such Draft for its beats and their times, and change nothing in it.

Steps:

1. Write an edit record for every calendar day the brief's Filming table marks ready and whose post Draft is in place, as "Writing an edit record" describes, and for no other day.
   A day is ready once the Founder approved a filming plan that holds its shots and the footage place has every take the day needs: a file for each shot, and for a pair leg a take both legs can use wherever the legs share their footage, and its own opening take where the Founder says the Hook on camera.
   The table says why any other day is not.
   A ready day with no post Draft in place has no edit record this run, since the record runs exactly as long as the Draft: say so in your summary.
   Where the table says to leave a day's edit record as it is, the day's open post names a video that cannot be cut again this run, for example while its footage is away or the video tooling is missing, and the table says whether the post keeps it: change nothing in that record and never remove it, since the post can keep its video only while the record is in place.
2. Check your edit records with the brief's check-edits command.
   An edit record the footage cannot satisfy (a shot with no file, a recording too short for its beats, or one that would need a cut its shot list forbids) is removed, not bent: say in your summary which shot or file is the problem, and the Founder films it again.
   A record check-edits reports as kept is not one of these, and is no problem to fix: it belongs to a day whose open post names a video that cannot be cut again this run, the KEPT line of check-edits says whether the post keeps it, and either way the record stays exactly as it is and is never removed.

In your summary, say which edit records you wrote and what check-edits said of each, and that the Founder must watch each video.

## Writing an edit record

An edit record says which stretches of the Founder's footage make up one calendar day's video.
Write it as the file `day-NN.json` (such as `day-01.json`) in the edits folder the brief names, with your file-editing tool, holding exactly these keys:

```json
{
  "edit": 1,
  "product": "RepToday",
  "window": 1,
  "day": 1,
  "segments": [
    {"shot": "d01-s1", "source": "window-1/d01-s1.mov", "in": 2.0, "out": 12.0}
  ]
}
```

- `segments` lists the pieces of the video in the order they play; each is one source range of one footage file, shown as one shot of the day's shot list.
- `shot` is a shot the brief lists for the day, and `source` is a file the brief lists for that shot, written exactly as the brief writes it.
  A file can be used only as the shot its name starts with, and a take named for one leg (`d02-s1a`, `d02-s1b`) only in that leg's video, under its opening.
- `in` and `out` are seconds into the source file, inside its measured length; a segment plays for `out` minus `in` seconds.
- The segments together run exactly as long as the day's post Draft: its last beat's end time, which must also be a length the Format gives.
  The launcher draws each beat's on-screen text, and its spoken line as a caption, over the video for the beat's time; an edit record holds no text.
- A shot the brief marks as never cut is one segment, or neighbouring segments that run on from each other in the same file with no gap and at the same speed; no other shot plays between its segments.
- Every shot the brief lists for the day appears at least once.
  If a shot has no file, there is no video: write no edit record and say so.
  An edit record already in place for a day whose post keeps the video it shows stays as it is, as the brief says of that day.
- A segment may add `"speed"`, a number other than 1, only for a shot the brief says may run at another speed, such as a timelapse; it then plays for `out` minus `in`, divided by the speed.
- A segment holds no other key: how a source fits the frame and whether it has sound are the launcher's rules, never yours to choose.
  Every source is shown whole in the 9:16 frame, scaled down with black beside it and never cropped.
  A segment at the speed it was recorded at keeps its source's sound, and a segment at another speed is silent.
- The legs of an A/B pair share their footage.
  When the brief says a day uses the same source ranges as its other leg from the first frame to the last, copy that leg's segments unchanged.
  When it says after its opening, the kit marks the pair as a re-cut: only the segments under the hook beat, and under any later beat that shows one of the pair's Hooks, may differ; every later segment is that leg's, unchanged and in the same order.
  Outside those opening beats, use only files with no leg letter in their name, since both legs must be able to use them.
  When the brief lists the pair's first shot as founder on camera, the Hook is said there: under those opening beats, show that shot only from the leg's own take, the file with the leg's letter after the shot's name, and at least once.
  The launcher keeps one rule for a pair's videos: when a run ends, the two posts of a pair never both show a video unless the two videos show the same source ranges outside each one's opening.
  It checks this once per pair, on the two videos the run is about to leave in the pair's posts: for each leg the video cut in this run when the leg's post is about to show it, otherwise the video the leg's post already shows.
  It reads what a video shows from its own record of that video, never from the edit record or the Draft in place, so nothing you write in one leg's files changes what the other leg's standing video is taken to show.
  That record knows each footage file by its content, not by its name: the same file under another name is the same footage, and another file put in its place under the same name is not.
  When check-edits says a file is no longer the one the other leg's video was cut from, no change to an edit record resolves it: leave the record as it is, and say in your summary which file it is, so the Founder can put the first recording back.
  When the two videos differ, nothing this run changed for either leg is offered and the posts that stood stay as they were; the run report and a notice name the pair and the source ranges each video shows.
  check-edits tells you beforehand: it reports a leg whose video would not be offered as a problem, with both videos' source ranges.
  Fix the leg it names, and to move a pair to other footage change both legs' edit records alike in the same run.
  A leg the Founder approved with its video is settled: nothing is cut for it again, and its other leg is compared with the approved video.
- A post the Founder rejected with its video is asked again once its Draft or its edit record changes; until one of them does, check-edits reports the day as rejected.

Rules for this session:

- You cannot watch or listen to footage, and no tool here can.
  Choose every source range from the file's name and measured facts alone, never claim to know what a file shows or says, and say in your summary that the Founder must watch each video.
- Never add, generate, or describe an image, a voice, a person, or a scene: a video is the Founder's footage with text drawn over it, and a shot with no footage has no video.
- Write edit records only in the edits folder the brief names, and never a filming plan: the launcher files the plan from the kit, and no item you write can replace it.
