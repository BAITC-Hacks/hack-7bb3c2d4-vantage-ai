# How to read the screen

`python3 run.py --serve`, then open `http://localhost:8000/web/`. One HTML page and three modules, no
libraries, no build step. It reads only `out/graph.json`, served over HTTP. Everything on it is a
hypothesis drawn from transfer structure and amounts; nothing on it asserts wrongdoing. It opens in
Russian; a RU/KZ/EN switch in the top bar changes the language and remembers the choice, and a
Light/Dark toggle sits beside it. Evidence strings, hypotheses and reasons are pipeline English, shown as is.

Terms used throughout: a **listed account** is one of the 81 named by law enforcement. A **hop** is
the number of transfers away from a listed account. A **linked account group** is a set of accounts
the rules found moving money together (`out/formations.csv`). A group's **key account** is the one
whose removal disconnects the most members. **Matching amounts** are sums that leave an account the
way they arrived (`out/echoes.csv`).

## The layout: seven numbered sections

A top bar with one search box ("find an account by id"), a rail on the left with seven numbered
sections, one section shown at a time.

| | Section | What it holds |
|---|---|---|
| 01 | Overview | Six figures: 81 listed accounts, 2,248 accounts, 3,119 transfer relationships, 25 to review first (amber), 653 linked account groups, 558 not judged. Then "Highest-priority accounts" (the top 3), "Highest-priority groups" (the top 3) and "Also in the data": the busiest day, the matching-amount count, the 444 accounts at the edge of the data. Every figure links into its section |
| 02 | Priority accounts | The 25 ranked accounts: #, account, assessed as, priority, "the reason, in the rule's own numbers". Click a row to open the account |
| 03 | Account | The map around the selected account with a panel beside it that reads as sentences |
| 04 | Linked account groups | The 653 groups ranked (first 80 listed; the rest are in `out/formations.csv`), each drawn on its own map with its key account in amber |
| 05 | Transfers by day | July day by day on the hop layout |
| 06 | Matching amounts | 203 matches, each as an in → account → out diagram |
| 07 | Data limitations | Boundary figures, additional data to request, where centrality misleads, the removal test |

## How to answer "who do I look at first"

1. Section 01 answers it: "Highest-priority accounts" shows rank 1 to 3 with role and reason. Click
   one to open it in section 03.
2. For the full list, section 02. Rank 1 is the first to review; the last column is the rule's
   evidence string. The ranking is on the rules that fired, not on centrality.
3. Say it as a hypothesis: "signs of consolidation", "consistent with a collection point", not a verdict.

## How to find an account the jury names and show its links

1. Type the digits into the top-bar box. It autocompletes on the ids; the account opens once all 18
   digits are in, or when you pick a suggestion or press Enter.
2. Section 03 opens on it in "Linked accounts" mode. Columns, left to right: "paid the payers",
   "paid this account", "this account", "were paid by it", "were paid next". Arrows point the way
   the money moved, width is by KZT, colour is role, listed accounts are ringed. An account that
   paid and was paid is drawn once on the left with arrows both ways. At most 28 accounts per column
   are drawn; a note under the map says how many were left out.
3. Read the panel "This account" top to bottom: "Received X KZT from N accounts and sent Y KZT to M
   accounts in July." "Assessed as" the role, rule confidence and plain definition. "Figures the
   rule used:" the evidence string. "Investigation priority": score and "#k of 2,248", or "not in
   the top 25". "Position": hops and group. "What we know of it": knowledge state, confidence and
   limitation from `completeness.csv`. "Groups it belongs to": clickable chips, or "None."
4. Toggle "All accounts": all 2,248 by hop, listed accounts left, hop 4 right, the selection and its
   transfers lit. Hover a node for id and role, click to select; hover a legend role for its definition.

## How to show a linked account group and its key account

1. Section 04. The left list is ranked: kind, member count, listed accounts, KZT through it. Click a
   row, or a chip in an account's "Groups it belongs to".
2. The map draws only the members, by hop, the key account ringed in amber. The panel "This group"
   gives the definition, counts and KZT through it, then "Key account": the id in amber and "Remove
   this one account and N accounts cut off" (or "N KZT stopped"), with the method that found it.
