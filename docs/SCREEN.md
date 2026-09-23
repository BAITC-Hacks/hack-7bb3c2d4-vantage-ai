# How to read the screen

`python3 run.py --serve`, then open `http://localhost:8000/web/`. One HTML file, no libraries, no
build step. It reads only `out/graph.json`. Everything on it is a hypothesis drawn from transfer
structure and amounts; nothing on it asserts wrongdoing.

## What you see when it opens

The screen opens on the answer to the case's question: which of these 2,248 accounts to look at
first, and why.

- **Header.** "Money Graph", a one-line subtitle, and a summary strip: 81 known clients (the seeds)
  → 2,248 accounts reached → 25 to review first → 653 structures found → 558 not judged. The 558
  are the two abstention roles. A button, "Where the data runs out", opens a full-width panel.
- **Left pane.** A search box, then two tabs. *Accounts to review* is the ranked top list
  from `top_nodes.csv`: rank, role, one-line reason. *Structures* is the ranked formations from
  `formations.csv`: kind, members, known clients, KZT through. Clicking a row selects it.
- **Centre, the map.** Default mode "Around this account": the selected account in the centre, the
  accounts that paid it to the left, the accounts it paid to the right, one more ring either side.
  Arrows point the way the money moved, line width is by KZT, nodes are coloured by role, known
  clients are ringed. Hovering a node shows its id and role; clicking selects it. A legend lists the
  roles with counts; hovering a role shows its plain definition.
- **Right pane, "This account".** The full gid, then: "Received X KZT from N accounts and sent
  Y KZT to M accounts." "Assessed as <role>" with the plain definition, the rule's own evidence
  string (the numbers it fired on) and the rule confidence. "Investigation priority: score, rank #k
  of 2,248" (the rank appears when the account is in the top list). Hop from a known client and
  group id. "What we know of it": the knowledge state and confidence from `completeness.csv`, with
  its limitation sentence. "Structures it belongs to": the formations containing it, clickable.
  If the account sits at hop 4 with nothing going out, a caveat says so.

## How to answer "who do I look at first"

1. Read the *Accounts to review* tab from the top. Rank 1 is the first account to review; its one-line reason
   says why.
2. Click it. The right pane gives the role, the rule's evidence string and the priority score, all
   from computed metrics. The map shows who paid it and whom it paid.
3. Switch to the *Structures* tab for the same question at group level: each row is a formation,
   ranked, with its member count and the KZT that moved through it. Selecting one shows its members
   on the map with the breaking point, the member whose removal breaks most of it, marked in amber.
4. Say it as a hypothesis: "signs of consolidation", "consistent with a funnel", never a verdict.

## How to find an account the jury names and show its links

1. Type the digits into the search box at the top of the left pane. It autocompletes on the id
   digits; type the full id or pick a suggestion.
2. The account is selected and the map re-centres on it. Left of centre are the accounts that paid
   it, right of centre the accounts it paid, then one more ring either side.
3. Read the right pane top to bottom: the money sentence, the role and its definition, the evidence
   string, the priority, the hop and group, the knowledge state, and the structures it belongs to.
   Click a structure to see the whole formation on the map.
4. For the wider context, toggle "Whole network": all 2,248 laid out by hop, known clients on the
   left and hop 4 on the right, with the selection highlighted.

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

Every role is a named rule with a numeric threshold, and the evidence string in the right pane
shows the numbers the rule fired on. The two abstentions are the 558 "not judged" in the header.

## What the structure kinds mean

- **funnel:** several accounts each send most of their outflow to one collection point.
- **chain:** money forwarded account to account, each passing on most of what arrived.
- **reciprocal_loop:** money sent and sent back, a pair or a short cycle.
- **fan_out:** one account paying many receivers that send nothing on.
- **bridge:** one account that part of a group depends on to reach the rest of the network.

## Where the data runs out

The header button opens a full-width panel with four parts:

- **Completeness summary figures.**
- **Next data requests, ranked.** What to ask the data owner for, and what each request resolves.
- **Where centrality and evidence disagree.** The table of accounts where a plain centrality
  ranking and the evidence ranking disagree.
- **The removal test.** What happens to the network if the top-ranked accounts are removed.

Two limits are worth saying aloud. The crawl followed outbound transfers only, so money arriving at
the 81 known clients was never followed back. And the crawl stopped at hop 4, so an account there
with nothing going out is not judged and carries a caveat in the right pane; the hop 4 column on the
right of "Whole network" is the edge of what was collected, not the edge of the money.
