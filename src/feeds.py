"""
RSS feed URLs organised by newsletter topic.

Edit this file to add, remove, or reorder feeds. Topic names must match
the names in config.py exactly.

Feeds marked with a comment are known to need runtime validation —
they may 404 or return unparseable content. The fetcher logs and skips
any feed that fails.
"""

FEEDS: dict[str, list[str]] = {
    # ------------------------------------------------------------------
    # 1. Climate Policy & Energy Transition
    # ------------------------------------------------------------------
    "Climate Policy & Energy Transition": [
        # Subscribed (paywall — have FT, NYT, Economist, AFR subs)
        "https://www.ft.com/climate-capital?format=rss",
        "https://www.ft.com/energy?format=rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml",
        "https://www.economist.com/science-and-technology/rss.xml",
        # Free / substantial content
        "https://reneweconomy.com.au/feed",
        "https://www.theguardian.com/au/environment/rss",
        "https://www.theguardian.com/environment/climate-crisis/rss",
        "https://www.abc.net.au/news/feed/104217374/rss.xml",       # ABC Business
        "https://www.carbonbrief.org/feed",
        "https://cleantechnica.com/feed",
        "https://theconversation.com/au/environment/articles.atom",
        "https://insideclimatenews.org/feed",
        "https://www.climatechangenews.com/feed",
        "https://www.canarymedia.com/rss.rss",
        "https://yaleclimateconnections.org/feed",
        "https://www.cleanenergywire.org/feed",                     # needs testing
        # Substacks & independents
        "https://www.volts.wtf/feed",
        "https://www.tempestsandterawatts.com/feed",
        "https://ketanjoshi.co/feed",                               # needs testing
        "https://www.climateandcapitalmedia.com/feed",              # needs testing
        "https://energydaily.substack.com/feed",
        "https://www.climatecouncil.org.au/feed",                   # needs testing
        "https://www.climatepolicyinitiative.org/feed",             # needs testing
    ],

    # ------------------------------------------------------------------
    # 2. AI & Technology
    # ------------------------------------------------------------------
    "AI & Technology": [
        # Subscribed
        "https://www.ft.com/artificial-intelligence?format=rss",    # needs testing
        "https://www.ft.com/companies/technology?format=rss",       # needs testing
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://www.economist.com/science-and-technology/rss.xml",
        # Major tech publications
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://arstechnica.com/ai/feed/",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://www.wired.com/feed/rss",
        "https://www.technologyreview.com/feed/",
        "https://www.theguardian.com/technology/artificialintelligenceai/rss",
        "https://www.itnews.com.au/RSS/rss.ashx",
        "https://www.innovationaus.com/feed/",                      # needs testing
        # Substacks & blogs
        "https://simonwillison.net/atom/everything/",
        "https://www.oneusefulthing.org/feed",
        "https://importai.substack.com/feed",
        "https://thezvi.substack.com/feed",
        "https://aisnakeoil.substack.com/feed",
        "https://thealgorithmicbridge.substack.com/feed",
        "https://www.platformer.news/rss/",
        "https://www.404media.co/rss/",
        "https://stratechery.com/feed/",
        "https://noahpinion.substack.com/feed",
        # AI company blogs
        "https://openai.com/news/rss.xml",
        "https://research.google/blog/rss/",
        "https://deepmind.google/blog/rss.xml",                    # needs testing
    ],

    # ------------------------------------------------------------------
    # 3. Australian Politics & Public Sector
    # ------------------------------------------------------------------
    "Australian Politics & Public Sector": [
        # Subscribed
        "https://www.ft.com/australia?format=rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml",
        "https://www.economist.com/asia/rss.xml",
        # Core free feeds
        "https://www.abc.net.au/news/feed/104217372/rss.xml",      # ABC Politics
        "https://www.theguardian.com/australia-news/australian-politics/rss",  # needs testing
        "https://www.themandarin.com.au/feed/",
        "https://www.themandarin.com.au/category/the-juice/feed/",
        "https://www.smh.com.au/rss/politics/federal/feed.xml",
        "https://theconversation.com/au/politics/articles.atom",    # needs testing
        "https://www.crikey.com.au/feed",
        "https://www.sbs.com.au/news/feed",
        "https://michaelwest.com.au/feed/",
        "https://johnmenadue.com/feed/",
        "https://australiainstitute.org.au/feed/",
        "https://insidestory.org.au/feed",
        "https://feeds.feedburner.com/IndependentAustralia",
        "https://www.governmentnews.com.au/feed/",
        "https://www.aspistrategist.org.au/feed",
        # Parliament feeds
        "https://www.aph.gov.au/senate/rss/new_inquiries",
        "https://www.aph.gov.au/senate/rss/reports",
        "https://www.aph.gov.au/house/rss/house_news",
        # Substacks
        "https://newpolitics.substack.com/feed",
        "https://www.pollbludger.net/feed",
        "https://www.tallyroom.com.au/feed",
        "https://devpolicy.org/feed",
    ],

    # ------------------------------------------------------------------
    # 4. Top Global Stories
    # ------------------------------------------------------------------
    "Top Global Stories": [
        # Subscribed
        "https://www.ft.com/world?format=rss",
        "https://www.ft.com/global-economy?format=rss",
        "https://www.ft.com/rss/home",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.economist.com/international/rss.xml",
        "https://www.economist.com/leaders/rss.xml",
        "https://www.economist.com/asia/rss.xml",
        "https://www.economist.com/china/rss.xml",
        "https://www.economist.com/europe/rss.xml",
        "https://www.economist.com/middle-east-and-africa/rss.xml",
        "https://www.economist.com/the-americas/rss.xml",
        # Breaking news (free)
        "https://www.abc.net.au/news/feed/104217382/rss.xml",      # ABC World
        "https://www.theguardian.com/world/rss",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://apnews.com/world-news.rss",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.france24.com/en/rss",
        "https://www.france24.com/en/asia-pacific/rss",
        "https://rss.dw.com/rdf/rss-en-top",
        "https://rss.dw.com/rdf/rss-en-asia",
        "https://feeds.npr.org/1004/rss.xml",
        # Analysis & foreign policy
        "https://thediplomat.com/feed",
        "https://foreignpolicy.com/feed",
        "https://www.foreignaffairs.com/rss.xml",
        "https://responsiblestatecraft.org/feeds/feed.rss",
        "https://warontherocks.com/feed",
        "https://asiasentinel.com/feed",
        # Asia-Pacific (paywalled, headline discovery)
        "https://www.scmp.com/rss/91/feed",
        "https://asia.nikkei.com/rss/feed/nar",
        # Substacks
        "https://noahpinion.substack.com/feed",
        "https://timothyash.substack.com/feed",
    ],

    # ------------------------------------------------------------------
    # 5. Other Top Australian Stories
    # ------------------------------------------------------------------
    "Other Top Australian Stories": [
        "https://www.abc.net.au/news/feed/10719986/rss.xml",       # ABC Top Stories
        "https://www.abc.net.au/news/feed/10719976/rss.xml",       # ABC Just In
        "https://www.abc.net.au/news/feed/104333858/rss.xml",      # ABC Around Australia
        "https://www.theguardian.com/australia-news/rss",
        "https://www.sbs.com.au/news/feed",
        "https://www.sbs.com.au/news/topic/australia/feed",        # needs testing
        "https://www.smh.com.au/rss/feed.xml",
        "https://www.theage.com.au/rss/feed.xml",
        "https://www.canberratimes.com.au/rss.xml",
        "https://theconversation.com/au/articles.atom",            # needs testing
        "https://thenewdaily.com.au/feed/",                        # needs testing
        "https://feeds.feedburner.com/IndependentAustralia",
    ],

    # ------------------------------------------------------------------
    # 6. Canberra & ACT (grounding fallback enabled)
    # ------------------------------------------------------------------
    "Canberra & ACT": [
        "https://www.abc.net.au/news/feed/5512668/rss.xml",       # ABC ACT
        "https://www.canberratimes.com.au/rss.xml",
        "https://the-riotact.com/feed",                            # needs testing
        "https://canberradigest.com.au/rss.xml",
        "https://hercanberra.com.au/feed",
        "https://citynews.com.au/feed",                            # needs testing
        "https://www.act.gov.au/our-canberra/rss-feed",
    ],

    # ------------------------------------------------------------------
    # 7. Sports (grounding fallback enabled)
    # ------------------------------------------------------------------
    "Sports": [
        # Middlesbrough FC
        "https://www.gazettelive.co.uk/all-about/middlesbrough-fc?service=rss",
        "https://www.gazettelive.co.uk/sport/?service=rss",
        "https://feeds.bbci.co.uk/sport/football/teams/middlesbrough/rss.xml",  # needs testing
        "https://feeds.bbci.co.uk/sport/football/english-championship/rss.xml",  # needs testing
        "https://www.theguardian.com/football/middlesbrough/rss",  # needs testing
        "https://www.thenorthernecho.co.uk/sport/rss",
        "https://www.fmttmboro.com/articles/feed/",               # needs testing
        # Canberra Raiders / NRL
        "https://www.raiders.com.au/news/feed",                   # needs testing
        "https://www.nrl.com/feed/",                               # needs testing
        "https://www.zerotackle.com/nrl/feed/",                   # needs testing
        "https://www.theroar.com.au/rugby-league/feed/",
        "https://www.seriousaboutrl.com/feed/",                   # needs testing
        "https://www.abc.net.au/news/feed/103728570/rss.xml",     # ABC Sport
        # Australian cricket
        "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
        "https://www.espncricinfo.com/rss/content/story/feeds/2.xml",  # needs testing
        "https://feeds.bbci.co.uk/sport/cricket/rss.xml",
        "https://www.theguardian.com/sport/cricket/rss",
        "https://www.theroar.com.au/cricket/feed/",
        "https://cricketetal.substack.com/feed",
        "https://www.wisden.com/feed",                             # needs testing
        "https://www.cricket.com.au/news/feed",                   # needs testing
    ],
}
