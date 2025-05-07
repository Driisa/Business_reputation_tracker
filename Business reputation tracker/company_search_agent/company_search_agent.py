# Company Reputation Search Agent (LLM + Google API + Analysis)
# Modular, extensible version with OpenAI query generation and sentiment-aware results

import requests
import json
import time
from datetime import datetime, timedelta
import os
import hashlib
from dotenv import load_dotenv
from openai import OpenAI

# ---------- CONFIGURATION ----------
REGIONS = {
    "global": {"lang": "en", "country": None},
    "us": {"lang": "en", "country": "US"},
    "uk": {"lang": "en", "country": "GB"},
    "dk": {"lang": "da", "country": "DK"},
    "de": {"lang": "de", "country": "DE"},
    "fr": {"lang": "fr", "country": "FR"},
    "jp": {"lang": "ja", "country": "JP"},
    "cn": {"lang": "zh", "country": "CN"},
}

REPUTATION_TERMS = {
    "en": ["reputation", "reviews", "news"],
    "da": ["omd\u00f8mme", "anmeldelser", "nyheder"],
    "de": ["ruf", "bewertungen", "nachrichten"],
    "fr": ["r\u00e9putation", "critiques", "actualit\u00e9s"],
    "ja": ["\u8a55\u5224", "\u30ec\u30d3\u30e5\u30fc", "\u30cb\u30e5\u30fc\u30b9"],
    "zh": ["\u58f0\u8a89", "\u8bc4\u8bba", "\u65b0\u95fb"]
}

# ---------- CLASS DEFINITION ----------
class CompanyReputationSearchAgent:
    def __init__(self, region="global", days_back=7, max_results=5, cache_enabled=True):
        load_dotenv()

        self.region = region
        self.lang = REGIONS[region]["lang"]
        self.country = REGIONS[region]["country"]
        self.days_back = days_back
        self.max_results = max_results
        self.cache_enabled = cache_enabled

        self.google_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.google_cx = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        self.openai_key = os.getenv("1OPENAI_API_KEY")

        self.client = OpenAI(api_key=self.openai_key) if self.openai_key else None
        self.api_calls = {"google": 0, "openai": 0}

        # Get script directory for file operations
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create cache directory in script folder
        self.cache_dir = os.path.join(self.script_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def load_companies(self, path="companies.json"):
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Construct the full path to the companies.json file
        full_path = os.path.join(script_dir, path)
        with open(full_path, encoding="utf-8") as f:
            return json.load(f)["companies"]

    def build_query_fallback(self, company):
        name = company.get("name", "")
        terms = REPUTATION_TERMS.get(self.lang, REPUTATION_TERMS["en"])
        return f'"{name}" ({" OR ".join(terms[:2])})'

    def build_query_llm(self, company):
        if not self.client:
            return self.build_query_fallback(company)

        prompt = [
            {"role": "system", "content": "You are an expert at crafting short, effective Google search queries to check public opinion about companies. Generate a keyword-style search query (max 12 words) to find recent news, reviews, or controversies related to a company. Use common public sentiment terms like 'reputation', 'review', 'scandal', 'praise', 'complaint', or 'lawsuit'. Include ORs to increase coverage. Quote the company name."},
            {"role": "user", "content": f"Company: {company.get('name')}, Industry: {company.get('industry', '')}, Country: {company.get('country', '')}, Services: {', '.join(company.get('main_services', []))}, Description: {company.get('description', '')}"}
        ]

        self.api_calls["openai"] += 1
        response = self.client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=prompt,
            temperature=0.3,
            max_tokens=60
        )

        return response.choices[0].message.content.strip()

    def cache_key(self, query):
        return hashlib.md5(query.encode()).hexdigest()

    def load_cache(self, key):
        path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(path): return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_cache(self, key, data):
        path = os.path.join(self.cache_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def search_google(self, query):
        cache_key = self.cache_key(query)
        if self.cache_enabled:
            cached = self.load_cache(cache_key)
            if cached: return cached

        params = {
            "q": query,
            "key": self.google_key,
            "cx": self.google_cx,
            "num": self.max_results,
            "sort": "date",
            "dateRestrict": f"d{self.days_back}",
        }
        if self.lang: params["lr"] = f"lang_{self.lang}"
        if self.country:
            params["gl"] = self.country.lower()
            params["cr"] = f"country{self.country}"

        self.api_calls["google"] += 1

        try:
            r = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"Search failed: {e}")
            return {"query": query, "results": []}

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "source": item.get("displayLink"),
                "published": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", "")
            })

        out = {"query": query, "results": results, "searched": datetime.now().isoformat()}
        if self.cache_enabled: self.save_cache(cache_key, out)
        return out

    def classify_relevance_with_llm(self, company_name, title, snippet, source):
        if not self.client or not snippet:
            return "unknown"

        prompt = [
            {"role": "system", "content": (
                "You are a reputation-focused search result classifier. Given a title, snippet, and source domain, classify if this result is about public perception, controversy, or reviews related to the company. Only label as 'relevant' if it directly relates to the company's reputation, public opinion, or legal/social impact. Respond with only 'relevant' or 'irrelevant'."
            )},
            {"role": "user", "content": f"""
        Company: {company_name}
        Title: "{title}"
        Snippet: "{snippet}"
        Source: "{source}"
        Label: 
        """}
        ]

        try:
            self.api_calls["openai"] += 1
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=prompt,
                temperature=0.0,
                max_tokens=5
            )
            label = response.choices[0].message.content.strip().lower()
            return label if label in {"relevant", "irrelevant"} else "unknown"
        except Exception as e:
            print(f"LLM relevance check error: {e}")
            return "unknown"

    def search_and_analyze(self, company):
        query = self.build_query_llm(company)
        result = self.search_google(query)
        result["company"] = company["name"]
        result["results_count"] = len(result["results"])

        for item in result["results"]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            source = item.get("source", "")
            label = self.classify_relevance_with_llm(company["name"], title, snippet, source)
            item["relevance"] = label
        
        # Then filter for relevant results
        result["results"] = [r for r in result["results"] if r.get("relevance") == "relevant"]
        result["results_count"] = len(result["results"])
        
        return result

    def analyze_summary(self, all_results):
        top_sources = {}
        company_stats = {}

        for r in all_results:
            company_stats[r["company"]] = len(r["results"])
            for m in r["results"]:
                src = m.get("source", "")
                top_sources[src] = top_sources.get(src, 0) + 1

        sorted_sources = dict(sorted(top_sources.items(), key=lambda x: x[1], reverse=True))
        return {"companies": company_stats, "top_sources": sorted_sources}

    def run(self, filepath):
        companies = self.load_companies(filepath)
        all_results = [self.search_and_analyze(c) for c in companies]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = os.path.join(self.script_dir, f"search_results.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({"results": all_results, "stats": self.api_calls}, f, indent=2)

        print(f"Saved results to {out_file}")
        summary = self.analyze_summary(all_results)
        print("Summary:", summary)
        return summary

# ---------- MAIN ----------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", default="companies.json")
    parser.add_argument("--region", default="global")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max", type=int, default=5)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    agent = CompanyReputationSearchAgent(
        region=args.region,
        days_back=args.days,
        max_results=args.max,
        cache_enabled=not args.no_cache
    )
    agent.run(args.companies)
