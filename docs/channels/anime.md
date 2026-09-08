# anime - channel doctrine

Config: `channel-anime.toml`. Runs: `projects-anime/`. Not yet created on YouTube.

**Ready to produce on.** The style was locked 2026-09-08; what remains before a first upload is a
YouTube channel, a topic and a first Run.

**Premise.** Stories and scenarios, narrated and acted - "life before AI" is the shape, an ordinary
person moved through a situation rather than a list of facts about it.

**Format.** Narrative, always. This is the channel the format was built for.

**Why this channel exists.** Channel one runs 1-2.2% click-through and stikkky 0-1.5%, against a
healthy 4-6%. That is a thumbnail number, not a video-art number: nobody who did not click has ever
seen a Scene. So the bet being placed here is that an anime thumbnail out-clicks a stickman one, and
the cheap half of that test - re-thumbnailing stikkky's four uploaded videos and watching CTR - runs
in parallel and does not need this channel at all. Worth knowing which experiment answered what.

**Intro.** Cold open. The story starts at Scene 1, in scene, and the hook is a narrative moment
rather than a stated question. No presenter to camera and no standing set: a story that opens by
cutting to a narrator explaining that a story is coming is fighting itself.

**No outro.** The video ends on its last Scene. No callback, no fixed turn, no sign-off - a story
that has finished should stop, and the three-Scene outro the other two channels run is an explainer
device that would read as tacked on here.

The cost is real and accepted: those three Scenes exist partly because they run about fifteen
seconds, which is the runtime YouTube's end screen needs. Ending on the last Scene leaves nowhere to
put one, so this channel gives up the end-screen subscribe button and the next-video card. Watch
whether that shows up in subscribers per view against the other two channels.

**Cards.** Time and chapter markers rather than ranks: "2019", "THREE YEARS LATER", "THE NIGHT IT
CHANGED". Same `card: true` flag, same `plain_card` clause. Short capitalised words only - Meta
spells those correctly and does not spell sentences.

**Pacing.** The 7-10 second default holds. Short beat Scenes of 3-5 seconds are allowed inside a
Beat Group, for a reaction that carries three words. They are not licence to deliver a full sentence
fast: at 1.0 speed and three seconds a Scene the delivery had no room to land a line, which is what
sent the channels back to 7-10 seconds in the first place.

**Acting.** Named per Scene - the Lead's expression and body language in the Image Prompt, and a
reaction given its own frame rather than folded into the shot before it. The Lead Sheet carries an
expression row so Meta has references for them.

**Quota.** One Run a day on the shared Meta account, roughly twenty one images. Four audition
candidates plus a forty-Scene story is a two to three day image job.

## What the probe found (2026-09-08, 10 images, `tuning/anime-probe/`)

**Meta draws anime well.** The character sheet came back with four angles, a three-expression row
and a correct 16:9 frame, off nothing but a placeholder prefix.

**A character reference works.** The sheet attached to a fresh prompt produced a new scene - bus
stop, rain, different clothes and pose - with the same face and hair, and an incidental costume
detail carried through. Nothing was edited or returned. The Lead mechanism is sound.

**A setting reference does not.** Attached alongside the sheet, the kitchen came back a different
kitchen. Attached alone, with an explicit "keep the room exactly as it is", still a different
kitchen. Meta reads an attached scene as mood and palette, not as a room to rebuild. And the first
attachment wins: putting the setting first cost the character too, returning a person nobody drew.
Settings are therefore held by a verbatim Visual Bible line
([ADR-0004](../adr/0004-one-reference-picture-per-scene.md)).

**Shot clauses hold.** `shot_wide`, `shot_close` and `shot_over_shoulder` each did what they say and
kept the 16:9 frame - close included, which was the one expected to drift portrait. `shot_low`,
`shot_high` and `shot_medium` are untested. `shot_over_shoulder` invents a second figure by
definition, so it belongs only on Scenes that genuinely have two people.

## The style, locked 2026-09-08

`flat-cel`, from a four candidate grid in `tuning/style-grid/anime`: flat 2d anime cel, clean even
black outlines of constant weight, one hard edged shadow tone and no gradients, bright saturated
palette, simple uncluttered backgrounds.

It won on consistency rather than beauty. `retro-cel` and `painted` were both better looking and
both drifted into brushwork and washes; `soft-cel` drifted into gradients. `flat-cel` drew a face,
an interior and an empty exterior in the same treatment, and it left the empty street empty - the
subject that catches a prefix quietly supplying a character.

The negative prompt is built from what the losers did, not copied from the stickman channels, whose
list bans "clean vector art" and "smooth even line weight" - a description of this look.

## Before the first upload

- Create the channel: handle, avatar, banner.
- Pick the first topic and check it against YouTube search first, the way the dumbest-deaths topic
  was on 2026-08-26.
- First Run: audition the Lead, then a narrative Script - cold open, Beat Groups, time marker cards,
  no outro. A forty Scene story is two to three days of image allowance.
- Thumbnails use the `caricature` style in `scripts/thumbnails.py`, same as the stickman channels.
