# System Overview

A plain-language tour of how this application is built and why it's built that
way. No prior knowledge of the codebase assumed.

Setup instructions are in the [README](README.md). Full request and response
detail for every endpoint is generated from the code and browsable at
`http://localhost:8000/docs` once the stack is running.

---

## What the product does

Two very different people use this system.

**A prospect** finds a public web page, fills in their name, email and resume,
and submits. They get a confirmation email. They never make an account.

**An attorney** signs in to a private dashboard, sees every lead that has come
in, downloads resumes, and marks a lead as "reached out" once they've contacted
that person.

That's the whole product. Almost every design choice below follows from those
two audiences being different: one is anonymous and on the open internet, the
other is trusted and signed in.

---

## The big picture

```
   PROSPECT                                    ATTORNEY
   (anonymous)                                 (signed in)
       │                                            │
       │  submits the form                          │  opens the dashboard
       │                                            ▼
       │                                   ┌──────────────────┐
       │                                   │   Web app        │
       │                                   │   (Next.js)      │
       │                                   │  holds the login │
       │                                   │  session safely  │
       │                                   └────────┬─────────┘
       │                                            │
       └──────────────┐              ┌──────────────┘
                      ▼              ▼
              ┌───────────────────────────────┐
              │   API  (FastAPI)              │
              │   every rule lives here       │
              └───┬──────────┬─────────┬──────┘
                  │          │         │
            ┌─────▼───┐ ┌────▼────┐ ┌──▼──────┐
            │Database │ │  File   │ │  Email  │
            │         │ │ storage │ │ service │
            └─────────┘ └─────────┘ └─────────┘
```

The prospect's submission goes straight to the API. The attorney's requests all
pass through the web app first. That difference is deliberate and explained
below.

---

## The front end

The front end is a Next.js application with two separate areas.

### The public form (`/apply`)

A single page: four fields and a drag-and-drop area for the resume. It checks
your input as you type, shows errors under the specific field that's wrong, and
switches to a thank-you message on success.

**Why the browser talks to the API directly here.** There's no login involved,
so there's no secret to protect. Sending the file through the web app first
would mean the resume gets copied twice for no benefit. So this one page calls
the API straight from the browser.

**Why the form still validates on the server.** The checks in the browser exist
to give fast feedback, not to enforce anything. Anyone can bypass them. The API
re-checks everything, and the API's answer is the one that counts.

### The dashboard (`/admin`)

A login page, a searchable list of leads with filter tabs and pagination, and a
detail page for each lead showing their submission, the history of status
changes, and whether both emails actually got delivered.

**Why the pages are built on the server.** The dashboard's pages are assembled
on the server and sent to the browser as finished HTML. This is the single most
consequential front-end decision, and it exists to protect the login token —
explained in the decisions section below.

**Why filters live in the web address.** Because pages are built on the server,
choosing "Pending" or typing a search changes the URL rather than just changing
something in the browser's memory. The useful side effect is that a filtered
view can be bookmarked or pasted to a colleague and it still works.

---

## The API calls

Everything the front end does comes down to eight requests.

| Request | What it's for | Who can call it |
|---|---|---|
| `POST /leads` | Submit a lead and resume | Anyone |
| `POST /auth/login` | Sign in, get a session | Anyone |
| `GET /auth/me` | Who am I? | Signed in |
| `GET /leads` | The lead list, with search and filters | Signed in |
| `GET /leads/stats` | Counts for the filter tabs | Signed in |
| `GET /leads/{id}` | One lead, with history and email status | Signed in |
| `PATCH /leads/{id}` | Mark a lead as reached out | Signed in |
| `GET /leads/{id}/resume` | Download the resume | Signed in |

Two more, `/healthz` and `/readyz`, exist only so the hosting platform can tell
whether the service is alive.

**Why every error looks the same.** Whenever something goes wrong, the API
replies in one consistent shape: a short code, a human-readable message, and —
if the problem was with a specific field — which field. That means the front end
needs one piece of code to understand every failure, instead of guessing at a
different format each time. It's why a bad email address highlights the email
box rather than showing a generic "something went wrong."

---

## The back end

The API is organised into layers, each with one job. It's a bit like a company
where departments don't do each other's work:

- **Routes** handle the web request itself — reading the input, returning the
  answer. They contain no rules.
- **Services** hold the actual rules — is this status change allowed, what
  emails should go out.
- **Repositories** are the only place that talks to the database.

The benefit is that a rule lives in exactly one place. When you want to know how
a lead's status can change, there's one file to read, not a search across the
codebase.

### What's stored

- **Leads** — everything the prospect submitted, plus their current status.
- **Users** — the attorneys who can sign in.
- **Status history** — an append-only log: every status change, who made it, and
  when. Nothing is ever overwritten here.
- **Email records** — one row per email the system owes, and whether it was
  actually delivered.

### Two things treated as replaceable

**File storage** and **email** are the two parts the application doesn't
control. Both sit behind a simple internal interface, so switching from local
development tools to real cloud services is a configuration change, not a code
change. It also means the automated tests can substitute fake versions and run
without touching the network.

