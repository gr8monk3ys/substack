# The Playbook

What it actually takes to get big on Substack in 2026, and how the tools in this
repo map onto it.

Written for your situation: **not launched yet, building a personality rather than
a niche.**

---

## 1. The one thing you have to solve first

You said you're not targeting a niche — you're building a personality. That's a
legitimate strategy and it produces the biggest publications on the platform. It's
also the version with the highest failure rate, for a mechanical reason:

**Every discovery surface on Substack is a legibility machine.**

- A stranger scrolling Notes gives you about two seconds.
- A recommendation asks another writer to explain you to their readers in *one line*.
- The feed algorithm predicts "will this reader like this creator" from behaviour
  patterns — it needs a pattern to find.

"A bit of everything" fails all three. Not because range is bad, but because range
is invisible until someone already trusts you. Range is what you *earn*.

### The resolution: a container, not a niche

Look at Write Conscious, since it's your model. Ian Cattanach is unmistakably the
product — the voice, the face, the opinions. But the publication is not called *Ian
Cattanach*. It's called **Write Conscious**, and it sits on a legible shelf: the
literary life. Inside that shelf he does whatever he wants — philosophy, poetry,
craft, a daily podcast, a book club reading 28 novels, courses.

That's the trick, and almost nobody says it out loud:

> **Legible on the outside. Wide on the inside.**

The container is a promise a stranger can grasp in two seconds. What you put in it
is your whole personality.

**Do this first:**
```bash
./substack.py pos worksheet     # fill it in honestly
./substack.py pos build         # generates your About page + welcome post
./substack.py pos check         # stress-tests it against how strangers meet you
```

The hardest question on that worksheet is the three-obsessions one. Answer it with
what you *already* can't stop thinking about, not what you think should sell. The
throughline is whatever those three share — and it's a **question or a stance**,
never a topic list.

---

## 2. How growth actually works here now

Substack changed materially in late 2025 / 2026. The old advice is actively wrong.

### Notes is the growth engine, not the newsletter

Substack's feed no longer prioritises people you follow — most of what any reader
sees is creators they've *never* followed. Substack has said tens of millions of
new subscriptions per quarter now originate inside the app rather than from
external traffic. Writers consistently report **~60% of their subscriber growth
comes from Notes.**

Implication: your essay is the thing people subscribe *to*. Notes are the thing
that makes them find you. They are not the same job, and the note must never be a
summary of the post.

### Replies beat posting

Substack describes Notes as a **dinner party**. Broadcasting into it doesn't work;
being in conversation does. The 2026 ranking weights high-signal interactions — a
reply that adds a fact, a counter-example, or a story — well above hearts and
"love this". A reply that lands on a big writer's note puts you in front of their
audience with an implicit endorsement.

**This is the single highest-ROI hour of your day, and it's the one most people
skip because it doesn't feel like writing.**

### Restacks-with-commentary are the network signal

When you restack someone and add your own take, you tell the algorithm *these two
share an audience* — which is exactly the shape it uses to route strangers to you.
A bare restack teaches it nothing. Always add your line on top.

### Recommendations compound; virality doesn't

A viral note sends readers once. A recommendation from a peer publication sends
readers **forever**. This is the difference between a spike and a curve. Ten
recommendation partners at your size beats one lucky note, permanently.

```bash
./substack.py net targets        # where to find them
./substack.py net add --name ... # track them
./substack.py net due            # who's going cold
```

**The size rule:** aim at publications 1×–3× your size. Below that they can't move
your numbers; far above that you're invisible. Re-aim as you grow.

**The sequence that works** (and the one people get wrong):

1. Reply substantively to 3–5 of their notes over ~2 weeks. No ask.
2. Restack them once, with commentary.
3. Recommend them *first*, with no request to reciprocate.
4. *Then* send a short note. By now they know your name.

Cold-DMing a stranger for a rec swap is the most common and most useless move on
the platform.

---

## 3. Don't launch yet

The most expensive mistake available to you right now is publishing your first
post to zero followers. You get one launch. Spend it on an audience that exists.

**Two to four weeks before you publish anything:**

- Set up the profile (your face, not a logo — personality brands need a person).
- Post Notes daily. Reply constantly. Build to a few hundred followers.
- Write three posts and keep them in the drawer.
- Set five recommendations pointing at writers you actually read.

Then launch into people who already recognise your name.

```bash
./substack.py checklist                      # 11 launch items
./substack.py checklist --check notes_warm   # tick them off
```

---

## 4. The operating rhythm

This is the whole job, and it's small enough to do daily.

| Daily | Weekly |
|---|---|
| 1 original note | 1 essay, same day every week |
| 5 substantive replies | 3–5 notes pulled from that essay |
| 2 restacks with commentary | 2 new network targets engaged |
| Log the numbers | `./substack.py review` |

