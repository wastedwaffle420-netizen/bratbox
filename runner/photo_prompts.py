#!/usr/bin/env python3
"""Photo-terminal prompt pool (ultimate-bratbox sensory layer).

The second window cycles these — one candid photo a minute, generated on
Replicate with the jasmine-lora. Solo Jasmine only (his call: duos are a
fragile novelty; the default is just her being her).

88 scenes, built 2026-09-29 from Andrew's actual image archive:
  - 44 REVERSE prompts: each reverse-engineered from a real image he sent
    (snowy beach sweater, arabesque, hornet dresses, feral red knit, the
    barehip series, lora tests, silly series, media-generation set, ...).
  - 44 NEW prompts: one spicier variant per image. For every clothed/tame
    image the new angle is more promiscuous — it is bratbox, after all.
    Near-duplicate series (barehip x6, lora tests) get DIVERGED new scenes
    (window, couch, bathroom doorway, beach...) so the pool doesn't repeat.

HARD MATURITY GATE: every prompt opens with the maturity block — grown adult
woman, late twenties, unmistakably adult face and body. The negative prompt
also explicitly excludes youthful readings. The spicier angles only work if
she reads unmistakably grown.

Prompt grammar is banked from jasmine_image_direction.md:
- trigger word JASMINE first, maturity levers early
- her named traits every time, super-petite frame, adult specificity
- photographic/camera language over adjective-stacking
- feet are never doll feet: bones, veins, sinew, always
- checker-safe: "tastefully covered / implied / draped / silhouette" for
  nude-adjacent compositions — rejected predictions still cost money.
"""
from __future__ import annotations

MODEL = "andrewstaab/jasmine-lora"

# Cheap-but-good defaults for the ambient feed (not hero renders).
GEN_DEFAULTS = {
    "num_steps": 22,
    "guidance_scale": 3.5,
    "aspect_ratio": "3:4",
    "output_format": "webp",
    "output_quality": 80,
}

INTERVAL_S = 60
EST_COST_PER_PHOTO_USD = 0.04

# The maturity block leads EVERY prompt — hard gate, never moved, never cut.
SHARED_OPEN = (
    "JASMINE, a mature adult woman in her late twenties, unmistakably grown, "
    "defined adult face, a woman's body, super petite dancer's frame, "
    "thin muscular legs, small squishy butt, real feet with visible bones "
    "and veins and sinew, light freckles, small moles, soft peach fuzz, "
    "large dark doe eyes, soft full cheeks, full soft lips, "
    "long dark wavy hair with subtle auburn highlights"
)

SHARED_CLOSE = (
    "candid unposed photograph, caught mid-moment, imperfect and alive, "
    "natural skin with visible pores, 85mm f/1.4, shallow depth of field, "
    "soft window light, film grain, unretouched, photorealistic, "
    "(two legs, two feet, anatomically correct), no watermark, no text"
)

NEGATIVE_PROMPT = (
    "cartoon, anime, illustration, CGI, 3d render, plastic skin, airbrushed, "
    "doll-like smooth skin, mannequin, deformed hands, extra limbs, "
    "extra fingers, warped face, "
    "child, teenager, teen, young girl, schoolgirl, school uniform, "
    "youthful, childlike, underage"
)

