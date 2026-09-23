# How to read the screen

`python3 run.py --serve`, then open `http://localhost:8000/web/`. One HTML page and two modules, no
libraries, no build step. It reads only `out/graph.json`, served over HTTP. Everything on it is a
hypothesis drawn from transfer structure and amounts; nothing on it asserts wrongdoing.

## The layout: a case file in seven sections

A top bar with one search box ("find an account by id"), a rail on the left with seven numbered
sections, one section shown at a time.

| | Section | What it holds |
|---|---|---|
| 01 | The case in one screen | Six figures: 81 known clients, 2,248 accounts, 3,119 transfer relationships, 25 to review first (amber), 653 structures, 558 not judged. Then "Start with these accounts" (the top 3), "Start with these structures" (the top 3) and "Also in this file": the busiest day, the echo count, the 444 accounts where the crawl stopped. Every figure links into its section |
| 02 | Who to review first | The 25 ranked accounts: #, account, assessed as, priority, "the reason, in the rule's own numbers". Click a row to open the account |
| 03 | One account | The map around the selected account with a panel beside it that reads as sentences |
| 04 | Structures | The 653 formations ranked (first 80 listed; the rest are in `out/formations.csv`), each drawn on its own map with its breaking point in amber |
| 05 | Replay the month | July day by day on the hop layout |
| 06 | Amount echoes | 203 echoes, each as an in → account → out diagram |
| 07 | Where the data runs out | Boundary figures, next data requests, where centrality misleads, the removal test |

## How to answer "who do I look at first"

1. Section 01 answers it: "Start with these accounts" shows rank 1 to 3 with role and reason. Click
   one to open it in section 03.
2. For the full list, section 02. Rank 1 is the first to review; the last column is the rule's
   evidence string. The ranking is on the rules that fired, not on centrality.
3. Say it as a hypothesis: "signs of consolidation", "consistent with a funnel", never a verdict.

## How to find an account the jury names and show its links

1. Type the digits into the top-bar box. It autocompletes on the ids; the account opens once all 18
   digits are in, or when you pick a suggestion or press Enter.
2. Section 03 opens on it in "Around this account" mode. Columns, left to right: "paid the payers",
   "paid this account", "this account", "were paid by it", "were paid next". Arrows point the way
   the money moved, width is by KZT, colour is role, known clients are ringed. An account that paid
   and was paid is drawn once on the left with arrows both ways. At most 28 accounts per column are
   drawn; a note under the map says how many were left out.
3. Read the panel "This account" top to bottom: "Received X KZT from N accounts and sent Y KZT to M
   accounts in July." "Assessed as" the role, rule confidence and plain definition. "The rule fired
   on:" the evidence string. "Investigation priority": score and "#k of 2,248", or "not in the top
   25". "Position": hops and group. "What we know of it": knowledge state, confidence and limitation
   from `completeness.csv`. "Structures it belongs to": clickable chips, or "None." At hop 4 with
   nothing going out, a caveat says the crawl stopped here, not necessarily the money.
4. Toggle "Whole network": all 2,248 by hop, known clients left, hop 4 right, the selection and its
   transfers lit. Hover a node for id and role, click to select; hover a legend role for its definition.

## How to show a structure and its breaking point

1. Section 04. The left list is ranked: kind, member count, known clients, KZT through it. Click a
   row, or a chip in an account's "Structures it belongs to".
