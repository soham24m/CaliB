# Design notes

## Brand system

The dashboard uses California Burrito's red (`#E31F2D`), deep red (`#B8231A`), forest green (`#2F4F3A`), cream (`#FFECCD`), and white for focus treatment. Cream is the page canvas; cards use cream and green outlines; red and green are reserved for emphasis and surfaces. The official logo is stored locally in `public/images/logo.png`. Gabarito is used for the brand's bold, uppercase display style. Font weights are served locally from `public/fonts/` with `font-display: swap`; weight 700 is preloaded, and the font OFL license is included.

The palette is intentionally restricted to keep data views visually consistent with the restaurant brand and to avoid assigning unrelated hues to chart categories. Chart series reuse red, green, deep red, and token-derived tints. Weekday/hour intensity uses cream-to-red with a green peak outline.

## Contrast checks

Relative luminance contrast (WCAG formula):

- Cream on red: **4.03:1**. This is close to the 4.5:1 AA threshold for normal text, so small text uses deep red instead; cream text is reserved for bold 20px+ labels and large KPI values, while KPI notes use green-on-cream chips.
- Cream on forest green: **7.88:1**, above the 4.5:1 AA threshold for normal text.
- Green on cream: **7.88:1**, above the 4.5:1 AA threshold for normal text.

Keyboard focus uses a visible cream outline on red/green surfaces and a red-tinted ring for filter controls on cream. Reduced-motion preferences disable decorative animation.

The About section uses the supplied portrait and education history; image is stored locally with the rest of the public site assets.