---

## Design decisions, and what they cost

### Emails are recorded before they are sent

**What we do.** When a lead is submitted, we save the lead *and* two "email owed"
records in a single, all-or-nothing database write. Only afterwards do we
actually try to send them.

**Why.** The obvious approach — send the emails immediately — forces a bad
choice when the mail service is down. Either you tell the prospect the
submission failed (but it didn't, it's already saved, so they submit again and
you get duplicates), or you tell them it worked and quietly never notify the
attorney. The second is worse, because nothing anywhere records that a
notification was missed.

Saving the email records alongside the lead means a lead can never exist without
a record of the emails owed on it. If sending fails, that's visible on the lead's
page rather than lost.

**Cost.** One extra database table. In exchange, "did the attorney actually get
notified?" is a question you can answer.

*This wasn't theoretical — during development a timing bug meant emails weren't
sent. Nothing was lost, because the records were already saved and simply showed
as pending.*

### Resumes are checked by their contents, not their name

**What we do.** We accept PDF and Word (.docx) files up to 5 MB, and we verify
the file type by inspecting the actual bytes rather than trusting the file
extension.

**Why.** Anyone can rename a program to `resume.pdf`. The file extension and the
file type the browser reports are both supplied by whoever is uploading, so
neither is evidence. Reading the first few bytes tells you what the file really
is.

We also never use the uploaded filename when saving the file — that name is
chosen by a stranger, and using it opens the door to overwriting other people's
files. The original name is kept only so the download shows something sensible.

**Cost.** A little more code. It closes off the most obvious way to abuse a
public upload form.

### Attorneys are deactivated, never deleted

**What we do.** Removing an attorney's access flips a switch on their account
rather than deleting the record.

**Why.** Lead history refers back to the attorney who acted on it. Deleting the
account would blank out those references — so the record of who contacted which
prospect would develop holes exactly where accountability matters most. The
switch separates "this person can no longer sign in" from "erase what they did."

Access is also re-checked on every single request, not just at sign-in. Otherwise
someone who was just deactivated would keep working until their session
naturally expired, up to an hour later.

**Cost.** One extra column, and one check on each request.

### Only one status change is allowed

**What we do.** A lead starts as `PENDING` and can move to `REACHED_OUT`. That's
it. Trying to move it back, or to repeat a change, is rejected.

**Why.** "We un-contacted them" isn't a real event. Allowing it would make the
history misleading. Keeping the permitted changes in one short list also means
adding a new status later is a small, obvious edit rather than a hunt through
the code.

**Cost.** None meaningful. The system is stricter than a free-form status field,
which is the point.

### The login token never reaches the browser's code

**What we do.** Signing in produces a token, which is stored in a cookie the
browser will send but that page scripts cannot read. The dashboard's pages are
built on the server, where that cookie can be used.

**Why.** The common shortcut is to keep the token somewhere the page's own
JavaScript can read it. That's simpler, but it means any single scripting
vulnerability anywhere on the site hands over the session. Keeping the token out
of reach removes that whole category of risk.

**Cost.** The dashboard has to fetch its data while building each page, which is
why filters live in the URL. That constraint turned out to be a feature.

There's also a guard that redirects signed-out visitors away from the dashboard,
but that's only about not showing people a broken screen. The real check is the
API verifying the token on every request — one system decides who gets in, not
two that could eventually disagree.

### Resume downloads bypass the application

**What we do.** Clicking a resume gets you a temporary, expiring link directly to
the file storage service.

**Why.** The alternative is piping every file through the application, which ties
up capacity for the length of each download. A temporary link is answered
instantly and the file travels directly to the attorney.

**Cost.** The link works for five minutes without further checks. That's a
deliberate, bounded trade.

### Development uses fake email and storage

**What we do.** Locally, emails go to a mail catcher — a tool that accepts every
message and shows it in a web page — instead of being delivered.

**Why.** It means anyone can run the project and see exactly what both emails
look like, without configuring a mail provider and without any risk of
accidentally emailing real people during testing. Pointing at a real provider is
a matter of changing a few settings.

---

## What we deliberately did not build

Being explicit about this is part of the design.

- **Automatic email retry.** A failed email stays failed and is shown as such.
  The database already has the columns a retry system would need, so adding one
  later doesn't require restructuring anything.
- **Rate limiting that works across multiple servers.** The current protection
  against form spam counts requests within a single running copy of the
  application. That's correct for one server and would need replacing to run
  several.
- **Instant sign-out everywhere.** Signing out clears the session in that
  browser, but the token itself remains technically valid until it expires.

Each of these is a real limitation with a known solution. They were left out to
keep the first version small and working, which was the priority.

---

## How it's verified

68 automated tests run against a real database rather than a simplified stand-in,
so the behaviour being tested is the behaviour that ships. They cover the things
most worth being confident about: that a disguised file is rejected, that a mail
outage doesn't cost you a lead, that a deactivated attorney loses access
immediately, and that an illegal status change is refused.
