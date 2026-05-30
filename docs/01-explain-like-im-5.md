# 1 · Explain Like I'm 5

## The big analogy: a smart shop assistant in a giant test shop

Imagine a **huge shop** that sells 377 different "tests". Each test measures
something about a job candidate — some test if you can code in Java, some test
your personality, some test if you're good with numbers.

A customer walks in and says: *"Umm... I'm hiring someone, I need a test."*

A **bad** shop assistant would immediately grab 10 random boxes and say "here!"
A **good** shop assistant does this instead:

1. **Listens and asks back.** "Sure! What job is it for? What do you want to
   find out about the person?" → this is **Clarify**.
2. **Walks to the right shelves.** Once they know it's a "Java developer", they
   walk to the *Java* and *coding* shelves, not the cooking shelf. → this is
   **Retrieval**.
3. **Picks the best few boxes** and explains why each one fits. → **Recommend**.
4. **Changes the pile if you change your mind.** "Oh, also add a personality
   test" → they keep the Java tests and *add* a personality one. → **Refine**.
5. **Compares two boxes** if you ask "what's the difference between these two?"
   — reading the labels, not making things up. → **Compare**.
6. **Says no nicely** if you ask something silly like "what's the weather?" —
   "Sorry, I only help with tests here." → **Refuse**.

Our software **is that shop assistant.** That's the whole idea.

## Who are the helpers behind the assistant?

The assistant is actually a small team:

- **The Catalog** 📒 — a notebook listing all 377 real tests (names, web links,
  what each measures). The assistant is **only allowed to recommend things
  written in this notebook** — so it can never make up a fake test.
- **The Finder (Retrieval)** 🔎 — a fast helper who, given the customer's words,
  flips to the most likely pages of the notebook and hands over ~30 candidate
  tests. It works purely on matching words, so it's instant and never lies.
- **The Brain (the LLM / AI)** 🧠 — the part that actually *talks*: it decides
  whether to ask a question, which of the 30 candidates truly fit, and writes
  the friendly reply. You plug in your own free AI key to power this brain.
- **The Doorman (the API / FastAPI)** 🚪 — stands at the door, takes the
  customer's message, passes it to the team, and hands back the answer in a
  very strict envelope shape that the examiner (SHL's robot grader) expects.

## Why split the work between the Finder and the Brain?

Because they're good at *different* things:

- The **Finder** is fast, free, and **honest** (it only returns real catalog
  items) but it's "dumb" — it just matches words.
- The **Brain** is smart and conversational but **expensive and sometimes
  makes things up** (it could invent a test that doesn't exist).

So we let the Finder do the honest searching, and the Brain only **chooses from
what the Finder found** and writes nice sentences. The Brain is never trusted to
invent test names or web links — we always look those up in the notebook again.
This is the single most important trick in the whole project.

## One step deeper (still simple)

Every time the customer says something, the **whole conversation so far** is
handed to the doorman again — the shop keeps *no memory* between visits. This is
called being **stateless**. It sounds wasteful, but it's actually great: any
copy of the shop can serve any customer, nothing breaks if one shop restarts,
and the examiner can replay conversations easily.

There's also a **timer**: the conversation can only be 8 messages long. So the
assistant is trained to *not* ask too many questions — if it's running out of
time, it stops asking and just gives its best shortlist.

➡️ Next: [Architecture](02-architecture.md) — see the actual pieces and arrows.
