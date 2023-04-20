# Tao Tie (饕餮)
Let taotie be your helper to consume the information.

<p align="center">
    <img src="./images/taotie.png" alt="drawing"/>
</p>



<p align="center">
    <img src="./images/architecture.png" alt="drawing"/>
    <br>The architecture of TaoTie
</p>

## Example
### Subscribe from twitter stream, github trend, and http service, and then dump the summarization to notion.
The example code can be seen in [examples/summarize_to_notion/example.py](examples/info_summarizer.py)

This example shows how to subscribe from both passive and active sources, call the LLM agent, and then dump to the storage.

### 1. Add your api tokens in .env.

The template is available at .env.template.

```bash
OPENAI_API_KEY=aaa
TWITTER_BEARER_TOKEN=bbb  # Please follow https://developer.twitter.com/en/portal.

NOTION_TOKEN=ccc  # Please follow https://developers.notion.com/docs/create-a-notion-integration.
NOTION_ROOT_PAGE_ID=ddd  # The id of the page where you want to dump the summary.
```

### 2. Build the example:
```bash
# Build the docker image
docker build -t summarize-to-notion -f examples/summarize_to_notion/Dockerfile .
```

### 3. Run the example:
```bash
docker run -it summarize_to_notion
```

When the program runs, it will subscribe from twitter stream, github trend, and http service, and then dump the summarization to notion.
It also setup a http server listening on port 6543 to receive the ad-hoc summarization request. 
For example, if you see a blog post you want to summarize, you can send a request to the server as follows:
```bash
curl -X POST -H "Content-Type: application/json" -d '{"url": "https://www.harmdevries.com/post/model-size-vs-compute-overhead"}' http://localhost:6543/api/v1/url
```

A more user friendly tool is not yet available. But you can use the [Postman](https://www.postman.com/) to send the request.

**Note: Please remember to stop the container after a while. Otherwise, your OPENAI bill will grow continously.**

The example output can be seen as follows:

<p align="center">
    <img src="./examples/summarize_to_notion/example.png" alt="drawing"/>
    <br>Output of the info summarizer example
</p>

In your notion, you can see the contents added.

<p align="center">
    <img src="./images/web-page.png" alt="drawing"/>
    <br>Summarized Web-page (Medium post)
</p>

<p align="center">
    <img src="./images/github-repo.png" alt="drawing"/>
    <br>Summarized Github-repo (Github Trends)
</p>