from flask import Flask, request, render_template, jsonify
from googleapiclient.discovery import build
import re
import emoji
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from langdetect import detect, LangDetectException

app = Flask(__name__)

def extract_video_id(url):
    video_id = None
    regex = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(regex, url)
    if match:
        video_id = match.group(1)
    return video_id

def fetch_comments(video_id, max_comments):
    youtube = build('youtube', 'v3', developerKey='AIzaSyBAo_ZUqUbvWk381swZN25ZwUnNlh-UGNA')
    comments = []
    nextPageToken = None
    while len(comments) < max_comments:
        request = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=min(200, max_comments - len(comments)),  # Adjust maxResults according to remaining comments
            pageToken=nextPageToken
        )
        response = request.execute()
        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']
            if 'authorChannelId' in comment:
                comments.append(comment['textDisplay'])
        nextPageToken = response.get('nextPageToken')
        if not nextPageToken:
            break
    return comments

def filter_comments(comments):
    hyperlink_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    threshold_ratio = 0.65
    relevant_comments = []
    for comment_text in comments:
        comment_text = comment_text.lower().strip()
        emojis = emoji.emoji_count(comment_text)
        text_characters = len(re.sub(r'\s', '', comment_text))
        try:
            if detect(comment_text) != 'en':  # Filter out non-English comments
                continue
        except LangDetectException:
            continue  # If language detection fails, skip the comment

        if (any(char.isalnum() for char in comment_text)) and not hyperlink_pattern.search(comment_text):
            if emojis == 0 or (text_characters / (text_characters + emojis)) > threshold_ratio:
                relevant_comments.append(comment_text)
    return relevant_comments

def analyze_sentiments(comments):
    sentiment_object = SentimentIntensityAnalyzer()
    emoji_positive = ['🔥', '😍', '🥳', '😃', '😊', '👍', '💯', '🥵', 'uffffff']
    emoji_negative = ['😡', '😠', '👎', '😢', '😞', '💔', 'mad', 'really mad', 'killing', 'no spiderman']
    polarity = []
    positive_comments = []
    negative_comments = []
    neutral_comments = []

    for comment in comments:
        sentiment_dict = sentiment_object.polarity_scores(comment)
        score = sentiment_dict['compound']

        # Adjust score based on presence of positive/negative emojis
        for emj in emoji_positive:
            if emj in comment:
                score += 0.2
        for emj in emoji_negative:
            if emj in comment:
                score -= 0.2

        polarity.append(score)
        if score > 0.05:
            positive_comments.append(comment)
        elif score < -0.05:
            negative_comments.append(comment)
        else:
            neutral_comments.append(comment)

    return polarity, positive_comments, negative_comments, neutral_comments

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    video_url = request.form['video_url']
    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"})

    # Get number of comments from the form input
    max_comments = int(request.form.get('comment_count', 800))

    comments = fetch_comments(video_id, max_comments)
    relevant_comments = filter_comments(comments)
    polarity, positive_comments, negative_comments, neutral_comments = analyze_sentiments(relevant_comments)

    avg_polarity = sum(polarity) / len(polarity)
    sentiment = "neutral"
    top_comments = neutral_comments[:5]
    if avg_polarity > 0.05:
        sentiment = "positive"
        top_comments = positive_comments[:5]
    elif avg_polarity < -0.05:
        sentiment = "negative"
        top_comments = negative_comments[:5]

    result = {
        "sentiment": sentiment,
        "top_comments": top_comments,
        "positive_count": len(positive_comments),
        "negative_count": len(negative_comments),
        "neutral_count": len(neutral_comments)
    }

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
