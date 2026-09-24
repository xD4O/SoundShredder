# AudioShake: ideas for SoundShredder

Research date: September 24, 2026. Reviewed official product and developer documentation; no account, paid processing or media upload was used.

## What the documentation shows

AudioShake presents film/TV separation through concrete production jobs: recovering dialogue, music and effects; preparing dubbing material; replacing music; and recovering stems from mixed archives. Its examples let visitors audition the mix and separated components. It also describes web tools and API/SDK delivery. These are documented capabilities, not a quality benchmark we performed. [Film and TV workflows](https://www.audioshake.ai/film-tv)

Its multi-speaker API separately provides aligned individual-speaker tracks, including overlapping speech, speaker-timing metadata and an optional background track. Speaker count can be inferred or supplied. [Multi-speaker separation documentation](https://developer.audioshake.ai/multi-speaker-separation)

## Our takeaways

- **Lead with the job.** Quick Cleanup offers familiar choices; Target a Sound guides a particular repair. Users should not need model names to choose a workflow.
- **Make the change audible.** Input, cleaned and removed playback should help users judge results alongside the footage.
- **Keep attempts recoverable.** Short previews and saved versions encourage comparison before export.
- **Keep claims specific.** Our prompt names a sound for AudioSep. It does not provide individual-speaker separation. The reviewed AudioShake pages do not establish an equivalent free-text removal interface.

Individual-speaker separation is possible future research requiring a separate engine evaluation and interface. It is outside this release scope. SoundShredder's prototype keeps text and media processing local; no AudioShake integration or quality parity is claimed.
