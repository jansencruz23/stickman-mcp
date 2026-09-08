---
name: produce-video
description: Produce a stickman explainer video from a Topic - Script, narration, images, and the rendered Video Package. Use when the creator asks for a video about a topic, or to resume an interrupted Run.
---

# Produce a video

One Topic in, one Video Package out. You write the Script, the Image Prompts and the upload
metadata; the `stickman_*` tools do the mechanical work and nothing else ([ADR-0002](../../../docs/adr/0002-creative-work-in-host-claude.md)).
The vocabulary below is the project's — [CONTEXT.md](../../../CONTEXT.md) defines it.

## Read the channel's doctrine first

The skill holds what is true of every channel. The premise, intro, cards and avatar are
per-channel and live in `docs/channels/`, one file each - read the one for the channel this Run is
on before writing a Scene:

- [could-be-worse.md](../../../docs/channels/could-be-worse.md) - `channel.toml`, ranked countdowns
- [stikkky.md](../../../docs/channels/stikkky.md) - `channel-stikkky.toml`, general stickman
- [anime.md](../../../docs/channels/anime.md) - `channel-anime.toml`, stories in an anime look

## Read the request first

Four switches, all set by the creator's opening message:

- **Format.** `illustrative` (the default) or `narrative` - see [Two Formats](#two-formats). A
  ranked list is illustrative; a story or scenario is narrative. The channel does not decide this.
- **Scene count.** Default 35-70 Scenes. An explicit count ("4 scenes only") wins outright.
- **Yolo Mode.** The word "yolo" turns off all three Checkpoints, the duration offer, and the music
  question. Say once that you are in Yolo Mode and will not stop, then run to the end and report. On
  a narrative Run it takes the first Lead candidate unseen, which is the expensive thing to get
  wrong at roughly twenty one images a day — worth saying out loud when the creator asks for both.
- **Music.** A named track, or "no music". Unstated: ask at the render step in default mode, and
  render without music in Yolo Mode.

## The Run

1. **Create.** `stickman_create_run(topic)` returns the run id every later call takes.
2. **Write the Script** — see [Writing the Script](#writing-the-script). Done when every Scene has
   narration and an Image Prompt, and Scene 1 hooks.
3. **Script Approval Checkpoint** — see [The Checkpoints](#the-checkpoints). Skipped in Yolo Mode.
4. **Save.** `stickman_save_script(run_id, script)`. It validates; a returned `Error:` names what to
   fix. Heed a `warning` about stale assets — it means clips or images on disk no longer match.
5. **Audition the Lead** — narrative Runs with a recurring character only; skip it entirely
   otherwise. `stickman_audition_lead(run_id, sheet_prompt)` starts a background job, polled like
   the image job. Then the **Lead Audition Checkpoint**, and `stickman_choose_lead(run_id, n)`.
   In Yolo Mode, choose candidate 1 without stopping.
6. **Narrate.** `stickman_synthesize_narration(run_id)`. One synchronous call that takes minutes for
   a full Script; Claude Code backgrounds it after two and the session stays usable. Then apply the
   [duration rule](#the-duration-rule).
7. **Illustrate.** `stickman_generate_images(run_id)` starts a background job and returns at once.
   Poll `stickman_job_status(run_id)` until `state` leaves `running` — `done` moves on, `error`
   carries the failure and sends you to [When a stage stops](#when-a-stage-stops).
8. **Image Review Checkpoint** — see [The Checkpoints](#the-checkpoints). Skipped in Yolo Mode.
9. **Render.** `stickman_render_video(run_id, music_track)` — another background job, polled the
   same way. For music, `stickman_list_music()` lists the curated folder and the track is passed by
   file name.
10. **Metadata** — see [Writing the metadata](#writing-the-metadata).
11. **Hand over.** Give the three paths: `video.mp4`, `subtitles.srt`, `metadata.txt`. Remind the
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

Shape of one Scene: 2-3 sentences carrying one idea, 7-10 seconds spoken. Write what should be
*said* — short sentences, plain words, symbols and abbreviations spelled out the way a voice reads
them ("twenty per cent", not "20%").

A Scene holds one still, and these stills do not move. Channels that cut every 3-4 seconds are
animating; cutting a static picture that fast reads as flicker rather than pace. One idea per Scene,
held long enough to look at. The intro is the exception, and it has its own rule below.

Measured across 96 Scenes and 2024 words at `am_puck` speed 1.0, narration runs **0.35 seconds a
word**, so 7-10 seconds is **20-29 words**. A 5-10 minute video is **35-70 Scenes**, and 8-12
minutes is 65-100. Estimate words first, not Scenes: word count times 0.35 is reliable, and a Scene
count is not, because a card Scene runs a third as long as a content one.

### The intro

Illustrative Runs only - a narrative Run cold opens instead, see
[The narrative intro is a cold open](#the-narrative-intro-is-a-cold-open).

The opening decides whether the rest is watched, so the intro is cut faster and staged differently
from the body. **How long, and over how many Scenes, is a channel decision** - the doctrine file
gives the number, and they differ: one channel runs thirty to forty seconds, another ten to fifteen.

Whatever the length, the intro is cut at roughly **twice the rate of the body**, four to five
seconds a Scene, which is 11-14 words at 0.35 seconds a word. It is the one place the flicker
warning above does not apply: nobody has settled in yet, so movement reads as pace rather than
noise. The body returns to 7-10 seconds a Scene.

**The character presents it.** About half the intro Scenes are the channel figure talking to camera -
mouth open mid-speech, one clear gesture, seen front on and close. The other half are the ordinary
standalone metaphors. Alternate them rather than grouping: four talking heads in a row read as one
held frame, because a still does not move and the viewer cannot tell the cut happened.

**The presenter Scenes share one standing set**, held as a Visual Bible entry and pasted verbatim
into each of them, the same way any recurring location is. A set is what separates an intro that
looks like a channel from one that looks like a blank slide, and it should be the literal claim the
intro makes. Each channel's own set is in its doctrine file.

Presenter Scenes carry the `people` clause like any other Scene with a person in it. The channel
avatar is that figure, and since there is no outro it now appears only here - so the intro is the
one place the channel's face is established, and it must not drift.

### The ending

**No channel runs an outro.** A video ends on its last Scene - the last ranked item, or the last
beat of the story. Dropped across all three channels on 2026-09-08: a fixed sign-off written once
and pasted onto every video lands unconnected to what the video was actually about, and reads as
arriving out of nowhere.

Two things follow. Nothing asks for on-screen words at the end, and there is no fifteen-second tail
for YouTube's end screen, so the subscribe button and next-video card have nowhere to sit - a known
cost, accepted. Write the last Scene so it can carry the ending on its own.


### Image Prompts

In the [Illustrative Format](../../../CONTEXT.md) each Scene is a **standalone visual metaphor** for
its narration: no Scene promises visual continuity with its neighbours, so each prompt must stand
alone. In the narrative format that holds only across a Beat Group boundary - inside a group the
Scenes share a setting, and hold it by repeating its Visual Bible line word for word.

Everything below applies to both.

Meta declines some prompts, and a refusal is invisible: it answers with words instead of a picture,
which the backend can only read as a timeout after 180 seconds.

**The line is suffering, not intensity** - narrowed 2026-09-08 by testing it deliberately. Refused: a
body under a sheet, a man kneeling with his head hanging, a face shouting with veins showing, and a
two panel before-and-after split. Drawn without complaint: bulging bloodshot eyes, deep hollow eye
rings, sweat, drool, wild hair, a manic grin, and a dinosaur's open jaws a foot from a man's face.
So a wrecked, frightened or disgusting figure is fine; a figure in pain is not. Collapse,
unconsciousness and a hand at a throat still risk it.

Where a Scene does need pain, let the picture hold the place instead of the person - the empty
ground, the heat shimmer, the still water - or show the figure upright and seen from behind.

Describe subject, action and composition in plain nouns and verbs — what is in the frame and what
it is doing. Content only: the server prepends the channel Style Prefix and applies the negative
prompt to every image, which is what makes all frames of all videos one look. Style words in your
prompt ("minimalist", "line art", "black and white", "flat vector") fight that prefix, and are the
one reliable way to break the channel's identity.

### Card Scenes

A countdown or chapter screen is a Scene with `"card": true` alongside its `id`, `narration` and
`image_prompt`. That flag does one thing: it lifts `text`, `watermark` and `signature` from the
negative prompt, because a ranking screen exists to be read. Everything else about the channel look
still applies.

Use one to open each item of a ranked list, and describe the screen literally - what is on it,
where, and how large. Meta spells single digits and short capitalised words like BAD and NIGHTMARE
correctly, so both are safe. Sentences on an image are still not.

Cards in one video do not have to share a layout. Design each for its own rank: the card announcing
number 4 can be built around the 4 alone. A row of every rank with one marked is allowed where it
earns its place, but it is not the default, because asking Meta to index into a row is the one part
it gets wrong - it circled the wrong digit twice in a ten-item countdown.

Hand-lettering shifts a little between cards whatever the layout. That reads as the channel's look
rather than a mistake, but it does mean no two cards are pixel-identical.

Ordinary Scenes never set it. Words on a normal Scene are a mistake the negative prompt is there to
prevent.

### Animals

The Style Prefix says nothing about animals, deliberately: naming them on every image had Meta
supplying a dog and a sheep to Scenes that asked for neither. So a Scene that genuinely needs one
carries the rule itself, pasted verbatim the way a Visual Bible entry is:

> drawn as an ordinary four legged cartoon animal with a solid furry body and a real animal head

Without it the stick figure treatment bleeds onto the animal and you get a beaked stick-wolf or a
dog with a round human head. Only Scenes whose narration actually has an animal get the phrase.

### Style clauses

A channel may declare named clauses in `[style.clauses]`, and a Scene opts into them by name:
`"clauses": ["creature"]` alongside its `id`. They are off by default and that default matters.

Meta supplies whatever the prefix names. A clause reading "any creature is drawn as..." put a deer
beside a man on a cliff and a mouse beside an intestine; applied channel-wide to a prehistory video
it gave a bare wall of glacier ice two hikers, a polar bear and a caribou. So a clause must ride only
on the Scenes that genuinely hold that subject. Marking a Scene that has none is the mistake; leaving
one unmarked only costs that Scene its anatomy rule.

Check the channel config for which names exist. A name the channel does not offer stops the batch
and says so, rather than drawing every Scene without the rule.

### Visual Bible

Any character or setting appearing in more than one Scene earns a Visual Bible entry: a name mapped
to one canonical line of description. Paste that line **verbatim** into every Image Prompt that
mentions it — the server does not expand entries for you, and paraphrasing is what makes a recurring
character drift between Scenes.

## Two Formats

A Script declares one, and it is a decision about the *content*, not about the channel. Any channel
produces either.

**Illustrative** (`"format": "illustrative"`, the default) - each Scene a standalone visual metaphor
for its narration, nothing carried between them. The right shape for a ranked list, because ten
items genuinely are unrelated and pretending otherwise costs continuity you cannot deliver.

**Narrative** (`"format": "narrative"`) - the shape a story or scenario takes. Scenes run in **Beat
Groups**, and the rules below apply on top of everything else in this skill.

### The narrative intro is a cold open

A narrative Run has no intro section in the sense above: no presenter to camera, no standing set, no
stated question. The story starts at Scene 1, in scene, and the hook is a narrative moment. A story
that opens by cutting to a narrator explaining that a story is coming is fighting itself.

That makes the intro rule per *Format* first and per channel second: a channel's doctrine file gives
its intro length for illustrative Runs, and a narrative Run on the same channel ignores it.

### Beat Groups

A Beat Group is 3-6 consecutive Scenes sharing one setting. Write the first as the wide shot that
shows the space, then the Scenes after it as closer looks *inside* that space, and cut hard to a new
group when the story moves.

**Nothing in the Script marks a group.** It is a way of writing, not a field. What actually holds the
setting together is a **Visual Bible entry pasted verbatim** into every Image Prompt in the group -
the same mechanism that holds any recurring location, and the only one that works. Write the setting
once, as one line, and repeat it exactly.

**The cut between two groups is deliberate.** Continuity is promised inside a group and nowhere else.
Meta has no seed, so holding one setting across forty Scenes is not achievable; holding it across
four, by repeating its line, is. Three to six is the working range - a group of twelve is a group
that has stopped being one.


### The Lead

A narrative Run's recurring character. Give it a Visual Bible entry like any recurring subject, and
then a picture as well:

1. `stickman_audition_lead(run_id, sheet_prompt)` draws candidates. Ask for a **character sheet** -
   several angles and two or three expressions in one image - not a single pose. One image is one
   attachment and one unit of the daily allowance, and the angles are what Meta otherwise invents.
2. Show them at the **Lead Audition Checkpoint** and stop.
3. `stickman_choose_lead(run_id, n)` on the answer.

Then mark `"lead": true` on **only** the Scenes that actually hold the character. This is the same
rule as a style clause and it matters more here: an attached picture is a stronger instruction than
a phrase, so marking a Scene that has no person is how the Lead ends up in an empty street. Leaving
a Scene unmarked only costs that Scene its reference.

**One Lead per Run, and one picture per Scene.** Meta reads the first attachment and ignores a
second, so there is no room for a second character or for a setting picture alongside the Lead
([ADR-0004](../../../docs/adr/0004-one-reference-picture-per-scene.md)). Everything other than the
Lead's face is held by words.

### Acting, in a picture that does not move

A still cannot act, so the acting is carried two ways. **Name the expression and the body language**
in the Image Prompt - not "she is upset" but what the frame shows. And **give a reaction its own
Scene**: three shots where an explainer would use one.

That second one bends the pacing rule and only that far. A reaction Scene runs 3-5 seconds because
it carries three or four words. It is not licence to deliver a full sentence fast - at 3 seconds a
Scene with a whole line in it, the delivery has no room to land before the picture cuts, which is
the failure that set the 7-10 second default in the first place.

### Cards in a narrative Run

Cards stay, and stop being ranks. A card is a time or chapter marker - `2019`, `THREE YEARS LATER`,
`THE NIGHT IT CHANGED`. Same `"card": true`, same `plain_card` clause where the channel has one,
same rule that short capitalised words are safe and sentences are not.

## Shot grammar

Every channel offers six shot clauses, and a Scene opts into **one**:

`shot_wide`, `shot_medium`, `shot_close`, `shot_low`, `shot_high`, `shot_over_shoulder`.

They exist because a run of Scenes that are each a single object floating in space reads as random
rather than directed. Naming where the camera is turns a list of pictures into a sequence, and it
does that on any channel and either format - a countdown benefits as much as a story.

Two limits. **One shot clause per Scene**: they contradict each other, and Meta obeys the last thing
it read. And **nothing beyond these six** - no panels, no split screens, no frames within frames. A
composed layout is the recorded way to lose the channel look outright, and the words in these
clauses were chosen to stay plain camera language for exactly that reason.

## The Checkpoints

Three exist, and all are hard stops: end the message, wait for the creator, do nothing else until
they answer. The Lead Audition happens only on a narrative Run that has a Lead.

**Script Approval** — before anything is saved or synthesized, so a rejected Script costs no GPU
time. Show the title, the Visual Bible, and every Scene in order with its id, narration and Image
Prompt. Give the estimated duration. Then stop. Edits mean revising and showing the changed Scenes
again, still before saving.

**Lead Audition** — after `stickman_audition_lead` finishes, before narration. Name the Run's
`reference/` folder, note the candidates are `lead-01.png`, `lead-02.png`, ... and stop. On the
answer, call `stickman_choose_lead`. Redrawing the set is another `stickman_audition_lead` call,
which costs the allowance again — say so before offering it.

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

The finished video runs `total_duration_seconds` plus one `render.scene_gap_seconds` per Scene,
currently 0.0, so judge that number rather than the narration alone. The target is 5-10 minutes;
the band that needs no comment is **4.5-10.5 minutes**.

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
