#!/usr/bin/env python3
"""
Fetch posts from r/ClaudeCode subreddit about Claude best practices.
This script uses PRAW in read-only mode (no authentication required).
"""

import praw
import json
from datetime import datetime

def fetch_claudecode_posts(limit=25):
    """
    Fetch recent posts from r/ClaudeCode.

    Args:
        limit: Number of posts to fetch (default: 25)
    """
    # Create a read-only Reddit instance (no authentication needed)
    reddit = praw.Reddit(
        client_id="your_client_id_here",  # You'll need to add this
        client_secret="your_client_secret_here",  # You'll need to add this
        user_agent="claude-best-practices-fetcher/1.0"
    )

    print(f"Fetching {limit} posts from r/ClaudeCode...\n")

    subreddit = reddit.subreddit("ClaudeCode")
    posts_data = []

    # Fetch hot posts
    for post in subreddit.hot(limit=limit):
        post_info = {
            "title": post.title,
            "author": str(post.author),
            "score": post.score,
            "url": post.url,
            "permalink": f"https://reddit.com{post.permalink}",
            "created_utc": datetime.fromtimestamp(post.created_utc).isoformat(),
            "num_comments": post.num_comments,
            "selftext": post.selftext,
            "link_flair_text": post.link_flair_text,
        }
        posts_data.append(post_info)

        print(f"📄 {post.title}")
        print(f"   👤 u/{post.author} | 👍 {post.score} | 💬 {post.num_comments} comments")
        print(f"   🔗 {post_info['permalink']}")
        print()

    # Save to JSON file
    output_file = "claudecode_posts.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(posts_data, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(posts_data)} posts to {output_file}")
    return posts_data

if __name__ == "__main__":
    # First, install PRAW: pip install praw
    fetch_claudecode_posts(limit=25)