3. "Hypothesis to test" is the sentence to say aloud. "Figures behind it:" is the evidence string.
   "Members" are chips coloured by role; clicking one opens that account in section 03.

## How to run the day-by-day view

- Section 05 is the "All accounts" hop layout, one day at a time. **Play** advances a day roughly
  every 0.7 seconds and loops; it reads **Pause** while running.
- The **day scrubber** (a slider) picks any day; beside it the date, "KZT moved", "transfers" and
  "active accounts" for that day.
- The **31-bar strip** is July's daily KZT, the current day amber. Hover a bar for its total, click to jump.
- **Trail** (on by default) fades the previous three days' arcs behind the current day.
- The busiest day is **16 July**: 23,732,052 KZT in 224 transfers, 241 active accounts. Section 01
  links straight to it. Clicking a node in this view opens it in section 03.

## How to read a matching-amount card

Section 06 lists 203 matches: 135 relays, 61 splits, 7 same-amount fan-outs. The three chips turn a
kind on or off; "sort" orders by score, amount or date. Each card has:

- A diagram: payers left, the account centre, receivers right, the amount on each line. Clicking
  any dot opens that account. Under it a badge: **EXACT** (amber, 127 matches) or **WITHIN 2%** (76).
- The kind in words: "Same amount in and out" (relay), "One amount in, split on the way out" (split),
  "Same amount to N receivers" (fan-out); the dates ("16 July, same day" or "22–23 July"); in, out
  and the 0..1 score; the evidence sentence with the figures it rests on.
- An **Open account** button, and the match id with the full account id.

The largest is a relay of 652,000 KZT sent back to the payer the same day, 22 July. 39 of the relays
are amounts sent straight back to the payer (their evidence line says "back to"); all of those pairs
are also in `reciprocal_pairs.csv`, so a relay and a "money returned" group can be the same money seen
twice. A relay can be rent passed on; a fan-out can be a payday. Each is a hypothesis to check.

## What the role names mean

- **consolidator:** Paid by 8 or more different accounts and keeps most of it, passing on under half.
- **coordinator:** Receives from 4 or more accounts and pays 4 or more; money moves through both ways.
- **transit:** Passes on roughly what it receives, between 80% and 120%.
- **distributor:** Pays out to 20 or more receivers.
- **terminal:** Money arrives and nothing leaves, before the edge of the data, so it appears to stay.
- **peripheral:** No rule threshold met: low activity, or a listed account with only outbound transfers.
- **abstained_boundary:** Sits at hop 4 with nothing going out. The data stops here, so no judgement.
- **abstained_single_observation:** Fewer than three transfers in total. Too little to judge.

Every role is a named rule with a numeric threshold; the evidence string in section 03 shows the
numbers it fired on. The two abstentions are the 558 "not judged" in section 01.

## What the group kinds mean

- **collection point** (`funnel`): several accounts each send most of their outflow to one account.
- **forwarding chain** (`chain`): money forwarded account to account, each passing on most of what arrived.
- **money returned** (`reciprocal_loop`): money sent and sent back, a pair or a short cycle.
- **one sender, many receivers** (`fan_out`): one account paying many receivers that send nothing on.
- **single link to the network** (`bridge`): one account that part of a group depends on to reach the rest of the network.

## Data limitations

- **Tiles.** 444 accounts at hop 4 with nothing going out ("the data stopped, not the money"),
  1,110 dead ends the data does follow to their end, 19 of the 81 listed accounts in no transfer,
  31 listed accounts that sent nothing, and the share of accounts and turnover at the boundary.
- **Additional data to request.** Ranked; each says what it resolves and the KZT it lights up.
- **Where a plain centrality ranking would mislead.** Accounts that moved most between the
  centrality rank and the evidence rank, with the numbers.
- **If the top-ranked accounts were removed.** Largest group left, separate pieces, accounts still
  reachable from the listed accounts.

Two limits are worth saying aloud. The data covers outbound transfers only, so money arriving at
the 81 listed accounts was never followed back, and anyone directing them from above is outside this
extract by construction. And the data stops at hop 4, so the hop 4 column on the right of "All
accounts" and of the day-by-day view is the edge of what was collected, not the edge of the money.
