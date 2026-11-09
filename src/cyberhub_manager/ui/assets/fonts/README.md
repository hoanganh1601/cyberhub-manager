# Bundled desktop fonts

Inter (400, 700) and Space Grotesk (400, 700) are distributed under their included
SIL Open Font Licenses. These static TrueType files are loaded privately for the
current process by CustomTkinter; users do not need to install fonts manually.

The original subsets came from the Google Fonts CSS API. Current full fonts
come from the official Google Fonts repository, as pinned below. Licenses:
`ofl/inter/OFL.txt` and `ofl/spacegrotesk/OFL.txt` (line endings/trailing spaces
normalized locally; license wording unchanged).

## Vietnamese coverage fix — 2026-11-09

The original binaries contained only 230 mapped characters (Latin subset),
missing Vietnamese letters such as ă, đ, ư, ệ and ợ. Browsers mixed system
fallback fonts into the same sentence. All four files now contain the full
upstream character set, including Vietnamese precomposed and combining forms.

Upstream Google Fonts revision: `5bb28733cec313b63fbd415b574b5ae35c8aa8b8`.

- `ofl/inter/Inter[opsz,wght].ttf`, SHA256
  `29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031`.
- `ofl/spacegrotesk/SpaceGrotesk[wght].ttf`, SHA256
  `acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72`.

Static 400/700 instances were generated with FontTools 4.62.1 using
`instantiateVariableFont(..., updateFontNames=True)`, pinning `wght` to the
target weight and every other axis to its default (Inter `opsz=14`). No glyph
subsetting was applied. Matching upstream SIL OFL licenses are included.
FontTools is a maintenance tool, not an application/runtime dependency.

Verification checks all U+1EA0–U+1EF9 characters, Vietnamese base letters and
their Unicode NFD forms. The real-browser preview test also checks rendered
fonts via Chrome DevTools. Inter/Space Grotesk are the only application and
assistant fonts. Web asset URLs include a cache version.

The Login and assistant use Inter for body/input text and Space Grotesk for
headings/labels, matching the original application typography. All login icons
and circuits are drawn locally.
