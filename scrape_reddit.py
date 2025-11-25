#!/usr/bin/env python3
"""
Simple web scraper for r/ClaudeCode subreddit.
Fetches posts without requiring Reddit API credentials.
"""

import requests
import json
from datetime import datetime
from typing import List, Dict
import time


def scrape_subreddit(subreddit_name: str = "ClaudeCode", limit: int = 25, sort: str = "hot", time_filter: str = "all") -> List[Dict]:
    """
    Scrape posts from a subreddit using Reddit's old.reddit.com interface.

    Args:
        subreddit_name: Name of the subreddit (default: ClaudeCode)
        limit: Number of posts to fetch (default: 25)
        sort: Sort method - "hot", "new", "top", "rising" (default: hot)
        time_filter: Time filter for "top" sort - "hour", "day", "week", "month", "year", "all" (default: all)

    Returns:
        List of post dictionaries
    """
    if sort == "top":
        url = f"https://old.reddit.com/r/{subreddit_name}/top/.json"
    elif sort == "new":
        url = f"https://old.reddit.com/r/{subreddit_name}/new/.json"
    elif sort == "rising":
        url = f"https://old.reddit.com/r/{subreddit_name}/rising/.json"
    else:
        url = f"https://old.reddit.com/r/{subreddit_name}/.json"

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    params = {
        'limit': limit
    }

    if sort == "top":
        params['t'] = time_filter

    print(f"Fetching posts from r/{subreddit_name} (sort: {sort}, time: {time_filter})...")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        posts = data['data']['children']

        posts_data = []

        for post in posts:
            post_data = post['data']

            post_info = {
                'title': post_data.get('title', ''),
                'author': post_data.get('author', '[deleted]'),
                'score': post_data.get('score', 0),
                'url': post_data.get('url', ''),
                'permalink': f"https://reddit.com{post_data.get('permalink', '')}",
                'created_utc': datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                'num_comments': post_data.get('num_comments', 0),
                'selftext': post_data.get('selftext', ''),
                'link_flair_text': post_data.get('link_flair_text', ''),
                'id': post_data.get('id', ''),
                'is_self': post_data.get('is_self', False),
            }

            posts_data.append(post_info)

            print(f"\n📄 {post_info['title']}")
            print(f"   👤 u/{post_info['author']} | 👍 {post_info['score']} | 💬 {post_info['num_comments']} comments")
            print(f"   🔗 {post_info['permalink']}")
            if post_info['selftext']:
                preview = post_info['selftext'][:100].replace('\n', ' ')
                print(f"   📝 {preview}{'...' if len(post_info['selftext']) > 100 else ''}")

        return posts_data

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
        return []


def scrape_post_comments(post_id: str, subreddit_name: str = "ClaudeCode") -> Dict:
    """
    Scrape comments from a specific post.

    Args:
        post_id: Reddit post ID
        subreddit_name: Name of the subreddit

    Returns:
        Dictionary containing post and comments data
    """
    url = f"https://old.reddit.com/r/{subreddit_name}/comments/{post_id}/.json"

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        # First element is the post, second is comments
        post_data = data[0]['data']['children'][0]['data']
        comments_data = data[1]['data']['children']

        comments = []
        for comment in comments_data:
            if comment['kind'] == 't1':  # t1 is a comment
                comment_data = comment['data']
                comments.append({
                    'author': comment_data.get('author', '[deleted]'),
                    'body': comment_data.get('body', ''),
                    'score': comment_data.get('score', 0),
                    'created_utc': datetime.fromtimestamp(comment_data.get('created_utc', 0)).isoformat(),
                })

        return {
            'post': {
                'title': post_data.get('title', ''),
                'selftext': post_data.get('selftext', ''),
                'author': post_data.get('author', '[deleted]'),
            },
            'comments': comments
        }

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching comments: {e}")
        return {}


def main():
    """Main function to scrape r/ClaudeCode posts."""

    # Scrape top posts from the past month
    posts = scrape_subreddit(subreddit_name="ClaudeCode", limit=100, sort="top", time_filter="month")

    if not posts:
        print("\n❌ Failed to fetch posts. Reddit might be blocking requests.")
        print("Try again in a few minutes or reduce the limit.")
        return

    # Save posts to JSON
    output_file = "claudecode_top_month.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Successfully scraped {len(posts)} posts")
    print(f"📁 Saved to {output_file}")

    # Ask if user wants to fetch comments for specific posts
    print("\n" + "="*60)
    print("To fetch comments for a specific post, note its ID from the JSON file")
    print("and run: scrape_post_comments('post_id_here')")


if __name__ == "__main__":
    main()