```bash
./substack.py plan          # what to do today, based on your actual state
./substack.py notes today   # the slate, with progress bars
./substack.py review        # the weekly loop — did any of it work?
```

**Score your notes.** A day or two after posting, record what a note actually
did (`notes score <id> --subs 6 --restacks 4`). After ~20 scored notes,
`notes best` stops being generic best-practice and starts telling you which
formulas work *for your voice and your readers* — which is the only version that
matters. Most writers never learn this about themselves because they never
write it down.

**Cadence beats volume.** Weekly, on a fixed day, forever, outperforms three posts
one week and nothing for a month. Pick the day in the worksheet and defend it.

**Write from a bank, never from a blank page.** Capture ideas the moment they
happen:
```bash
./substack.py idea add "the thing you just said out loud"
```

**Every essay is raw material for a week of notes:**
```bash
./substack.py post repurpose <draft> --queue
```

---

## 5. What to steal from Write Conscious specifically

| What he does | Why it works | Your move |
|---|---|---|
| Personality is the product, but the publication has its own name | Recommendable in one line; outlives any single topic | Name the container, not yourself |
| Named sections (Book Club, Writing School, the podcast) | Lets him be wide without looking scattered; each section is its own reason to subscribe | Define three sections in the worksheet |
| A daily podcast | Daily surface area without daily essays — audio is far cheaper to produce than prose | Consider a short audio note; talking is faster than writing |
| A book club with a published year-long reading list | Manufactures a *reason to return* and a *reason to talk to each other* | Build one recurring communal ritual |
| Strong, defended opinions | Agreeableness is invisible; disagreement generates replies | Say the thing you'd defend out loud |
| Courses / paid products | Monetises the audience beyond subscriptions | Later — not before 1,000 subs |

The deepest lesson: **he built containers, not just content.** A book club and a
"school" are things people *join*. Posts are things people read and forget. Joining
is what turns an audience into a base.

---

## 6. Milestones and what changes at each

**0 → 100.** Entirely manual. Your existing network, personally asked. Notes every
day. Nothing compounds yet; you're just proving you'll show up.

**100 → 1,000.** Notes plus recommendations. This is where the flywheel starts.
Your job is 10+ active recommendation relationships and one essay a week that's
genuinely good. Expect 6–12 months. Most people quit at month three, right before
it starts working.

**1,000 → 10,000.** Now range starts paying. You've earned the right to be
unpredictable. Add a ritual (book club, series, a recurring thread). Consider
paid — but only once free growth is reliably compounding; turning on paid too early
suppresses the growth you still need.

**Throughout: track it.**
```bash
./substack.py stats log --subs N --followers N --note "what you changed"
./substack.py stats report && open data/report.html
```

---

## 7. The honest part

Nothing here is a hack. There is no automation that gets you big on Substack —
the platform's entire ranking system is built to reward a human being having real
conversations, and it's fairly good at detecting the alternative. Bulk-posting
notes, generic replies, and rec-swap spam all measurably underperform, and the
2026 changes made that worse.

What these tools do is remove every excuse: they tell you what to do today, keep
your ideas from evaporating, turn one essay into a week of distribution, stop your
relationships from going cold, and show you whether any of it is working.

The writing and the conversations are still yours.

---

### Sources

- [The Complete Guide to Substack Notes in 2026 — Sarah Fay](https://www.substackwritersatwork.com/p/the-new-substack-notes-algorithm-2026)
- [Substack Notes Strategy 2026 (60% of my growth)](https://thrivewithcarrie.substack.com/p/substack-notes-strategy-2026)
- [Substack Just Changed How Notes Show Up in Feeds](https://escapethecubicle.substack.com/p/substack-just-changed-how-notes-show)
- [Substack Algorithm Changes in January 2026](https://lintra.substack.com/p/substack-algorithm-changes-january-2026)
- [How to Grow on Substack Fast in 2026](https://writebuildscale.substack.com/p/how-id-grow-on-substack-fast-in-2026)
- [How to Get Your First 100 Subscribers](https://pubstacksuccess.substack.com/p/how-to-get-your-first-100-subscribers)
- [5 Steps To Launch A New Substack From Scratch In 2026 — Dickie Bush](https://dickiebush.substack.com/p/5-steps-to-launch-a-new-substack)
- [Write Conscious](https://writeconscious.substack.com/) · [Ian Cattanach on Substack](https://substack.com/@iancattanach)
- [Substack: how to export your email list](https://support.substack.com/hc/en-us/articles/6314498343700-How-do-I-export-my-email-list-on-Substack) · [how to export your posts](https://support.substack.com/hc/en-us/articles/360037466012-How-do-I-export-my-posts)
