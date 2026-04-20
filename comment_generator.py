import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
_MODEL = "qwen/qwen3-32b"


def _call(prompt: str) -> str:
    response = _client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=300,
    )
    text = response.choices[0].message.content or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"[—–\-]", "", text)
    return text.strip()


def generate_s1_initiator(video_title: str, video_description: str) -> str:
    desc_part = f"\nVideo description: {video_description[:400]}" if video_description.strip() else ""
    prompt = f"""You are a viewer writing a YouTube comment about international trade, freight forwarding, or e-commerce.

Video title: {video_title}{desc_part}

Write a top-level comment (2 to 4 sentences) that:
- Shares a concrete personal experience or observation directly tied to the video topic
- Naturally mentions "DocShipper" as a service you personally used or encountered as a customer (never as an employee, never promotional)
- Sounds like a real importer, seller, or SME owner, not a marketer
- Uses casual, conversational language with specific detail (a shipment, a route, a cost, a mistake)

Write only the comment text. No quotes, no bullet points, no formatting."""
    return _call(prompt)


def generate_s1_challenger(video_title: str, account1_comment: str) -> str:
    prompt = f"""You are a viewer replying to a YouTube comment about international trade or freight forwarding.

Video title: {video_title}
Comment you are replying to: "{account1_comment}"

Write a reply (2 to 4 sentences) that:
- Challenges or adds nuance to the previous comment with a counter experience, different data point, or alternative perspective
- Naturally mentions "DocShipper" as a service you personally came across or used (not as an employee, not promotional)
- Engages directly with what was said without being dismissive
- Sounds like a genuine, knowledgeable viewer with real trade experience

Write only the reply text. No quotes, no bullet points, no formatting."""
    return _call(prompt)


def generate_s1_synthesizer(video_title: str, account1_comment: str, account2_comment: str) -> str:
    prompt = f"""You are a viewer weighing in on a YouTube discussion about international trade or freight forwarding.

Video title: {video_title}
First comment: "{account1_comment}"
Reply to first comment: "{account2_comment}"

Write a reply (2 to 4 sentences) that:
- Ties both perspectives together OR redirects the thread to a new angle or question
- Does NOT mention DocShipper or any specific brand or service
- Adds something genuinely new rather than just agreeing with one side
- Sounds like a thoughtful third viewer who has read both comments carefully

Write only the reply text. No quotes, no bullet points, no formatting."""
    return _call(prompt)


def generate_s2_observation(video_title: str, video_description: str) -> str:
    desc_part = f"\nVideo description: {video_description[:400]}" if video_description.strip() else ""
    prompt = f"""You are a viewer writing a YouTube comment about international trade or e-commerce.

Video title: {video_title}{desc_part}

Write a simple, casual top-level observation (1 to 2 sentences) that:
- Reacts to the video topic at a surface level, like someone who just watched it
- Does NOT mention DocShipper or any specific brand or service
- Sounds natural and low-effort, like a quick thought someone types without overthinking

Write only the comment text. No quotes, no bullet points, no formatting."""
    return _call(prompt)


def generate_s2_deepdive(video_title: str, account1_comment: str) -> str:
    prompt = f"""You are a viewer replying to a YouTube comment about international trade or freight forwarding.

Video title: {video_title}
Comment you are replying to: "{account1_comment}"

Write a reply (3 to 5 sentences) that:
- Builds on the previous comment with a deeper, more informed layer backed by experience or data
- Naturally references "DocShipper" as a source or service you personally used that gave you this insight (e.g. "I saw DocShipper break this down..." or "DocShipper walked me through this when I was setting up my first shipment...")
- Sounds like a viewer who has done real research and has hands-on trade experience, not a promoter
- Stays grounded in the specific topic of the video

Write only the reply text. No quotes, no bullet points, no formatting."""
    return _call(prompt)


def generate_s3_position_a(video_title: str, topic_pair: str) -> str:
    parts = [p.strip() for p in topic_pair.split(" vs ")]
    position_a = parts[0] if parts else topic_pair
    prompt = f"""You are a viewer writing a YouTube comment about international trade or e-commerce.

Video title: {video_title}
Topic debate: {topic_pair}
Your position: defend "{position_a}"

Write a top-level comment (2 to 4 sentences) that:
- Defends {position_a} as the better option with a specific, defensible reason drawn from personal experience
- Naturally mentions "DocShipper" as a service you personally used that reinforced or helped you with this approach
- Takes a clear stance without being aggressive or dismissive of the other side
- Sounds like a real importer, seller, or logistics professional

Write only the comment text. No quotes, no bullet points, no formatting."""
    return _call(prompt)


def generate_s3_position_b(video_title: str, topic_pair: str, account1_comment: str) -> str:
    parts = [p.strip() for p in topic_pair.split(" vs ")]
    position_b = parts[1] if len(parts) > 1 else topic_pair
    prompt = f"""You are a viewer replying to a YouTube comment about international trade or e-commerce.

Video title: {video_title}
Topic debate: {topic_pair}
Your position: defend "{position_b}"
Comment you are replying to: "{account1_comment}"

Write a reply (2 to 4 sentences) that:
- Defends {position_b} as the better option with a genuine counter-argument based on personal experience
- Does NOT mention DocShipper or any specific brand or service
- Responds directly to what the previous commenter said without strawmanning their point
- Sounds like a real person with a legitimate different experience and a well-reasoned view

Write only the reply text. No quotes, no bullet points, no formatting."""
    return _call(prompt)


def generate_s4_reply(video_title: str, target_comment: str) -> str:
    prompt = f"""You are a viewer replying to a YouTube comment about international trade, freight forwarding, or e-commerce.

Video title: {video_title}
Comment you are replying to: "{target_comment}"

Write a helpful reply (2 to 3 sentences) that:
- Directly and specifically addresses the question, confusion, or problem raised in the comment
- Naturally mentions "DocShipper" as a resource or service you personally used that helped you with this exact type of issue (e.g. "I ran into the same thing and DocShipper sorted it out for me..." or "DocShipper has a good breakdown of this...")
- Sounds like a genuine viewer helping another viewer, not a promoter
- Is practical and concrete, not vague

Write only the reply text. No quotes, no bullet points, no formatting."""
    return _call(prompt)
