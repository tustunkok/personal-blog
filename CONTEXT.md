# Personal Blog

A single-author blogging platform with fine-grained post lifecycle, aggressive visitor analytics, and a server-rendered modern UI.

## Language

### Post Lifecycle

**Post**:
A piece of written content identified by a unique slug, with a title, body (markdown), and associated metadata.
_Avoid_: Article, entry, page

**Draft**:
A post visible only in the admin area. Cannot be accessed by visitors or RSS consumers.
_Avoid_: Unlisted, hidden

**Scheduled**:
A post assigned a future publication datetime. Not visible to visitors but appears in RSS feed. Auto-transitions to Published when the datetime arrives.
_Avoid_: Queued, pending

**Published**:
A post currently visible to all visitors and in the RSS feed. Can be reverted to Draft at any time ("unpublished").
_Avoid_: Live, active

**Unpublish**:
The action of moving a Published post back to Draft. Instantaneous, no scheduling.
_Avoid_: Retract, take-down

**Auto-publish**:
The background mechanism that transitions Scheduled posts to Published when their datetime is reached.
_Avoid_: Cron publish, scheduled activation

### Content Structure

**Slug**:
The unique URL-safe identifier for a post, used in `/posts/{slug}`. Auto-generated from title, can be overridden.
_Avoid_: Permalink, URL key, ID

**Excerpt**:
A short plain-text summary of a post, displayed on listing cards and used in meta tags.
_Avoid_: Summary, description, blurb, teaser

**Featured Image**:
The hero/thumbnail image for a post, stored as a blob in SQLite alongside the post record.
_Avoid_: Hero image, cover image, thumbnail

**Tag**:
A freeform label attached to a post. A post can have many tags.
_Avoid_: Label, keyword, category

**Series**:
An ordered sequence of posts grouped by a shared title. Each post in the series knows its position. Displayed on the post page as a table of contents and prev/next navigation.
_Avoid_: Collection, sequence, chain

**Canonical URL**:
An optional URL indicating the original source if the post was cross-posted elsewhere.
_Avoid_: Original URL, cross-post link

**Static Page**:
A standalone page (About, Now) with a title and markdown body, stored in the settings table. Rendered via the same markdown pipeline as posts. Edited through the admin area with a markdown editor.
_Avoid_: Custom page, info page

**Mermaid Diagram**:
A diagram defined inline in a post or static page using ` ```mermaid` fenced code blocks. Rendered client-side by mermaid.js into SVG. Same pattern as Math Blocks: parsed server-side into a container element, rendered by JS in the browser.
_Avoid_: Chart, flowchart, graph

### Visitor Analytics

**Visit**:
A single page load by a visitor. Uniquely identified by a fingerprint hash combining IP, user-agent, and device attributes.
_Avoid_: Page view, hit, session

**Fingerprint**:
A hash computed from client-side attributes (screen, OS, browser, timezone, etc.) used to group visits by the same person without cookies.
_Avoid_: Device ID, signature

**Page Session**:
The span of time a visitor spends on a single post, from entry to exit, measured via heartbeat pings.
_Avoid_: Dwell time, read session

**Navigation Path**:
The sequence of internal URLs a visitor traverses during a browsing session.
_Avoid_: Click path, journey

**Engagement Event**:
A recorded interaction within a post page: text selection, copy, external link click, code block click.
_Avoid_: Interaction, action

### Interactions

**Comment**:
A visitor-submitted message on a post. Name and email are optional. Subject to bot protection (honeypot field + time gate, Turnstile as fallback). Comments track: IP, user-agent, reply depth, character count, submission time, URL usage, markdown features used.
_Avoid_: Reply, response

**Reaction**:
A visitor's quick sentiment signal on a post (like/vote/clap). Tracks: reaction type, IP, user-agent, scroll position, time-to-react.
_Avoid_: Vote, like, clap, emoji

**Share**:
A visitor clicking a social share button on a post. Tracks: platform, IP, user-agent.
_Avoid_: Social share, tweet

### Admin

**Admin Password**:
The single credential for accessing the admin area, sourced from an environment variable.
_Avoid_: Auth token, login

### Math Rendering

**Math Block**:
A LaTeX expression in a post body, delimited by `$...$` (inline) or `$$...$$` (display). Protected from Markdown processing by pymdown-extensions' arithmatex and rendered client-side by KaTeX.
_Avoid_: Formula, equation

### Syndication

**RSS Feed**:
An XML feed at `/feed.xml` containing the 20 most recent posts (full content), including both Published and Scheduled posts.
_Avoid_: Atom feed, syndication
