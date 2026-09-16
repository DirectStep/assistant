from app.news.providers import RssSource
from app.schemas.news import NewsCategory

DEFAULT_RSS_SOURCES = [
    RssSource("OpenAI", "https://openai.com/news/rss.xml", NewsCategory.AI),
    RssSource("Google DeepMind", "https://deepmind.google/blog/rss.xml", NewsCategory.AI),
    RssSource("NVIDIA", "https://blogs.nvidia.com/feed/", NewsCategory.AI),
    RssSource("Hugging Face", "https://huggingface.co/blog/feed.xml", NewsCategory.AI),
    RssSource("The Verge", "https://www.theverge.com/rss/index.xml", NewsCategory.AI),
    RssSource("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", NewsCategory.AI),
    RssSource(
        "РБК", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", NewsCategory.RUSSIAN_MARKET
    ),
    RssSource("Коммерсантъ", "https://www.kommersant.ru/RSS/news.xml", NewsCategory.RUSSIAN_MARKET),
    RssSource("ТАСС", "https://tass.ru/rss/v2.xml", NewsCategory.GEOPOLITICS),
    RssSource(
        "CNBC", "https://www.cnbc.com/id/100727362/device/rss/rss.html", NewsCategory.GEOPOLITICS
    ),
    RssSource("TechCrunch", "https://techcrunch.com/feed/", NewsCategory.STARTUPS),
    RssSource("Sifted", "https://sifted.eu/feed", NewsCategory.STARTUPS),
    RssSource("EU-Startups", "https://www.eu-startups.com/feed/", NewsCategory.STARTUPS),
    RssSource("Hacker News", "https://hnrss.org/frontpage", NewsCategory.STARTUPS),
]