2. The map draws only the members, by hop, the breaking point ringed in amber and labelled
   "breaking point". The panel "This structure" gives the definition, counts and KZT through it, then
   "Breaking point": the id in amber and "Remove this one account and N accounts cut off" (or "N KZT
   stopped"), with the method that found it.
3. "Hypothesis to test" is the sentence to say aloud. "Arithmetic behind it:" is the evidence string.
   "Members" are chips coloured by role; clicking one opens that account in section 03.

## How to run the replay

- Section 05 is the "Whole network" hop layout, one day at a time. **Play** advances a day roughly
  every 0.7 seconds and loops; it reads **Pause** while running.
- The **day scrubber** (a slider) picks any day; beside it the date, "KZT moved", "transfers" and
  "active accounts" for that day.
- The **31-bar strip** is July's daily KZT, the current day amber. Hover a bar for its total, click to jump.
- **Trail** (on by default) fades the previous three days' arcs behind the current day.
- The busiest day is **16 July**: 23,732,052 KZT in 224 transfers, 241 active accounts. Section 01
  links straight to it. Clicking a node on the replay opens it in section 03.

## How to read an echo card

Section 06 lists 203 echoes: 135 relays, 61 splits, 7 same-amount fan-outs. The three chips turn a
kind on or off; "sort" orders by score, amount or date. Each card has:

- A diagram: payers left, the account centre, receivers right, the amount on each line. Clicking
  any dot opens that account. Under it a badge: **EXACT** (amber, 127 echoes) or **WITHIN 2%** (76).
- The kind in words: "Same amount in and out" (relay), "One amount in, split on the way out" (split),
  "Same amount to N receivers" (fan-out); the dates ("16 July, same day" or "22–23 July"); in, out
  and the 0..1 score; the evidence sentence with the figures it rests on.
- An **Open account** button, and the echo id with the full account id.

The largest is a relay of 652,000 KZT sent back to the payer the same day, 22 July. 39 of the relays
are amounts sent straight back to the payer (their evidence line says "back to"); all of those pairs
are also in `reciprocal_pairs.csv`, so a relay and a reciprocal loop can be the same money seen twice.
A relay can be rent passed on; equal amounts fanned out can be a payday. Each is a hypothesis to check
against what the transfers were said to be for.

## What the role names mean

- **consolidator:** Paid by 8 or more different accounts and keeps most of it, passing on less than
  half.
- **coordinator:** Receives from 4 or more accounts and pays 4 or more. Money moves through it in
  both directions.
- **transit:** Passes on roughly what it receives, between 80% and 120%.
- **distributor:** Pays out to 20 or more receivers.
- **terminal:** Money arrives and nothing leaves, and it sits before the crawl's edge, so the money
  appears to stay.
- **peripheral:** No rule threshold met: low activity, or a known client with only outbound
  transfers recorded.
- **abstained_boundary:** Sits at hop 4 with nothing going out. The crawl stopped here, so no
  judgement is made.
- **abstained_single_observation:** Fewer than three transfers in total. Too little to judge.

Every role is a named rule with a numeric threshold, and the evidence string in section 03 shows the
numbers the rule fired on. The two abstentions are the 558 "not judged" in section 01.

## What the structure kinds mean

- **funnel:** several accounts each send most of their outflow to one collection point.
- **chain:** money forwarded account to account, each passing on most of what arrived.
- **reciprocal_loop:** money sent and sent back, a pair or a short cycle.
- **fan_out:** one account paying many receivers that send nothing on.
- **bridge:** one account that part of a group depends on to reach the rest of the network.

## Where the data runs out

- **Tiles.** 444 accounts at hop 4 with nothing going out ("The crawl stopped, not the money"),
  1,110 dead ends the crawl did follow to their end, 19 of the 81 known clients in no transfer,
  31 known clients that sent nothing, and the share of accounts and turnover at the boundary.
- **What to ask the data owner for next.** Ranked; each says what it resolves and the KZT it lights up.
- **Where a plain centrality ranking would mislead.** Accounts that moved most between the
  centrality rank and the evidence rank, with the numbers.
- **If the top-ranked accounts were removed.** Largest group left, separate pieces, accounts still
  reachable from the known clients.

Two limits are worth saying aloud. The crawl followed outbound transfers only, so money arriving at
the 81 known clients was never followed back, and anyone directing them from above is outside this
extract by construction. And the crawl stopped at hop 4, so the hop 4 column on the right of "Whole
network" and of the replay is the edge of what was collected, not the edge of the money.
