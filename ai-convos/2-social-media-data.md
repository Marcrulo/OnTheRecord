USER:

how might i use social media post data (or quotes from there) in a new commerical dataset?

-----------------------------------

AI:

Using social media content in a commercial dataset raises several distinct issues. Here's how they break down.

**Platform terms of service.** This is usually the hardest barrier. X, Reddit, Meta, and TikTok all prohibit scraping and restrict redistribution of content pulled through their APIs. Reddit and X now license data commercially and price it accordingly. Breaching ToS is a contract issue rather than copyright, but it's what actually gets projects shut down.

**Copyright.** A tweet or post is generally copyrightable if it has minimal creativity, and the poster owns it, not the platform. Very short factual posts may fall below the originality threshold. Fair use may cover text-mining and model training in the US, but that's actively being litigated and commercial use weakens the case considerably.

**Privacy law.** If you're in Denmark, GDPR applies. Public posts are still personal data. You need a lawful basis (legitimate interest is the usual one, but requires a balancing test), and you have transparency obligations to data subjects, which is genuinely hard at scale. Special category data (political views, health, sexuality) is more tightly restricted. The Danish DPA has been active here.

**Practical paths that reduce risk:**

- License data from the platform directly (Reddit Data API, X enterprise tiers, Meta's research products)
- Buy from an established data vendor who has assumed the compliance burden
- Use existing research corpora and check their licenses for commercial permission (many are non-commercial only)
- Store only post IDs and rehydrate through the API, which is the standard academic approach and keeps deletions honored
- Aggregate or derive rather than redistribute raw text, so your product is statistics or embeddings rather than the posts themselves
- Pseudonymize and strip usernames, though this doesn't fully exit GDPR scope
- Get explicit consent, which is only feasible for narrow, small datasets

If you tell me what the dataset is for (training, benchmarking, sentiment analytics, resale) and which platforms you have in mind, I can be more specific. Worth flagging that I'm not a lawyer, and this area is unsettled enough that you'd want actual counsel before commercializing.

---------------------------

USER:

I need a compilation of quotes from certain people

--------------------------

AI:

That shifts things. A compilation of quotes attributed to identified individuals is roughly the highest-risk shape this can take, because it stacks every problem on top of each other.

**Copyright.** Quoting means reproducing the expression verbatim, which is the core of what copyright protects. A compilation is not transformative in the way that training a model or computing aggregate sentiment might be. Fair use for quotation typically depends on brevity, commentary, criticism, or news reporting. A commercial product whose value *is* the quotes themselves lands badly on the fourth factor (market effect), because you're substituting for the original.

**Right of publicity.** In the US, using someone's name or likeness for commercial purposes without permission is a separate tort in most states. Attributed quotes are exactly that. If the people are public figures this actually gets worse, not better, since their identity has commercial value.

**GDPR.** Named quotes are unambiguously personal data, and the "certain people" framing means you can't argue anonymization. You'd need a lawful basis, and you'd owe those individuals notice, access, and possibly erasure. If any quotes touch politics, religion, health, or sexuality, they're special category data with a much higher bar.

**Defamation and context.** Quotes stripped of context and republished commercially carry liability if the compilation implies something false about the person.

**What actually works:**

- License it. Newspapers, wire services, and quote-database companies exist because this is the compliant path.
- Get permission from the individuals, especially if there are few of them.
- Use public-domain or Creative Commons sources, including government speech, which in the US is often public domain.
- Shift from reproduction to reference: store citations, links, and metadata pointing to where the quote lives, rather than the text. This is a genuinely different product and a much safer one.
- Paraphrase and analyze rather than reproduce, so you're selling the insight, not the words.

Who are these people, and what's the product? If they're politicians speaking on the record, or if the compilation is for commentary and criticism, the picture is meaningfully different from a dataset of private individuals' posts sold as raw material. Again, worth real legal advice before you build this.

-----------------------------

USER: 

can i instead just compile all the post links for each person? not even the content itself

----------------------------

AI:

Better, but not clean.

**What genuinely improves.** Copyright largely falls away. A URL is a fact, not creative expression, and linking is not reproduction. There's caselaw supporting this in both the US and EU. Deletions propagate automatically, since a dead link is a dead link. And you're not substituting for the original, you're driving traffic to it.

**What doesn't go away.**

*GDPR.* A curated list of "every post by this named person" is still personal data, arguably more so, because the compilation itself creates a profile that didn't exist before. That's the whole point of the product. The EU's *Google Spain* line of thinking is that aggregation and indexing of otherwise-public information is its own processing activity with its own harms. You still need a lawful basis, still owe notice and erasure rights, and if the posts touch special categories the compilation is now a political or religious profile of a named individual.

*Platform ToS.* Scraping to build the link list is still scraping, regardless of what you keep afterward. This is where most projects actually die.

*Database rights.* In the EU, a substantial investment in compiling a database gets *sui generis* protection even when the individual items aren't copyrightable. If you're systematically extracting a substantial part of a platform's database, that's a claim they can bring even though URLs are facts. This is EU-specific and worth knowing about, since you're in Denmark.

*Right of publicity.* Weaker but not zero if the product is marketed around specific named people.

**The practical upshot.** The ID-and-rehydrate pattern is the standard compliant approach, and you'd be adopting it. Get the IDs through official APIs rather than scraping and the ToS problem mostly resolves. Then your remaining work is the GDPR piece: legitimate interest assessment, a privacy notice, a way to honor erasure requests. If the individuals are public figures speaking in a public capacity and your purpose is journalism, research, or commentary, GDPR's Article 85 exemptions give member states room to carve out relief, and Denmark has implemented some.

What's the purpose? "Compilation of posts by named people, sold commercially" reads very differently if it's an accountability tool for politicians versus a monitoring product aimed at private individuals. That distinction does most of the legal work here.

-------------------------

USER:

specifically i'd like to compile links from politicians. these are public figures that post in the name of the party and their beliefs

---------------------------

AI:

That's about as favorable as this gets.

**Why it improves.** Politicians posting in their official or party capacity have essentially no reasonable expectation that their public statements won't be indexed and scrutinized. That's the point of political speech. GDPR's legitimate interest balancing test weighs the data subject's reasonable expectations against your purpose, and both sides of that scale move in your favor here. Right of publicity claims are weak against political accountability uses in most jurisdictions. And you're storing links, not content, so copyright is largely moot.

**The special-category wrinkle, and why it likely doesn't bite.** Political opinions are Article 9 special category data, which normally requires a higher bar. But Article 9(2)(e) carves out data "manifestly made public by the data subject." A politician tweeting their party's position is the textbook case. Don't lean on this without checking, but it's the right hook.

**What still needs doing.**

- **Get the links through official APIs, not scraping.** This is the ToS and database-rights problem, and it's the one most likely to actually cause you trouble. X, Meta, and others have research and enterprise access tiers. Cost is the constraint, not permission.
- **Write a legitimate interest assessment.** It's a document, not a formality. Purpose, necessity, balancing. It's your defense if the Datatilsynet asks.
- **Publish a privacy notice.** Article 14 applies when you collect data from a source other than the subject. There's a disproportionate-effort exemption, but for a bounded set of politicians it probably doesn't apply, so just publish it.
- **Scope it to official capacity.** Party accounts, official accounts, verified personal accounts used for political communication. A politician's private Instagram of their kids is a different thing, and including it undermines the whole legitimate-interest story.
- **Check the Danish journalism and expression exemptions.** Denmark implemented Article 85 through the Databeskyttelsesloven. If your product qualifies as journalistic or serves public debate, meaningful chunks of GDPR may not apply. Worth having counsel look at whether you fit.

**Where it can still go wrong.** Selectively compiling to make someone look bad, monitoring candidates rather than officeholders, or expanding scope to staffers, family, or private accounts. The defense here is "public accountability of public figures acting publicly," and every step away from that weakens it.

What are you building on top of the links? That shapes whether the journalism exemption is even in play.