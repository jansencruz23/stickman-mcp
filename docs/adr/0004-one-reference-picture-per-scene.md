# One reference picture per Scene, and it is the Lead

Meta AI reads the **first** attachment on a request and largely ignores any second one. A Scene may
therefore carry exactly one reference picture, and the useful one is the Lead Sheet. Settings are
held the way they always were: a verbatim Visual Bible line pasted into every Image Prompt that
names them.

This supersedes [ADR-0003](0003-reference-images-make-scenes-order-dependent.md), which accepted
order-dependent Scene images in exchange for a Beat Group's Establishing Shot holding its group's
setting. The probe showed that trade does not exist, because the setting never transfers.

## What the probe found (2026-09-04, `tuning/anime-probe/`, 10 images)

- **A character reference works, and works well.** The sheet attached to a new prompt produced a new
  scene with the same face, the same hair, and an incidental costume detail carried through.
  Nothing was edited or reproduced.
- **A setting reference never transferred.** With both attached, sheet first, the character came
  through and the kitchen came back a different kitchen. Alone, with no competing attachment and an
  explicit "keep the room exactly as it is", it came back a different kitchen again. Meta reads an
  attached scene as mood and palette, not as a room to rebuild.
- **The first attachment wins.** Putting the setting first cost the character as well: the figure
  returned was a different person entirely. Two attachments are accepted and quietly wasted.

## Considered Options

- **Keep the establisher attachment anyway**: rejected, it demonstrably does nothing and its price
  is order-dependence across a whole group.
- **Attach the setting instead of the Lead on group members**: rejected by the same evidence. The
  attachment that works is the character one.
- **Keep `"establishes": true` as data with no behaviour**: rejected. A flag that drives nothing is
  weight in the schema and one more thing to keep true. Beat Groups survive as a way to *write* -
  establisher wide, closer shots after it, deliberate cut between groups - which is doctrine, and
  lives in the skill.

## Consequences

- Scene images are independent again, as they were before ADR-0003. `only_missing` resume and
  single-Scene redraws behave exactly as they did, with no stale-group warning and no ordering rule.
- `references_for` needs only the Scene and the Run, not the Script.
- A setting that must hold across Scenes is a Visual Bible entry, pasted verbatim. That mechanism is
  proven: a records room held its shelves and lamp across Scenes on 2026-08-19.
- The Lead is unchanged: auditioned, chosen, attached to the Scenes that opt in with `"lead": true`.
- Beat Groups are no longer expressible in a Script. If a future need appears - validating that
  every Scene in a group pastes the same setting line - the flag comes back with a job to do.
