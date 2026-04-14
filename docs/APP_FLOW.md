# Research Paper Assistant — How the App Works

A plain-English guide to what happens when a professor uses the app.

---

## What Is This App?

A research assistant for professors. You give it academic papers, ask it research questions, and it reads through all the papers and writes a structured literature review for you — pointing out what papers agree on, what they contradict, and what is still an open question.

---

## The Big Picture

Think of the app like a very smart research librarian:

1. **You build a personal library** by uploading papers.
2. **You ask a research question.**
3. **The librarian searches your library.** If it finds enough relevant material, it reads it and writes a summary for you. If your library doesn't have enough on the topic, it automatically goes to the internet, fetches relevant papers, adds them to your library, and then writes the summary.

---

## What Happens When You Upload a Paper

**You can add papers in three ways:**

### 1. Upload a PDF

You drag a PDF file into the app. The app:

- Reads all the text out of the PDF.
- Cuts it into smaller pieces (like cutting a book into chapters, then paragraphs).
- Converts each piece into a set of numbers that represent its meaning (this is called an "embedding").
- Saves all those numbered pieces into a local database on your computer.

The paper is now in your personal library and can be searched.

### 2. Paste a DOI or URL

You paste a paper's DOI (the unique ID papers have, like `10.1145/...`) or a web link. The app:

- Looks up the paper's details (title, authors, abstract) from Semantic Scholar.
- Downloads the full text if a PDF link is available, otherwise uses the webpage text.
- Does the same cut → number → save process as above.

### 3. Discover & Import from the Internet

You type a topic in the Discover search box. The app:

- Searches Semantic Scholar and arXiv for papers matching your topic.
- Shows you a list of results as a **preview** — nothing is saved yet.
- You tick the ones you want and click Import.
- Only the selected papers get saved to your library.

---

## What Happens When You Ask a Research Question

This is the most important flow. You type a question like:

> *"What are the main challenges in using AI for medical diagnosis?"*

Here is what happens, step by step:

---

### Step 1 — Your question is sent to the app's brain

The app takes your question and starts a multi-step process involving four specialized agents that work together like a team.

---

### Step 2 — Agent 1 searches your local library

The app converts your question into numbers (the same way papers are stored) and looks for library content that is numerically "close" to your question — meaning semantically similar.

It finds the most relevant pieces from your saved papers and checks: **do I have enough good material here to answer this question well?**

- If **yes** — it skips the internet and goes straight to writing the answer.
- If **no** — it calls in the next agent.

---

### Step 3 — Agent 2 searches the internet (only if needed)

If your local library doesn't have enough relevant papers, this agent searches **four academic databases at the same time**:

- **arXiv** — Computer science, physics, math preprints
- **PubMed** — Medical and biological research
- **bioRxiv** — Biology preprints
- **medRxiv** — Medical preprints

It fetches up to 10 papers from each database (40 total), then removes duplicates and keeps only papers that have an abstract (a summary of the paper).

**Why so many?** Because no single database covers everything. A question about AI in healthcare needs results from both arXiv (AI side) and PubMed (healthcare side). Fetching broadly and then filtering is how the app ensures good coverage.

---

### Step 4 — Agent 3 saves the fetched papers to your library

The app takes the papers found from the internet and saves them into your local library — the same way you would if you had imported them manually.

**These papers stay in your library permanently.** Next time you ask a related question, they'll already be there.

---

### Step 5 — Agent 4 reads everything and writes the answer

Now with a full set of relevant material (from your original library plus any newly fetched papers), this agent:

1. Pulls the most relevant pieces of text from your library — again using the numbers-and-similarity approach.
2. Organises those pieces with numbered references like `[1]`, `[2]`, `[3]`.
3. Sends all of that to an AI language model (like GPT-4) along with the instruction: *"Write a structured literature review based only on what you see here. Do not invent anything."*
4. The AI writes back a structured response with:
  - **Summary** — Overall state of research on this topic
  - **Agreements** — Things multiple papers agree on
  - **Contradictions** — Places where papers disagree
  - **Research Gaps** — Questions that haven't been answered yet
  - **Citations** — Exact references to the papers used

---

### Step 6 — The answer is saved and shown to you

The result is saved so you can come back to it later. You see the structured review on screen with tabs for each section. If the app had to go fetch external papers, it shows a banner telling you how many new papers were added to your library.

---

## Your Library Over Time

Every time you use the app, your library gets smarter:

- Papers you upload manually → added permanently.
- Papers the app fetches automatically during a query → added permanently.
- Future queries on related topics will find this content locally, meaning faster answers and no need to go to the internet again.

---

## The Four Pages


| Page               | What it does                                         |
| ------------------ | ---------------------------------------------------- |
| **Dashboard**      | Overview — how many papers you have, recent queries  |
| **Upload**         | Add papers via PDF, DOI, or internet search          |
| **Ask a Question** | Type a research question and get a literature review |
| **Library**        | Browse, search, and delete papers in your collection |


---

## Summary in One Paragraph

You upload academic papers (or let the app find them for you). When you ask a research question, the app searches your paper collection for the most relevant content. If there isn't enough, it automatically searches arXiv, PubMed, and other academic databases, saves those papers to your library, and then uses all of it to write a grounded literature review — citing specific papers for every claim, and never making anything up.