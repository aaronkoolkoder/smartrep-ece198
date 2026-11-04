# SmartRep app design direction

Research reviewed November 3, 2026. This direction applies to the Expo participant app and instructor dashboard when those milestones are built.

## Reference products

- [Hinge Health](https://www.hingehealth.com/): the product centers a personal plan, guided exercise, real-time movement feedback and progress in one app. Use that emphasis for Today's plan and the live set.
- [Omada Health](https://www.omadahealth.com/): the member experience emphasizes personal programs and accessible support. Use a reassuring welcome, plain language and a visible Ask staff action.
- [Sword](https://sword.com/): its care experience pairs guided sessions and real-time feedback with clinician oversight. Keep participant screens focused on the current movement while staff get the broader progress view.

These are product references. The palette, spacing and component choices below are SmartRep's design decisions, not claims about these companies' exact design systems. Do not copy logos, screenshots, clinical claims or proprietary assets into the app.

## Visual direction

Use a warm ivory canvas, white surfaces, dark evergreen text and a strong green primary action. Pale sage supports progress information. Amber and red communicate adjustments and problems, always accompanied by an icon and words. This should feel calm, welcoming and carefully made.

Use the platform system sans-serif with generous line spacing. Body text starts at 18, headings at 28–36 and the live rep counter at 112. Respect system font scaling; labels wrap rather than truncate. Give controls at least 56 points of height. Use an 8-point spacing rhythm and restrained 16–24 point corner radii. Keep shadows subtle and avoid decorative gradients and distracting motion during exercise.

The initial contrast pairs are dark text #173C36 on white/ivory, white on primary #24634F, dark amber #805100 on #FFF1CC, dark red #A02E2E on #FCE8E6. Verify rendered screen contrast and largest font settings in M5.

## Participant screens

Home: a personal greeting, today's prescribed exercise plan, a clear completed/remaining summary, and one prominent Scan a station action. Show exercise names, sets, reps and load in separate readable lines. Progress reflects the prescribed dose rather than encouraging extra reps.

Station exercises: equipment name and load first, then matching prescribed exercises. A selected exercise shows a single Start set action. Empty and unavailable states explain what to do next.

Live set: exercise and set number at top, a dominant rep counter, target range underneath, and a large feedback panel with icon and label. Use “Good rep”, “Go a little further”, and “Slow down”. Show a small quiet signal trace as secondary information. Keep Finish set anchored within the safe area. The counter and words must be readable from a phone stand about one metre away.

Summary: completed reps, good/short/rushed counts, measured motion range and the next prescribed action. Never imply that a measured range proves medical safety or correct form.

Connect, sign-in and staff calibration: short steps with one main action and specific recovery messages. Preserve the brief's QR connection, six-digit ID and PIN flows. Don't add an unrelated onboarding funnel.

## Instructor dashboard

Use the same colors and typography with denser desktop spacing. Lead with session overview, then participants needing attention and a searchable participant list. Status has an icon plus text. Keep device health separate from participant progress. Set history opens on selection. Support a narrow layout without hiding warnings or actions.

## Implementation contract

Shared Expo tokens live in `app/src/design/theme.ts`. Build reusable screen, button, text, progress and status components around them in M5. During M4, mirror these tokens in CSS. Test all states with keyboard/focus support on web, screen-reader labels, large text, reduced motion, and status feedback that does not depend on color or sound alone.

## Additional reference review

Reviewed [21st dashboard components](https://21st.dev/community/components/explore/dashboard-component), [Mito Health](https://mitohealth.com/) ([YC profile](https://www.ycombinator.com/companies/mito-health)), and [Modern Health](https://www.modernhealth.com/) ([YC profile](https://www.ycombinator.com/companies/modern-health)). The app applies component hierarchy and compact navigation from the dashboard references, and clear leading messages and prominent primary actions from the health company homepages. The visual revision adds an evergreen feature panel, a sage action, restrained inset borders, larger editorial typography, a collapsible desktop rail and subtle hover states. Keep these patterns consistent across participant and staff views. Original SmartRep copy, icons and layout remain in the repository; no third-party component source or brand imagery was imported.

## Current visual system

The user-supplied Claymorphism brief supersedes the earlier evergreen visual direction for the browser UI. Authoritative color, type, radius and interaction tokens are implemented in `bridge/static/clay.css`, loaded after the existing stylesheet. Instrument Sans is self-hosted under the family alias Claymorphism Instrument. Pink feature cushions, cream grouped trays and mint/lavender/yellow/blue objects use consistent upper-left lighting. Existing content, routes, backend, keyboard focus and reduced-motion behavior are preserved. The Expo native app retains its existing styling; this visual pass targets the browser participant app and dashboard.
