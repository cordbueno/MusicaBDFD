
from youtube_search import YoutubeSearch

def youtube_search(query):
    results = YoutubeSearch(query, max_results=1).to_dict()

    if not results:
        return None

    return "https://www.youtube.com/watch?v=" + results[0]["id"]

