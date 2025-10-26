import trafilatura

url = "https://overreacted.io/open-social/"
downloaded = trafilatura.fetch_url(url)
text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
print(text)
