#!/usr/bin/env python3
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import json
import os
import argparse
import requests
import time
import re
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from data.pipeline_db_config import SessionLocal
from data.pipeline_db_models import SearchResult
from data.company_repository import get_all_companies, get_company_by_id
from logging_config import setup_logging

# Setup logging
loggers = setup_logging()
logger = loggers["search"]
api_logger = loggers["api"]
db_logger = loggers["database"]

# Load environment variables
load_dotenv()

def deduplicate_similar_content(results: List[Dict[str, Any]], threshold: float = 0.6) -> List[Dict[str, Any]]:
    """
    Remove duplicate content based on similarity across multiple dimensions.
    Works for any content type, not just specific platforms.
    
    Args:
        results: List of search result dictionaries
        threshold: Similarity threshold (0.0 to 1.0) for considering items as duplicates
        
    Returns:
        List of deduplicated search results
    """
    if not results:
        return []
        
    logger.info(f"Starting deduplication of {len(results)} results")
    unique_results = []
    seen_signatures = set()
    seen_normalized_urls = set()
    
    # Extract domains for domain-specific handling
    domain_counts = {}
    for result in results:
        url = result.get("link", "")
        domain_match = re.search(r'https?://(?:www\.|m\.)?([^/]+)', url)
        if domain_match:
            domain = domain_match.group(1)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
    
    # For domains with multiple results, we'll be more aggressive with deduplication
    common_domains = {domain for domain, count in domain_counts.items() if count > 1}
    logger.debug(f"Found {len(common_domains)} domains with multiple results")
    
    # Function to compute text similarity
    def compute_similarity(text1, text2):
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()
    
    # Process each result
    for result in results:
        url = result.get("link", "")
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()
        
        # 1. URL-based deduplication (normalize URLs)
        domain_match = re.search(r'https?://(?:www\.|m\.)?([^/]+)', url)
        if domain_match:
            domain = domain_match.group(1)
            
            # More aggressive normalization for common domains
            if domain in common_domains:
                # Extract meaningful segments from the URL
                path_match = re.search(r'https?://(?:www\.|m\.)?[^/]+(/[^?#]+)', url)
                if path_match:
                    path = path_match.group(1)
                    # Remove common URL elements like /posts/, /photos/, etc.
                    path = re.sub(r'/(posts|photos|articles|pages)/', '/', path)
                    # Extract only alphanumeric components of path
                    path_components = re.findall(r'/([a-zA-Z0-9_-]+)', path)
                    if path_components:
                        normalized_url = f"{domain}:{'-'.join(path_components)}"
                        if normalized_url in seen_normalized_urls:
                            logger.debug(f"Skipping URL pattern duplicate: {url}")
                            continue
                        seen_normalized_urls.add(normalized_url)
        
        # 2. Content-based deduplication
        content = f"{title} {snippet}"
        
        # 2.1 Extract significant words (filtering out common words)
        common_words = {"the", "a", "an", "and", "or", "but", "is", "in", "on", "at", "to", "for", "with", "by", "about", "as", "of"}
        words = [word for word in re.findall(r'\b\w+\b', content.lower()) if len(word) > 3 and word not in common_words]
        
        # 2.2 Get most frequent/important words
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency and take top words
        significant_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        significant_words = [word for word, _ in significant_words]
        
        # 2.3 Create content signature from significant words
        if significant_words:
            content_signature = "-".join(sorted(significant_words))
            if content_signature in seen_signatures:
                logger.debug(f"Skipping content signature duplicate: {title[:30]}...")
                continue
            seen_signatures.add(content_signature)
        
        # 2.4 Full content similarity check against existing unique results
        is_duplicate = False
        for unique_result in unique_results:
            unique_title = unique_result.get("title", "").lower()
            unique_snippet = unique_result.get("snippet", "").lower()
            
            # Compute similarity scores
            title_sim = compute_similarity(title, unique_title)
            snippet_sim = compute_similarity(snippet[:100], unique_snippet[:100])
            
            # Weight title more heavily than snippet
            combined_sim = (title_sim * 0.7) + (snippet_sim * 0.3)
            
            if combined_sim > threshold:
                logger.debug(f"Skipping content similarity duplicate ({combined_sim:.2f}): {title[:30]}...")
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_results.append(result)
    
    logger.info(f"After content deduplication: {len(results)} results -> {len(unique_results)} unique results")
    return unique_results

