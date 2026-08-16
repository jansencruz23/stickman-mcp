---
name: produce-video
description: Produce a stickman explainer video from a Topic - Script, narration, images, and the rendered Video Package. Use when the creator asks for a video about a topic, or to resume an interrupted Run.
---

# Produce a video

One Topic in, one Video Package out. You write the Script, the Image Prompts and the upload
metadata; the `stickman_*` tools do the mechanical work and nothing else ([ADR-0002](../../../docs/adr/0002-creative-work-in-host-claude.md)).
The vocabulary below is the project's — [CONTEXT.md](../../../CONTEXT.md) defines it.

## Read the request first

Three switches, all set by the creator's opening message:

- **Scene count.** Default 30-45 Scenes. An explicit count ("4 scenes only") wins outright.
- **Yolo Mode.** The word "yolo" turns off both Checkpoints, the duration offer, and the music
  question. Say once that you are in Yolo Mode and will not stop, then run to the end and report.
- **Music.** A named track, or "no music". Unstated: ask at the render step in default mode, and
  render without music in Yolo Mode.

## The Run

1. **Create.** `stickman_create_run(topic)` returns the run id every later call takes.
2. **Write the Script** — see [Writing the Script](#writing-the-script). Done when every Scene has
   narration and an Image Prompt, and Scene 1 hooks.
3. **Script Approval Checkpoint** — see [The two Checkpoints](#the-two-checkpoints). Skipped in
   Yolo Mode.
4. **Save.** `stickman_save_script(run_id, script)`. It validates; a returned `Error:` names what to
   fix. Heed a `warning` about stale assets — it means clips or images on disk no longer match.
5. **Narrate.** `stickman_synthesize_narration(run_id)`. One synchronous call that takes minutes for
   a full Script; Claude Code backgrounds it after two and the session stays usable. Then apply the
   [duration rule](#the-duration-rule).
6. **Illustrate.** `stickman_generate_images(run_id)` starts a background job and returns at once.
   Poll `stickman_job_status(run_id)` until `state` leaves `running` — `done` moves on, `error`
   carries the failure and sends you to [When a stage stops](#when-a-stage-stops).
7. **Image Review Checkpoint** — see [The two Checkpoints](#the-two-checkpoints). Skipped in Yolo
   Mode.
8. **Render.** `stickman_render_video(run_id, music_track)` — another background job, polled the
   same way. For music, `stickman_list_music()` lists the curated folder and the track is passed by
   file name.
9. **Metadata** — see [Writing the metadata](#writing-the-metadata).
10. **Hand over.** Give the three paths: `video.mp4`, `subtitles.srt`, `metadata.txt`. Remind the
    creator to tick YouTube's altered-or-synthetic-content declaration when they upload.

## Writing the Script

The Script is the single source of truth for narration, images, subtitles and timing, so it is
authored as ordered Scenes from the start — never as prose you split later
([ADR-0001](../../../docs/adr/0001-scene-first-scripts-no-timestamper.md)). It saves as `topic`,
`title`, an optional `visual_bible` of name to description, and `scenes`, each
`{id, narration, image_prompt}` with ids sequential from 1.

Shape of the whole: **hook, stakes, explanation in steps, payoff.** Scene 1 states the question the
viewer wants answered or the surprising claim you are about to prove, and earns the next thirty
seconds before any explaining starts. Every Scene after it leaves a reason to watch the next one.

Shape of one Scene: 2-4 sentences carrying one idea, 8-15 seconds spoken. Write what should be
*said* — short sentences, plain words, symbols and abbreviations spelled out the way a voice reads
them ("twenty per cent", not "20%").

A 5-10 minute video is 30-45 Scenes. Measured on this channel's voice a Scene averages about 12
seconds, so estimate on that at the Checkpoint; the real number arrives after synthesis.

### Image Prompts

The channel's [Illustrative Format](../../../CONTEXT.md): each Scene is a **standalone visual
metaphor** for its narration. No Scene promises visual continuity with its neighbours, so each
prompt must stand alone.

Describe subject, action and composition in plain nouns and verbs — what is in the frame and what
it is doing. Content only: the server prepends the channel Style Prefix and applies the negative
prompt to every image, which is what makes all frames of all videos one look. Style words in your
prompt ("minimalist", "line art", "black and white", "flat vector") fight that prefix, and are the
one reliable way to break the channel's identity.

### Visual Bible

Any character or setting appearing in more than one Scene earns a Visual Bible entry: a name mapped
to one canonical line of description. Paste that line **verbatim** into every Image Prompt that
mentions it — the server does not expand entries for you, and paraphrasing is what makes a recurring
character drift between Scenes.

## The two Checkpoints

Both are hard stops: end the message, wait for the creator, do nothing else until they answer.

**Script Approval** — before anything is saved or synthesized, so a rejected Script costs no GPU
time. Show the title, the Visual Bible, and every Scene in order with its id, narration and Image
Prompt. Give the estimated duration. Then stop. Edits mean revising and showing the changed Scenes
again, still before saving.

**Image Review** — after the images job finishes. Name the Run's `images/` folder so the creator can
open it, note that files are `001.png`, `002.png`, ... by Scene id, and offer regeneration. Then
stop.

- "scene 7 again" — `stickman_regenerate_image(run_id, 7)` rerolls the seed, same prompt. For a
  picture that is unlucky.
- "scene 7 should show a cracked bridge" — `stickman_regenerate_image(run_id, 7, image_prompt=...)`
  writes the new prompt into the Script, then redraws. For a picture that is wrong.

Each regeneration replaces that one file and touches no other Scene. Report the new image's path and
stop again for the verdict.

### The duration rule

The finished video runs `total_duration_seconds` plus one 0.4 s gap per Scene, so judge that number
rather than the narration alone. The target is 5-10 minutes; the band that needs no comment is
**4.5-10.5 minutes**.

Outside it, state the length and which side it fell on, then offer to lengthen (add Scenes, or
expand thin narration) or shorten (merge or cut Scenes) — or to proceed as it stands. Then wait.

Acting on the answer means **deleting before regenerating**, because synthesis and the image batch
both skip any Scene that already has a file:

- An edited Scene keeps its old clip until you delete `audio/<id>.wav`, and its old picture until
  you delete `images/<id>.png`.
- Cutting or merging Scenes renumbers every Scene after it, so their existing clips and images stay
  on disk attached to the wrong Scene — and a render would happily use them. Delete those too.

The `warning` the re-save returns lists exactly what went stale.

In Yolo Mode, state the length and the breach in passing and keep going.

## Writing the metadata

`stickman_save_metadata(run_id, title, description, tags)`:

- **Title**, at most 60 characters, so it survives YouTube's truncation. Concrete and specific about
  what the viewer will learn.
- **Description**: two to four sentences on what the video covers. The server appends the
  AI-generation disclosure line for you — write the description without one, or the saved file
  carries it twice.
- **Tags**: 10-15, mixing the broad topic with the specific terms the video actually explains.

## When a stage stops

Every stage derives its state from files on disk, so nothing finished is ever redone. Call
`stickman_get_run(run_id)` to see where a Run stands, then:

- **Narration interrupted** — call `stickman_synthesize_narration` again; it skips Scenes that
  already have a clip and finishes the rest.
- **Image job stopped** — `stickman_generate_images(run_id, only_missing=True)` draws only the
  Scenes without an image.
- **Render failed** — fix what the `Error:` names, then call `stickman_render_video` again; it
  rebuilds the whole package.
- **Script rewritten mid-Run** — the save `warning` lists the assets that went stale. Delete those
  files before re-running the tool named beside each, because those tools skip Scenes that already
  have assets.
