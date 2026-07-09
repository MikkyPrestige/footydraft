"""LLM client – Groq and Together (free tier)."""
from openai import OpenAI, RateLimitError
from config.settings import GROQ_API_KEY, TOGETHER_API_KEY

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

together_client = OpenAI(
    api_key=TOGETHER_API_KEY,
    base_url="https://api.together.xyz/v1",
)

DEFAULT_MODEL="llama-3.3-70b-versatile"
FALLBACK_MODEL="meta-llama/Llama-3.3-70B-Instruct-Turbo"
MAX_RETRIES=2

def generate_tweet(system_prompt: str, user_prompt: str, n: int = 1) -> list[str]:
    """Generate n tweet variants. Falls back to Together AI if Groq is rate‑limited."""
    variants = []
    for _ in range(n):
        generated = False
        # Try Groq first (primary)
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                response = client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=100,
                    temperature=0.9,
                )
                variants.append(response.choices[0].message.content.strip())
                generated = True
                break
            except RateLimitError:
                # Groq quota exhausted – switch to Together immediately
                print("Groq rate limited, trying Together fallback...")
                try:
                    response = together_client.chat.completions.create(
                        model=FALLBACK_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens=100,
                        temperature=0.9,
                    )
                    variants.append(response.choices[0].message.content.strip())
                    generated = True
                    break
                except Exception as fallback_error:
                    print(f"Together fallback also failed: {fallback_error}")
                    # If both Groq and Together failed, raise a fatal error
                    raise RuntimeError("LLM generation failed after all providers") from fallback_error
            except Exception as e:
                # Non‑rate‑limit error (e.g., network) – retry as usual
                if attempt <= MAX_RETRIES:
                    print(f"LLM call failed (attempt {attempt}/{MAX_RETRIES+1}): {e}. Retrying...")
                else:
                    raise RuntimeError(f"LLM generation failed after {MAX_RETRIES+1} attempts") from e
        if not generated:
            raise RuntimeError("LLM generation failed (exhausted all retries)")
    return variants