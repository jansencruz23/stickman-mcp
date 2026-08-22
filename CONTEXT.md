# Stickman Video Production

Turns a creator's topic idea into a narrated stickman explainer video for YouTube. Claude (the MCP host) does the creative work; MCP tools do the mechanical work.

## Language

### Production

**Run**:
One end-to-end production of a single video from a Topic. Every artifact a Run produces belongs to that Run.

**Topic**:
The one-line idea the creator supplies. The sole creative input to a Run.
_Avoid_: idea, subject

**Checkpoint**:
A human approval gate inside a Run. Two exist: Script Approval and Image Review.

**Yolo Mode**:
A Run option that skips all Checkpoints.

**Video Package**:
The final deliverables of a Run: the video file, subtitles, and upload metadata (title, description, tags).
_Avoid_: output, export

### Script & Scenes

**Script**:
The complete narration of a video, authored from the start as an ordered list of Scenes. There is no free-flowing prose that gets split later.
_Avoid_: transcript, story

**Scene**:
The atomic unit of a video: one Narration passage paired with one Image Prompt, shown as a single still image for roughly 7–10 seconds.
_Avoid_: segment, slide, cut

**Narration**:
The spoken text of one Scene, typically 3–4 sentences.

**Narration Clip**:
The synthesized audio of one Scene's Narration. Its length *defines* the Scene's duration — durations are never derived by transcribing audio.
_Avoid_: timestamp

**Image Prompt**:
The text describing a Scene's still image. Always carries the Style Prefix plus any Visual Bible entries it references.

**Style Prefix**:
The fixed prompt fragment that gives every image the channel's uniform stickman look, across all Scenes and all videos.

**Visual Bible**:
A Run's canonical one-line descriptions of recurring characters or settings, repeated verbatim in every Image Prompt that mentions them.

**Illustrative Format**:
The channel's format: each Scene is a standalone visual metaphor for its Narration. No visual continuity is promised between Scenes.
