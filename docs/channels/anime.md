# anime - channel doctrine

Config: `channel-anime.toml`. Runs: `projects-anime/`. Not yet created on YouTube.

**Not ready to produce on.** The style prefix and negative prompt in the config are placeholders and
the probe below has to run first. Everything else here is decided.

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

**Outro.** Not written. Needs a sign-off in the shape of the other two channels - a callback written
fresh, a fixed turn, a fixed ask - before the first upload.

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

## The probe, before any of this is used

One day's allowance, eight to ten images. It answers four things, and the second one decides
whether the design in [ADR-0003](../adr/0003-reference-images-make-scenes-order-dependent.md) is
buildable as written:

1. **Does an attachment read as a reference or as an edit?** Attach a character sheet, ask for that
   character in a new setting. If Meta returns the sheet edited, the Lead mechanism needs rethinking.
2. **Are two attachments accepted at once?** A Scene holding the Lead inside a Beat Group sends the
   Lead Sheet *and* the Establishing Shot. If only one lands, one of them has to go back to text.
3. **Does the Lead leak?** Draw an unmarked Scene in the same session and check no character appears.
4. **Which shot clauses hold the style?** Six exist. A composed layout is the recorded way to lose
   the prefix outright - a 2x2 panel grid came back watercolour with a photographic fox on
   2026-08-31 - so each shot word needs proving before it is trusted.

Record what comes back as comments beside the clauses in the config, the way every other hard-won
rule in `channel.toml` is kept.
