<!-- The approve-the-plan-before-any-edit gate below is adapted from skills/video/references/edit-anatomy.md, and the notes on fitting footage to the 9:16 frame from skills/ad-creative/references/short-form-video-specs.md, of github.com/coreyhaines31/marketingskills at commit 1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff (MIT; see THIRD_PARTY_NOTICES.md). -->
# Filming and edit records

How to turn the Founder's raw footage into an edit record the launcher can render into a day's finished video.
This is the Marketing Engineer's own working guidance; it holds no package content, which stays in Mandu.
The edit record's format is in the task definition, and the launcher's checks decide whether a video is made; this page is about the choices the checks cannot make.

## What is yours and what is not

- The filming plan is the launcher's: it reads each asset's shot list from the Angle's Format in the kit, groups the shots into sittings, and files one item the Founder approves before filming.
  You never write, change, or replace it.
- The video itself is the launcher's too: it renders your edit record with the day's post Draft drawn over it, and measures the result.
- Yours is the edit record: which stretch of which file plays, in which order.
- You cannot watch or listen to a file, and nothing in the run can.
  You know a file by its name, its length, its size, its frame rate, and whether it has sound, and by nothing else.
  Never write as if you had seen a recording, and never say a take is good: the Founder watches every video before approving its post.

## Before you write

- Read the brief's Filming table: it lists, for each calendar day due, the shots the edit must show, the length the Format gives, the files the footage place holds for each shot with what was measured, and whether the day is ready.
- Write an edit record only for a day marked ready.
  A day is not ready while its filming plan is not approved, while a shot has no file, or while the video tooling is missing; the table says which, and so should your summary.
- Read the day's post Draft: its beats set the video's length and the time of every line of text.
  The edit runs exactly to the last beat's end.

## Choosing source ranges

- A shot the table marks as never cut is one unbroken stretch of one file.
  Pick one stretch as long as the shot plays for, and leave it whole: never cut away to another shot and back.
- A file is usually longer than its shot: the recording starts before the action and ends after it.
  With nothing but the length to go on, take the stretch from the middle of the file, leaving the same margin at each end, and say in your summary that the start point is a first guess the Founder should check.
  When the Founder's rejection reason names a start point, such as "start a second later", use it exactly.
- When a shot has several takes, use the one the Founder's note or rejection reason names; with nothing to choose by, use the latest by name, and say which.
- Never stretch footage to fit: a recording shorter than its beats cannot be slowed down, looped, or padded.
  If the Draft's post is not approved, shorten the Draft's beats to what the footage holds, keeping the hook beat, and keep the length inside the Format's; otherwise write no edit record and say what is too short.
- A speed other than 1 is for a shot the table says may run at another speed, such as a timelapse.
  Choose the speed that fits the whole recording into the beats: the source range's length divided by the time it must play for.
- Keep a screen recording whole in the frame: leave `fit` at its default, so its edges are never cropped away.
  Use `"fit": "cover"` for camera footage only when the table shows it was filmed wider than 9:16.

## Pair legs

- The legs of an A/B pair are cut from the same footage, so the later leg films nothing new.
- When the table says a day uses the same source ranges as its other leg from the first frame to the last, copy that leg's segments and change only the day.
  The two videos then differ only in the Hook the launcher draws over them.
- When it says after its opening, the kit marks the pair as a re-cut.
  Each leg opens on its own take, the one whose name ends in the leg's letter, such as `d06-s1a` for leg A and `d06-s1b` for leg B.
  Use a lettered take only under the opening beats: everything after them comes from files with no leg letter, which both legs can use.
  Every segment after the opening is the other leg's, unchanged and in the same order.
- When the other leg's video is already in an open or approved post, never change that leg's edit record to make the two match: change the newer leg.

## When a rule blocks an edit

- check-edits names the rule: fix what the edit record can fix, such as a range past the end of a file or a length that does not match the Draft.
- A record the footage cannot satisfy is removed, never bent to pass: say which shot or file is the problem, so the Founder films it again.
- Never use a file as a shot it is not named for, and never name a file the brief does not list.
