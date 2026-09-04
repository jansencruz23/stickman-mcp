# Reference images buy continuity by making Scene images order-dependent

The Narrative Format needs a character and a setting to survive across several Scenes, and Meta AI offers no seed, so text alone cannot hold them: a verbatim Visual Bible line holds a records room, and it does not hold one face across forty pictures. We decided to attach reference pictures to the request instead - the Lead Sheet to every Scene marked `lead`, and a Beat Group's Establishing Shot to the Scenes that follow it.

Attaching the Establishing Shot means Scene 14 cannot be drawn until Scene 12 exists. Until now every Scene's image was independent, which is what made `only_missing` resume trivial and made a redraw touch exactly one file.

## Considered Options

- **Text-only, no attachments**: keeps images independent, changes no code. Rejected - it is the mechanism already in use, and the drift it leaves is precisely what the Narrative Format cannot tolerate.
- **One thread per Beat Group, letting Meta refine the previous picture**: needs no upload at all, and the behaviour is already recorded as working. Rejected - the same recording shows Meta refining the previous picture *instead of* drawing the new prompt, so a group would inherit its establisher's composition along with its setting. Fresh thread per Scene stays.
- **A reference picture for every recurring thing**: rejected as quota. The Establishing Shot is an image the Run was drawing anyway, so reusing it as the group's setting reference costs nothing extra.

## Consequences

- A Beat Group's Establishing Shot is drawn before the rest of its group. Scene order already guarantees this, because an establisher precedes its own group.
- Regenerating an Establishing Shot leaves the Scenes drawn from it on disk, individually fine and no longer matching. `stickman_regenerate_image` returns a warning naming them, in the same shape as the stale-asset warning `stickman_save_script` already returns. It does not delete them: the creator decides.
- A reference is opt-in per Scene, never channel-wide. An attachment is a stronger instruction than a style clause, and the clause lesson - name a subject and Meta supplies one - applies with more force to a picture.
- The Illustrative Format attaches nothing and is unchanged. A Run that declares no format behaves exactly as before.
- The local SDXL backend accepts references and drops them. Narrative Runs are a Meta AI feature in practice.