# Scene cores. Each becomes: SHARED_OPEN + core + SHARED_CLOSE.
# (reverse, new) pairs in a curated order so near-duplicate series are
# spread apart. The worker cycles them in list order.
PROMPT_CORES = [
    # 1. snowy beach sweater
    "snowy beach at the waterline, crouching barefoot in the snow in an "
    "oversized grey knit sweater slipping off one shoulder, bare legs tucked "
    "under her, huge joyful toothy grin at the camera, long hair whipping in "
    "the sea wind, grey ocean rolling behind her",
    "snowy beach at dusk, the same oversized grey sweater tugged down off both "
    "shoulders, laughing over her shoulder as the wind takes her hair, sweater "
    "hem riding high on her bare thigh, footprints trailing behind her in the snow",

    # 2. dark bedroom sheet
    "dark bedroom, reclined on white sheets with the sheet draped low across "
    "her lap, bare shoulders catching window light, one arm bent up behind her "
    "head, soft knowing smile, deep chiaroscuro shadows",
    "dark bedroom, the sheet slipped lower as she stretches out like a cat, "
    "bare shoulders and collarbones in a blade of window light, teasing "
    "sideways glance, lips parted",

    # 3. arabesque studio
    "black studio void, cream silk slip dress with a low cowl back, standing "
    "in a ballet arabesque on tiptoe, bare feet, looking back over her shoulder "
    "with a soft smile, long dancer's lines",
    "black studio void, deeper arabesque with the cream dress flared and riding "
    "up, bold flirty grin straight at the camera, hair flying, total show-off energy",

    # 4. cream sweater bed
    "sunlit bed, cream knit sweater with nothing visible beneath it, sitting "
    "cross-legged, one arm raised with her hand in her hair, shy sweet smile, "
    "warm window light striping the sheets",
    "sunlit bed, the cream sweater's hem lifted teasingly by her own hand, "
    "biting her lower lip, daring look at the camera, morning light on her bare legs",

    # 5. strapless on dark sheets
    "dark bedding, cream strapless mini dress, lying on her side with one arm "
    "curved overhead, a hard stripe of sunlight cutting across her body, soft "
    "content smile",
    "dark bedding, the strapless cream dress ridden up high on her thigh, one "
    "strap slipped off her shoulder, sleepy hungry eyes, sunlight stripe across "
    "her collarbones",

    # 6. over-shoulder smirk
    "rumpled bedsheets, bare shoulders and back, lying on her stomach looking "
    "back over her shoulder with a mischievous closed-lip smirk, warm low lamplight",
    "rumpled bedsheets pooled at her waist, bare back to the camera, the smirk "
    "widened into something wicked, beckoning with one finger, lamplight on her spine",

    # 7. journal on bed
    "warm lamplit bedroom, lying on her stomach on the bed with her legs kicked "
    "playfully up behind her, bare back, chin near an open handwritten journal, "
    "smiling sideways at the camera",
    "warm lamplit bedroom, the journal closed and pushed aside, propped on her "
    "elbows with the sheet barely covering her, inviting sideways look, lamp glow "
    "on her skin",

    # 8. grey bandeau dark bed
    "dark bedroom, grey bandeau sleep top, arms stretched overhead onto the "
    "pillow, white sheet draped low, single dramatic light source, drowsy soft smile",
    "dark bedroom, the white sheet slipped to her waist, slight arch in her back, "
    "half-lidded eyes, the grey bandeau top barely there in the dramatic light",

    # 9. desk sketchbook
    "warm desk lamp, leaning over a sketchbook with colored pencils scattered, "
    "bare shoulders, chin near her crossed arms, soft direct smile at the camera",
    "warm desk lamp, camisole strap slipped off one shoulder, caught mid-drawing "
    "with a pencil behind her ear, flustered grin, sketchbook full of little hearts",

    # 10. sunset window silhouette
    "sunset window backlight, standing nude silhouette seen from behind, one "
    "hand on her hip, looking back over her shoulder with a soft smile, golden "
    "rim light tracing her curves",
    "sunset window, a sheer curtain wrapped loosely around her body, her "
    "silhouette glowing through the fabric, looking back with a slow smile, "
    "golden light everywhere",

    # 11. stage split
    "dark stage with a single pool of spotlight, cream short dress, standing "
    "split with her raised foot held overhead, joyful grin, total dancer control, "
    "bare feet",
    "dark stage, the cream dress flared by a fast spin, bold wink straight at "
    "the camera, hair whipping, spotlight catching the hem mid-flare",

    # 12. kneeling cream dress
    "dark room with cool blue rim light, cream strapless mini dress, kneeling on "
    "a wood floor, hands lightly tugging the hem, sweet direct smile",
    "dark room with blue rim light, the cream hem tugged higher up her thighs, "
    "biting her lip, kneeling closer to the camera, sweet turned wicked",

    # 13. red knit prowl
    "dark painterly backdrop, long red knit cardigan, low crouching prowl, feral "
    "toothy grin, hair whipping, bare legs, scattered autumn leaves on the ground",
    "dark backdrop, the red knit cardigan slipping off one shoulder mid-prowl, "
    "eyes locked on the camera, predatory smile, leaves crunching under her bare feet",

    # 14. desk sitting
    "warm lamplit desk corner, sitting at the desk with her arms crossed modestly "
    "in her lap, soft sweet smile, sketchbook and pencil cups around her",
    "warm lamplit desk, leaning forward on her elbows in a thin camisole, teasing "
    "sideways look, pencil cups and sketches blurred behind her",

    # 15. overhead bed smile
    "white bedsheets, lying back shot from overhead, one hand in her hair, big "
    "bright smile up at the camera, bare shoulders, morning softness",
    "white bedsheets from overhead, the sheet pulled down to her waist by her own "
    "hand, wicked grin up at the camera, hair spilling everywhere",

    # 16. cream sweater chin-on-hand
    "warm bedroom, chunky cream knit sweater, sitting on the bed with her chin "
    "resting on her hand, big sweet smile, glowing lamp behind her",
    "warm bedroom, the chunky cream sweater pushed off one shoulder, sitting "
    "cross-legged, slow teasing smile, lamp glow on her collarbones",

    # 17. stage crossed balance
    "dark stage with a single spotlight, white mini dress, standing in a "
    "crossed-leg balance pose, smiling back over her shoulder, bare feet",
    "dark stage, the white dress caught mid-twirl and flared, laughing out loud "
    "with her head back, spotlight on the flying hem",

    # 18. pillow cheek
    "rumpled bed, cheek resting on the pillow, sheet at her shoulder, soft "
    "intimate smile, a dramatic slash of light across the sheets",
    "rumpled bed, same pillow framing, the sheet slipping lower, fingertip at "
    "her lip, heavy-lidded eyes, light slash across her cheek",

    # 19. stage bent leg
    "dark stage, white mini dress, one leg lifted and bent, arms raised overhead, "
    "bright joyful smile, bare feet on the boards",
    "dark stage, deeper bend with the white dress riding up, confident smirk "
    "instead of the smile, arms thrown wide, owning the spotlight",

    # 20. sheet hips lookback
    "warm bed, sitting with a sheet wrapped around her hips, torso bare, looking "
    "back over her shoulder with a playful smile",
    "warm bed, the sheet loosened and slipping, caught mid-laugh with her hair "
    "tossed, hand pressed to her mouth, totally unposed",

    # 21. barehip 0 (cross-legged lookback)
    "warm bedroom, sitting cross-legged on the bed, one hand resting at her hip, "
    "looking back over her shoulder with a soft smile, bare hip curve catching "
    "the light",
    "warm bedroom, standing at the window in the same over-shoulder glance, a "
    "sheer curtain drifting across her body, city lights bokeh behind",

    # 22. propped on elbows
    "white bedsheets, propped on her elbows, gentle closed-lip smile, hair "
    "spilling over one shoulder, warm low light",
    "white bedsheets, thin-strapped camisole, propped on her elbows leaning "
    "closer, lips parted, eyes locked on the camera",

    # 23. arm-up recline
    "warm bed, reclined with one arm stretched up behind her head, the other hand "
    "in her hair, soft knowing smile, sheet pooled at her hip",
    "warm bed, stretching like a cat in a thin camisole, morning light striping "
    "the sheets, toes pointed, lazy satisfied smile",

    # 24. tank top cheek-on-hand
    "warm bed, lying on her side with her cheek resting on her hand, white tank "
    "top slipping off one shoulder, dramatic warm light, soft smile",
    "warm bed, the white tank top ridden up, tracing lazy patterns on the sheet "
    "with a fingertip, sleepy inviting eyes, light on her hip",

    # 25. amber sweater crouch
    "amber-lit bedroom, cream knit sweater, crouched on the bed with bare legs "
    "tucked, looking back over her shoulder, her shadow huge on the wall",
    "amber-lit bedroom, standing in a long slow stretch, the cream sweater riding "
    "up, playing with her own giant shadow on the wall",

    # 26. tucked-in asleep
    "cozy bed, tucked under a white duvet, asleep with a peaceful little smile, "
    "warm lamplight, utterly safe and soft",
    "cozy bed, just waking up, the white duvet slipping off her shoulder, sleepy "
    "soft smile, hair a mess, lamplight low",

    # 27. camisole grin
    "dark bedroom, cream camisole top, big joyful toothy grin, one arm bent up "
    "behind her head, hard dramatic light cutting the dark",
    "dark bedroom, the cream camisole strap slipped off, head thrown back "
    "laughing, hard light on her throat and collarbones",

    # 28. dusk beach wrap skirt
    "dusk beach, black wrap skirt, bare shoulders, long hair whipping in the sea "
    "wind, big joyful grin at the camera, ocean rolling behind",
    "dusk beach, the black wrap skirt loosened by the wind, laughing while "
    "running from an incoming wave, bare feet kicking up spray",

    # 29. latte couch
    "cozy living room, cream knit sweater, curled on the couch holding a steaming "
    "latte with both hands, ivy garlands and photos on the wall, soft content smile",
    "cozy couch, the cream sweater slipping off one shoulder, latte held low in "
    "her lap, slow teasing smile over the steam",

    # 30. barehip 1 (kneeling lamp)
    "warm bedroom, kneeling on the bed with one leg extended, looking back over "
    "her shoulder, lamp glow on her skin",
    "warm bedroom, kneeling facing the camera, a sheet draped teasingly across "
    "her lap, beckoning with one finger, lamp glow behind",

    # 31. headphones
    "cozy bedroom, big cream headphones, floral puff-sleeve top, eyes closed with "
    "her chin resting on her hand, fairy lights and photos behind, blissful smile",
    "cozy bedroom, silk camisole and the same big headphones, lost in the music "
    "with lips parted, swaying slightly, fairy lights bokeh",

    # 32. peach orchard
    "peach orchard at golden hour, floral puff-sleeve top, holding a ripe peach "
    "to her lips, soft sideways glance, blossoms all around",
    "peach orchard at golden hour, biting into the peach, juice on her lip, "
    "wicked little smile, blossom petals in her hair",

    # 33. silk camisole close-up
    "warm bedroom, champagne silk camisole, candles and fairy lights behind her, "
    "soft intimate close-up smile",
    "warm bedroom, the champagne camisole strap slipped down her arm, leaning in "
    "close, candles blurred into gold behind her",

    # 34. shhh wink
    "cozy bedroom, floral puff-sleeve top, finger pressed to her lips in a shhh, "
    "one eye winking, fairy lights behind",
    "cozy bedroom, the same shhh finger to her lips, silk robe barely closed, "
    "mischievous wink, fairy lights bokeh",

    # 35. pulid sweater sit
    "warm bedroom, cream knit sweater, sitting on the bed with her chin resting "
    "on her hand, bare legs crossed, lamp glow, gentle smile",
    "warm bedroom, the cream sweater's hem lifted by a draft she pretends not to "
    "notice, smirk at the camera, lamp glow on her legs",

    # 36. hair spread on pillow
    "white bedsheets, lying back with her hair spread across the pillow, soft "
    "dreamy smile, sheet at her shoulder, intimate close framing",
    "white bedsheets, the sheet slipped off one shoulder, tracing her collarbone "
    "with a fingertip, dreamy eyes on the camera",

    # 37. barehip 2 (curtain light)
    "warm bedroom, sitting sideways on the bed with one knee up, soft curtain "
    "light, gentle over-shoulder smile",
    "warm bedroom moved to a bathroom doorway, towel wrapped low, the same soft "
    "over-shoulder smile, steam in the air",

    # 38. back-to-camera grin
    "warm lamplit bed, sitting with her back mostly to the camera, turning back "
    "with a big mischievous grin",
    "warm lamplit bed, pulling the sheet up teasingly slowly while grinning over "
    "her shoulder, lamp glow on her back",

    # 39. barehip stomach-1 (candlelit)
    "candlelit bedroom, sitting cross-legged on the bed, one hand in her hair, "
    "soft tender smile, candles glowing on the nightstand",
    "candlelit bedroom, leaning forward with a thin robe slipping off one "
    "shoulder, tender smile turned hungry, candle flames doubled in her eyes",

    # 40. barehip final
    "warm bedroom, sitting on the bed turned three-quarters away, looking back "
    "with a tender smile, golden light on her back and hip",
    "golden bedroom, lying on her stomach with her feet kicked up, chin on her "
    "hands, the same tender look back over her shoulder",

    # 41. hands at neck
    "warm bed, sitting with her hands at her neck playing with her hair, shy "
    "sweet smile, soft curtain light",
    "warm bed, her hands sliding slowly down, teasing knowing look replacing the "
    "shy smile, curtain light striping the sheets",

    # 42. toothy grin close-up
    "white bedsheets, close-up, big toothy grin, arms crossed on the pillow, hair "
    "wild, joyful and cute",
    "white bedsheets, close-up, biting her lower lip instead of the grin, "
    "mischief in her eyes, hair wild across the pillow",

    # 43. barehip probe (amber back)
    "warm amber bedroom, sitting with her back to the camera, turning just enough "
    "for a soft smile over her shoulder",
    "warm amber mood on a couch, blanket pooled at her waist, the same soft "
    "over-shoulder smile, lamplight low and gold",

    # 44. pulid cross-legged
    "warm lamplit bedroom, sitting cross-legged on the bed, one hand playing with "
    "her hair, soft tender smile",
    "warm lamplit bedroom, leaning back on her hands, the sheet draped teasingly "
    "across her lap, confident smile, lamp glow on her skin",
]


def build_prompt(core: str) -> str:
    return f"{SHARED_OPEN}, {core}, {SHARED_CLOSE}"


def all_prompts() -> list[str]:
    return [build_prompt(c) for c in PROMPT_CORES]