def enrich_company_info(company: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich company information to provide better context for analysis."""
    # Make a copy of the company to avoid modifying the original
    enriched = company.copy()
    
    # Set default fields if missing
    if "industry" not in enriched or not enriched["industry"]:
        enriched["industry"] = "Unknown"
    
    if "description" not in enriched or not enriched["description"]:
        company_name = enriched.get("company_name", "")
        industry = enriched.get("industry", "")
        # Create a basic description based on company name and industry
        if industry and industry != "Unknown":
            enriched["description"] = f"{company_name} is a company in the {industry} industry."
        else:
            enriched["description"] = f"{company_name} is a business organization."
    
    if "services" not in enriched or not enriched["services"]:
        enriched["services"] = []
    
    if "location" not in enriched:
        enriched["location"] = ""
    
    # Add basic business categories that might be relevant
    business_categories = {
        "energy": ["electricity", "gas", "renewable energy", "power", "utilities", "energy services"],
        "technology": ["software", "hardware", "IT services", "digital solutions", "tech consulting"],
        "retail": ["stores", "shopping", "consumer goods", "e-commerce", "merchandising"],
        "finance": ["banking", "investments", "financial services", "insurance", "wealth management"],
        "healthcare": ["medical services", "patient care", "pharmaceuticals", "health technology"],
        "manufacturing": ["production", "industrial goods", "factories", "assembly", "materials"],
        "telecommunications": ["networks", "connectivity", "internet services", "mobile", "communication"],
        "food": ["restaurants", "food service", "catering", "food products", "beverages"],
        "transportation": ["logistics", "shipping", "freight", "travel", "mobility"],
        "construction": ["building", "infrastructure", "development", "engineering", "real estate"],
        "agriculture": ["farming", "crops", "livestock", "agricultural products", "food production"],
        "education": ["schools", "teaching", "training", "learning", "educational services"],
        "entertainment": ["media", "events", "recreation", "content creation", "leisure activities"]
    }
    
    # If industry matches our categories, add related terms that might help with context
    industry_lower = enriched.get("industry", "").lower()
    for category, terms in business_categories.items():
        if category in industry_lower:
            if "industry_terms" not in enriched:
                enriched["industry_terms"] = []
            enriched["industry_terms"].extend(terms)
    
    return enriched

def get_companies_from_db(specific_company: str = None) -> List[Dict[str, Any]]:
    """Get companies from the database."""
    try:
        if specific_company:
            # If specific company is provided, search by name
            companies = get_all_companies()
            return [c for c in companies if c['company_name'] == specific_company]
        else:
            return get_all_companies()
    except Exception as e:
        logger.error(f"Error loading companies from database: {e}")
        return []

def extract_published_date(snippet: str, current_date: datetime) -> Optional[str]:
    """
    Extract published date from a snippet containing relative time references.
    Returns a formatted date string (YYYY-MM-DD) or None if no date reference is found.
    """
    # Look for common relative time patterns
    # e.g., "5 days ago", "2 hours ago", "1 week ago", "3 months ago"
    relative_date_patterns = [
        (r'(\d+)\s+day(?:s)?\s+ago', lambda x: current_date - timedelta(days=int(x))),
        (r'(\d+)\s+hour(?:s)?\s+ago', lambda x: current_date - timedelta(hours=int(x))),
        (r'(\d+)\s+minute(?:s)?\s+ago', lambda x: current_date - timedelta(minutes=int(x))),
        (r'(\d+)\s+week(?:s)?\s+ago', lambda x: current_date - timedelta(weeks=int(x))),
        (r'(\d+)\s+month(?:s)?\s+ago', lambda x: current_date - timedelta(days=int(x)*30)),  # Approximation
        (r'yesterday', lambda x: current_date - timedelta(days=1)),
        (r'today', lambda x: current_date),
    ]
    
    # Try each pattern
    for pattern, time_delta_func in relative_date_patterns:
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match:
            # If the pattern has a capture group, use it; otherwise None
            value = match.group(1) if len(match.groups()) > 0 else None
            date_obj = time_delta_func(value)
            return date_obj.strftime("%Y-%m-%d")
    
    # If no relative date pattern is found, return None
    return None

def search_company(
    company: Dict[str, Any],
    api_key: str,
    cse_id: str,
    date_restrict: str = "d7",
    total_results: int = 10  # Total desired results
) -> Optional[Dict[str, Any]]:
    """Search for a company and return unfiltered results from the last 7 day."""
    company_name = company.get("company_name", "").strip()
    if not company_name:
        logger.warning("Empty company name provided")
        return None

    company_id = company.get("company_id") or company_name.replace(" ", "_")
    
    # Improve query specificity by adding industry context if available
    industry = company.get("industry", "").strip()
    location = company.get("location", "").strip()
    
    # Basic query with company name in quotes for exact match
    query = f'"{company_name}"'
    
    # Add additional context to query if available to improve relevance
    if industry:
        # Extract first two industry keywords to avoid overly specific queries
        industry_keywords = industry.split()[:2]
        query += f" {' '.join(industry_keywords)}"
    if location:
        query += f" {location}"
    
    # Track URLs to avoid duplicates
    seen_urls = set()
    
    # Collect all results
    all_items = []
    
    # Calculate number of pages needed (10 results per page maximum)
    # Request more pages than strictly needed to account for duplicates or filtered results
    pages_needed = (total_results + 9) // 10 + 1  # Ceiling division + 1 extra page
    max_pages = 5  # Set a reasonable upper limit to avoid excessive API usage
    pages_needed = min(pages_needed, max_pages)
    
    for page in range(pages_needed):
        start_index = page * 10 + 1  # Google's API uses 1-based indexing
        
        # Prepare search request
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": 10,  # Maximum allowed by the API
            "start": start_index,
            "dateRestrict": date_restrict,
        }

        # Perform the search
        logger.info(f"Searching for: {company_name} (last 7 days) - Page {page+1}/{pages_needed}")
        try:
            response = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            search_data = response.json()
            
            # Add items from this page to our collection, avoiding duplicates
            items = search_data.get("items", [])
            
            for item in items:
                # Skip duplicates based on URL
                item_url = item.get("link", "")
                if item_url in seen_urls:
                    continue
                    
                seen_urls.add(item_url)
                all_items.append(item)
            
            # If we've reached our target or received fewer than 10 results, stop
            if len(all_items) >= total_results or len(items) < 10:
                break
                
            # Add a short delay between requests to be respectful of API limits
            if page < pages_needed - 1:
                time.sleep(0.5)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Search API error on page {page+1}: {e}")
            # Continue with results we have so far instead of returning None
            break

    # Process results as before, but limit to the requested total
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    processed_results = []
    for item in all_items[:total_results]:
        snippet = item.get("snippet", "")
        published_date = extract_published_date(snippet, today)
        
        processed_results.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": snippet,
            "date": today_str,
            "published_date": published_date
        })

    results = {
        "company_id": company_id,
        "company_name": company_name,
        "query": query,  # Include the actual query used
        "results": processed_results,
        "count": len(processed_results),
        "timestamp": datetime.now().isoformat()
    }

    logger.info(f"  Found {len(processed_results)} search results for {company_name}")
    return results


def create_analysis_prompt(company: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Create a well-structured prompt for analyzing a single search result."""
    # Extract company information
    company_name = company.get("company_name", "")
    industry = company.get("industry", "")
    description = company.get("description", "")
    services = company.get("services", [])
    industry_terms = company.get("industry_terms", [])
    location = company.get("location", "")
    
    # Format search result
    title = result.get("title", "")
    link = result.get("link", "")
    snippet = result.get("snippet", "")
    published_date = result.get("published_date", "Unknown")

    # Add industry terms if available
    industry_context = ""
    if industry_terms:
        industry_context = f"Industry-Related Terms: {', '.join(industry_terms)}\n"
    
    # Add location context if available
    location_context = ""
    if location:
        location_context = f"Location: {location}\n"

    # Construct prompt
    prompt = f"""You are an AI expert at analyzing search results and determining their relevance to a specific company.

COMPANY INFORMATION:
Company Name: {company_name}
Industry: {industry}
Description: {description}
Services Provided: {', '.join(services)}
{location_context}
{industry_context}

SEARCH RESULT:
Title: {title}
Link: {link}
Snippet: {snippet}
Published Date: {published_date}

TASK:
Analyze this search result and determine its relevance to {company_name} based on their specific business, industry, and services.

IMPORTANT GUIDELINES:
1. Consider any news about partnerships, collaborations, or business relationships as highly relevant
2. Content about the company's core products, services, or operational areas is highly relevant
3. Information about industry trends, regulations, or market developments that would affect this company is relevant
4. Consider geographical relevance - local news in the company's area of operation may be relevant
5. Business strategy, leadership changes, or company milestones are relevant
6. Judge content in the context of THIS SPECIFIC COMPANY'S business model and services
7. Remember that relevance can cross traditional industry boundaries - a restaurant chain partnering with an energy company on sustainability would be relevant to both
8. BE CAREFUL: There might be other companies, products, or people with the same name - make sure the content is about {company_name} specifically
9. If the result appears to be about a different entity with the same name (like a person, unrelated business, etc.), mark it as IRRELEVANT
10. If the result appears to be about a job, job posting, "Join Our Team" or job application, mark it as IRRELEVANT

Evaluate whether this content is:
1. HIGHLY RELEVANT: Directly about the company's activities, partnerships, products, services or significant industry developments
2. RELEVANT: Connected to the company's business interests, market position, or industry
3. SOMEWHAT RELEVANT: Tangentially related to the company or its industry
4. IRRELEVANT: Not connected to the company's business in any meaningful way

Respond with a JSON object in the following format:
{{
  "relevance_category": "HIGHLY_RELEVANT|RELEVANT|SOMEWHAT_RELEVANT|IRRELEVANT",
  "relevance_score": float,  // A value between 0.0 and 1.0 indicating relevance
  "reasoning": "string",     // Brief explanation of your reasoning
  "key_information": "string", // Key information about the company from this result
  "content_type": "string"   // E.g., "partnership announcement", "product news", "industry trend", etc.
}}
"""
    
    return prompt

def analyze_with_openai(prompt: str, api_key: str, model: str = "gpt-4.1-nano") -> Dict[str, Any]:
    """Use OpenAI to analyze a search result."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 800,
        "response_format": {"type": "json_object"}
    }
    
    try:
        api_logger.info(f"Starting OpenAI analysis with model: {model}")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        response_data = response.json()
        content = response_data["choices"][0]["message"]["content"]
        
        # Extract JSON from the response
        try:
            # Try to parse the whole response as JSON
            analysis = json.loads(content)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON portion using string manipulation
            api_logger.warning("Full response was not valid JSON, attempting to extract JSON portion")
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                try:
                    analysis = json.loads(json_str)
                except json.JSONDecodeError:
                    api_logger.error("Could not extract valid JSON from response")
                    return {"relevance_category": "UNKNOWN", "relevance_score": 0.0, 
                            "reasoning": "Error parsing response", "key_information": ""}
            else:
                api_logger.error("No JSON object found in response")
                return {"relevance_category": "UNKNOWN", "relevance_score": 0.0, 
                        "reasoning": "Error parsing response", "key_information": ""}
                    
        return analysis
    
    except requests.exceptions.RequestException as e:
        api_logger.error(f"API request error: {e}")
    except Exception as e:
        api_logger.error(f"Error processing OpenAI response: {e}")
    
    return {"relevance_category": "UNKNOWN", "relevance_score": 0.0, 
            "reasoning": "Error processing response", "key_information": ""}

def analyze_search_results(
    company: Dict[str, Any], 
    results: Dict[str, Any],
    openai_api_key: str,
    openai_model: str = "gpt-4.1-nano",
    batch_size: int = 3,  # How many results to analyze in parallel
    min_relevance_score: float = 0.15  # Minimum relevance score to include
) -> Dict[str, Any]:
    """Analyze search results and categorize by relevance."""
    company_name = company.get("company_name", "")
    search_results = results.get("results", [])
    
    if not search_results:
        logger.warning(f"No search results to analyze for {company_name}")
        return results
    
    categorized_results = {
        "highly_relevant": [],
        "relevant": [],
        "somewhat_relevant": [],
        "irrelevant": []
    }
    
    all_analyzed_results = []
    
    logger.info(f"Analyzing {len(search_results)} search results for {company_name}...")
    
    # Process results in batches to avoid overwhelming the API
    for i in range(0, len(search_results), batch_size):
        batch = search_results[i:i+batch_size]
        
        for result in batch:
            # Create prompt and analyze with OpenAI
            prompt = create_analysis_prompt(company, result)
            analysis = analyze_with_openai(prompt, openai_api_key, openai_model)
            
            # Add analysis data to the result
            result["analysis"] = analysis
            all_analyzed_results.append(result)
            
            # Log brief info about analysis
            title = result.get("title", "")[:40] + "..." if len(result.get("title", "")) > 40 else result.get("title", "")
            category = analysis.get("relevance_category", "UNKNOWN")
            score = analysis.get("relevance_score", 0.0)
            published_date = result.get("published_date", "Unknown date")
            logger.info(f"  Analyzed: '{title}' - {category} ({score:.2f}) - Published: {published_date}")
        
        # Delay between batches to respect rate limits
        if i + batch_size < len(search_results):
            time.sleep(1.0)
    
    # Filter out low relevance results
    filtered_results = []
    for result in all_analyzed_results:
        analysis = result.get("analysis", {})
        score = analysis.get("relevance_score", 0.0)
        category = analysis.get("relevance_category", "").lower()
        
        # Keep all results that are not explicitly irrelevant, or that meet minimum score
        if category != "irrelevant" or score >= min_relevance_score:
            filtered_results.append(result)
        else:
            title = result.get("title", "")[:30] + "..." if len(result.get("title", "")) > 30 else result.get("title", "")
            logger.debug(f"Filtered out low relevance result: {title} (score: {score:.2f})")
    
    # Categorize the filtered results
    for result in filtered_results:
        analysis = result.get("analysis", {})
        category = analysis.get("relevance_category", "UNKNOWN").lower()
        
        if category == "highly_relevant":
            categorized_results["highly_relevant"].append(result)
        elif category == "relevant":
            categorized_results["relevant"].append(result)
        elif category == "somewhat_relevant":
            categorized_results["somewhat_relevant"].append(result)
        elif category == "irrelevant":
            categorized_results["irrelevant"].append(result)
        else:
            # If unknown category, use the score to place it
            score = analysis.get("relevance_score", 0.0)
            if score >= 0.8:
                categorized_results["highly_relevant"].append(result)
            elif score >= 0.6:
                categorized_results["relevant"].append(result)
            elif score >= 0.3:
                categorized_results["somewhat_relevant"].append(result)
            else:
                categorized_results["irrelevant"].append(result)
    
    # Update results with categorized information
    analyzed_results = {
        "company_id": results.get("company_id", ""),
        "company_name": company_name,
        "query": results.get("query", ""),
        "timestamp": datetime.now().isoformat(),
        "total_count": len(search_results),
        "filtered_count": len(filtered_results),
        "categorized_results": categorized_results,
        "relevant_count": len(categorized_results["highly_relevant"]) + len(categorized_results["relevant"])
    }
    
    # Log summary of analysis
    logger.info(f"Analysis summary for {company_name}:")
    logger.info(f"  Original results: {len(search_results)}")
    logger.info(f"  After filtering (min score {min_relevance_score}): {len(filtered_results)}")
    logger.info(f"  Highly Relevant: {len(categorized_results['highly_relevant'])}")
    logger.info(f"  Relevant: {len(categorized_results['relevant'])}")
    logger.info(f"  Somewhat Relevant: {len(categorized_results['somewhat_relevant'])}")
    logger.info(f"  Irrelevant: {len(categorized_results['irrelevant'])}")
    
    return analyzed_results

def format_display_results(analyzed_results: Dict[str, Any], display_limit: int = None) -> str:
    """Format analyzed search results for display."""
    company_name = analyzed_results.get("company_name", "")
    categorized_results = analyzed_results.get("categorized_results", {})
    query = analyzed_results.get("query", "")
    total_count = analyzed_results.get("total_count", 0)
    filtered_count = analyzed_results.get("filtered_count", 0)
    
    highly_relevant = categorized_results.get("highly_relevant", [])
    relevant = categorized_results.get("relevant", [])
    somewhat_relevant = categorized_results.get("somewhat_relevant", [])
    
    output = f"\n=== Analyzed Search Results for {company_name} ===\n"
    
    # Display query and counts
    output += f"Search Query: {query}\n"
    output += f"Total Results: {total_count}\n"
    output += f"After Filtering: {filtered_count}\n\n"
    
    # Display summary
    output += f"Highly Relevant: {len(highly_relevant)}\n"
    output += f"Relevant: {len(relevant)}\n"
    output += f"Somewhat Relevant: {len(somewhat_relevant)}\n"
    output += f"Irrelevant: {len(categorized_results.get('irrelevant', []))}\n\n"
    
    # Display highly relevant results
    if highly_relevant:
        output += "HIGHLY RELEVANT RESULTS:\n" + "="*25 + "\n\n"
        for i, result in enumerate(highly_relevant[:display_limit], 1):
            analysis = result.get("analysis", {})
            output += f"{i}. {result.get('title', '')}\n"
            output += f"   {result.get('link', '')}\n"
            output += f"   {result.get('snippet', '')}\n"
            output += f"   Published: {result.get('published_date', 'Unknown')}\n"
            output += f"   Content Type: {analysis.get('content_type', 'Not specified')}\n"
            output += f"   Key Information: {analysis.get('key_information', '')}\n"
            output += f"   Reasoning: {analysis.get('reasoning', '')}\n\n"
        
        if display_limit and len(highly_relevant) > display_limit:
            output += f"(Showing {display_limit} of {len(highly_relevant)} highly relevant results)\n\n"
    
    # Display relevant results
    if relevant:
        output += "RELEVANT RESULTS:\n" + "="*20 + "\n\n"
        for i, result in enumerate(relevant[:display_limit], 1):
            analysis = result.get("analysis", {})
            output += f"{i}. {result.get('title', '')}\n"
            output += f"   {result.get('link', '')}\n"
            output += f"   {result.get('snippet', '')}\n"
            output += f"   Published: {result.get('published_date', 'Unknown')}\n"
            output += f"   Content Type: {analysis.get('content_type', 'Not specified')}\n"
            output += f"   Key Information: {analysis.get('key_information', '')}\n\n"
        
        if display_limit and len(relevant) > display_limit:
            output += f"(Showing {display_limit} of {len(relevant)} relevant results)\n\n"
    
    # Briefly mention somewhat relevant results if needed
    if somewhat_relevant and display_limit:
        output += "SOMEWHAT RELEVANT RESULTS:\n" + "="*25 + "\n\n"
        for i, result in enumerate(somewhat_relevant[:display_limit], 1):
            analysis = result.get("analysis", {})
            output += f"{i}. {result.get('title', '')}\n"
            output += f"   {result.get('link', '')}\n"
            output += f"   Published: {result.get('published_date', 'Unknown')}\n"
            output += f"   Content Type: {analysis.get('content_type', 'Not specified')}\n\n"
        
        if len(somewhat_relevant) > display_limit:
            output += f"(Showing {display_limit} of {len(somewhat_relevant)} somewhat relevant results)\n"
    
    return output

def intelligent_search_process(
    companies: List[Dict[str, Any]],
    openai_model: str = "gpt-4.1-nano",
    display_limit: int = 10,
    specific_company: str = None,
    results_per_company: int = 10,
    min_relevance_score: float = 0.15
) -> List[Dict[str, Any]]:
    """Run the intelligent search and analysis process."""
    # Get API credentials
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    google_cse_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
    openai_api_key = os.environ.get("1OPENAI_API_KEY")
    
    if not google_api_key or not google_cse_id:
        logger.error("GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID must be set in environment variables or .env file.")
        return []
    
    if not openai_api_key:
        logger.error("OPENAI_API_KEY must be set for search result analysis.")
        return []
    
    # Track results
    all_analyzed_results = []
    
    # Process each company
    for company in companies:
        company_name = company.get("company_name", "")
        
        # Skip if not the specified company (when specific_company is provided)
        if specific_company and company_name != specific_company:
            continue
        
        # Enrich company information to provide better context
        enriched_company = enrich_company_info(company)
        
        # 1. Search for the company
        results = search_company(
            enriched_company, 
            google_api_key, 
            google_cse_id,
            total_results=results_per_company
        )
        
        if results:
            # Add this line to deduplicate content generally
            results["results"] = deduplicate_similar_content(results["results"])
            
            # 2. Continue with analysis
            analyzed_results = analyze_search_results(
                enriched_company,
                results,
                openai_api_key,
                openai_model,
                min_relevance_score=min_relevance_score
            )
        
        # 3. Display formatted results
        formatted_results = format_display_results(analyzed_results, display_limit)
        print(formatted_results)
        
        # 4. Save analyzed results
        all_analyzed_results.append(analyzed_results)
    
    return all_analyzed_results

def main():
    """Main function for intelligent search."""
    try:
        logger.info("Starting intelligent search process")
        parser = argparse.ArgumentParser(description='Intelligent Search with Post-Search Analysis')
        parser.add_argument('--model', type=str, default='gpt-4.1-nano', help='OpenAI model to use')
        parser.add_argument('--display-limit', type=int, default=10, help='Maximum number of results to display for each category')
        parser.add_argument('--results-per-company', type=int, default=10, help='Number of search results to fetch per company')
        parser.add_argument('--min-relevance', type=float, default=0.15, help='Minimum relevance score to keep result (0.0-1.0)')
        parser.add_argument('--company', type=str, help='Process only this specific company (by name)')
        parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
        args = parser.parse_args()
        
        # Set logging level
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        
        # Load companies from database
        companies = get_companies_from_db(args.company)
        if not companies:
            logger.error("No companies found in database. Exiting.")
            return
        
        # Run the intelligent search process
        analyzed_results = intelligent_search_process(
            companies,
            openai_model=args.model,
            display_limit=args.display_limit,
            specific_company=args.company,
            results_per_company=args.results_per_company,
            min_relevance_score=args.min_relevance
        )
        
        # Save analyzed results to database
        if analyzed_results:
            session = SessionLocal()
            try:
                new_results_count = 0
                duplicate_results_count = 0
                
                for company_results in analyzed_results:
                    for category in ['highly_relevant', 'relevant', 'somewhat_relevant']:
                        for result in company_results['categorized_results'][category]:
                            # Check if this result already exists in the database
                            existing_result = session.query(SearchResult).filter(
                                SearchResult.link == result['link']
                            ).first()
                            
                            if existing_result:
                                duplicate_results_count += 1
                                logger.debug(f"Skipping duplicate result: {result['title'][:50]}...")
                                continue
                            
                            # Convert string date to Python date object if it exists
                            published_date_str = result.get('published_date')
                            published_date = None
                            if published_date_str:
                                try:
                                    published_date = datetime.strptime(published_date_str, '%Y-%m-%d').date()
                                except (ValueError, TypeError):
                                    logger.warning(f"Invalid date format for {published_date_str}, setting to None")
                            
                            sr = SearchResult(
                                company_id=company_results['company_id'],
                                company_name=company_results['company_name'],
                                title=result['title'],
                                link=result['link'],
                                snippet=result['snippet'],
                                published_date=published_date,
                                relevance_category=category,
                                relevance_score=result['analysis'].get('relevance_score', 0.0),
                                content_type=result['analysis'].get('content_type', ''),
                                key_information=result['analysis'].get('key_information', ''),
                                reasoning=result['analysis'].get('reasoning', ''),
                                raw_json=result
                            )
                            session.add(sr)
                            new_results_count += 1
                
                session.commit()
                logger.info(f"Saved {new_results_count} new results to database")
                if duplicate_results_count > 0:
                    logger.info(f"Skipped {duplicate_results_count} duplicate results")
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving results to database: {str(e)}")
                raise
            finally:
                session.close()

    except Exception as e:
        logger.error(f"Intelligent search process failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()